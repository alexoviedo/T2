#!/usr/bin/env python3
"""Flash firmware provenance candidates and capture BLE advertisement evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import time
from typing import Any


DEFAULT_SERIAL_COMMANDS = [
    "GET_INFO",
    "GET_STATUS",
    "GET_USB_STATUS",
    "LIST_USB_DEVICES",
    "LIST_BLE_COMPAT_VARIANTS",
]


def run_command(
    argv: list[str],
    cwd: pathlib.Path,
    output_path: pathlib.Path,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        argv,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "$ " + " ".join(argv) + "\n\n" + result.stdout + result.stderr,
        encoding="utf-8",
    )
    return result


def powershell_lines(script: str, cwd: pathlib.Path) -> list[str]:
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-Command", script],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def serial_port_names(cwd: pathlib.Path) -> list[str]:
    lines = powershell_lines("[System.IO.Ports.SerialPort]::GetPortNames()", cwd)
    return sorted({line for line in lines if re.fullmatch(r"COM\d+", line, re.IGNORECASE)})


def autodetect_port(cwd: pathlib.Path, out_dir: pathlib.Path, timeout: float) -> str:
    candidates = serial_port_names(cwd)
    transcript = [f"candidate_ports={candidates}"]
    for candidate in candidates:
        probe = run_serial_commands(cwd, candidate, ["GET_INFO", "GET_STATUS"], timeout)
        transcript.extend([f"--- {candidate} ---", probe])
        if "INFO:" in probe and "usb2ble" in probe.lower():
            (out_dir / "serial_autodetect.txt").write_text("\n".join(transcript), encoding="utf-8")
            return candidate
    if len(candidates) == 1:
        (out_dir / "serial_autodetect.txt").write_text("\n".join(transcript), encoding="utf-8")
        return candidates[0]
    raise RuntimeError("No serial COM port detected")


def run_serial_commands(cwd: pathlib.Path, port: str, commands: list[str], timeout: float) -> str:
    result = subprocess.run(
        [sys.executable, "tools/serial_command.py", "--port", port, "--timeout", str(timeout), *commands],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout + result.stderr


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_offset_from_manifest(manifest: pathlib.Path | None, artifact: pathlib.Path) -> int | None:
    if manifest is None:
        return None
    text = manifest.read_text(encoding="utf-8", errors="replace")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"flash_command=.*?\s(0x[0-9a-fA-F]+|\d+)\s+\S+", text)
        if match:
            return int(match.group(1), 0)
        return None
    artifact_name = artifact.name
    for build in data.get("builds", []):
        for part in build.get("parts", []):
            if pathlib.PurePosixPath(str(part.get("path", ""))).name == artifact_name:
                return int(part["offset"])
    parts = [part for build in data.get("builds", []) for part in build.get("parts", [])]
    if len(parts) == 1 and "offset" in parts[0]:
        return int(parts[0]["offset"])
    return None


def flash_artifact(
    cwd: pathlib.Path,
    artifact: pathlib.Path,
    manifest: pathlib.Path | None,
    port: str,
    out_dir: pathlib.Path,
    mode: str,
) -> dict[str, Any]:
    if artifact.suffix.lower() == ".bin":
        offset = parse_offset_from_manifest(manifest, artifact)
        if offset is None:
            raise RuntimeError(f"Refusing to flash merged binary without explicit manifest offset: {artifact}")
        argv = [
            "espflash",
            "write-bin",
            "--chip",
            "esp32s3",
            "--port",
            port,
            hex(offset),
            str(artifact),
        ]
        flash_method = "write-bin"
    else:
        offset = None
        argv = ["espflash", "flash", "--port", port, str(artifact)]
        flash_method = "flash-elf"
    result = run_command(argv, cwd, out_dir / "flash_output.txt", timeout=180)
    return {
        "mode": mode,
        "flash_method": flash_method,
        "offset": offset,
        "returncode": result.returncode,
        "succeeded": result.returncode == 0,
    }


def run_watcher(cwd: pathlib.Path, out_dir: pathlib.Path, duration: float) -> dict[str, Any]:
    result = subprocess.run(
        [
            sys.executable,
            "tools/windows_ble_advertising_watcher.py",
            "--duration",
            str(duration),
            "--out-dir",
            str(out_dir),
            "--run-name",
            "windows_ble_scan",
        ],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    (out_dir / "windows_ble_watcher_stdout.txt").write_text(result.stdout, encoding="utf-8")
    (out_dir / "windows_ble_watcher_stderr.txt").write_text(result.stderr, encoding="utf-8")
    summary_path = out_dir / "windows_ble_scan" / "scan_summary.json"
    if summary_path.exists():
        return json.loads(summary_path.read_text(encoding="utf-8"))
    return {"returncode": result.returncode, "error": "scan_summary_missing"}


def scan_name_summary(out_dir: pathlib.Path, names: list[str]) -> dict[str, Any]:
    scan_path = out_dir / "windows_ble_scan" / "scan_all.jsonl"
    records: list[dict[str, Any]] = []
    if scan_path.exists():
        records = [json.loads(line) for line in scan_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    name_results: dict[str, Any] = {}
    for name in names:
        name_lower = name.lower()
        name_hex = name.encode().hex()
        exact = [record for record in records if str(record.get("local_name", "")).lower() == name_lower]
        contains = [record for record in records if name_lower in str(record.get("local_name", "")).lower()]
        raw = [
            record
            for record in records
            for section in (record.get("data_sections") or [])
            if name_hex in str(section.get("data_hex", "")).lower()
        ]
        matched = exact or contains or raw
        rssis = [record.get("rssi_dbm") for record in matched if isinstance(record.get("rssi_dbm"), int)]
        name_results[name] = {
            "seen": bool(matched),
            "exact_local_name_count": len(exact),
            "contains_local_name_count": len(contains),
            "raw_name_bytes_count": len(raw),
            "addresses": sorted({str(record.get("bluetooth_address")) for record in matched if record.get("bluetooth_address")}),
            "rssi_min": min(rssis) if rssis else None,
            "rssi_max": max(rssis) if rssis else None,
        }
    return {
        "records": len(records),
        "unique_addresses": len({str(record.get("bluetooth_address")) for record in records if record.get("bluetooth_address")}),
        "names": name_results,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=pathlib.Path, required=True)
    parser.add_argument("--manifest", type=pathlib.Path, default=None)
    parser.add_argument("--name-filter", action="append", default=[])
    parser.add_argument("--mode", choices=("release", "pages", "actions", "local"), required=True)
    parser.add_argument("--out-dir", type=pathlib.Path, required=True)
    parser.add_argument("--port", default=None)
    parser.add_argument("--serial-timeout", type=float, default=5.0)
    parser.add_argument("--scan-duration", type=float, default=30.0)
    parser.add_argument("--boot-wait", type=float, default=6.0)
    parser.add_argument("--start-command", action="append", default=[])
    parser.add_argument("--skip-flash", action="store_true")
    parser.add_argument("--restore-current", type=pathlib.Path, default=None)
    parser.add_argument("--restore-manifest", type=pathlib.Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cwd = pathlib.Path.cwd()
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact = args.artifact.resolve()
    manifest = args.manifest.resolve() if args.manifest else None
    port = args.port or autodetect_port(cwd, out_dir, args.serial_timeout)

    summary: dict[str, Any] = {
        "mode": args.mode,
        "artifact": str(artifact),
        "artifact_size": artifact.stat().st_size,
        "artifact_sha256": sha256(artifact),
        "manifest": str(manifest) if manifest else None,
        "manifest_sha256": sha256(manifest) if manifest else None,
        "selected_port": port,
        "name_filters": args.name_filter,
    }

    if args.skip_flash:
        summary["flash"] = {"skipped": True}
    else:
        summary["flash"] = flash_artifact(cwd, artifact, manifest, port, out_dir, args.mode)
        if not summary["flash"]["succeeded"]:
            (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
            print(json.dumps(summary, indent=2, sort_keys=True))
            return 2

    time.sleep(args.boot_wait)
    serial_commands = [*DEFAULT_SERIAL_COMMANDS, *args.start_command]
    serial_text = run_serial_commands(cwd, port, serial_commands, args.serial_timeout)
    (out_dir / "serial_probe.txt").write_text(serial_text, encoding="utf-8")
    summary["serial_responded"] = "INFO:" in serial_text or "STATUS:" in serial_text
    summary["serial_error"] = "ERROR:" in serial_text
    summary["start_commands"] = args.start_command

    watcher = run_watcher(cwd, out_dir, args.scan_duration)
    names = args.name_filter or ["USB2BLE Gamepad", "Xbox Wireless Controller", "BLE_SMOKE"]
    name_summary = scan_name_summary(out_dir, names)
    summary["watcher_summary"] = watcher
    summary["name_scan_summary"] = name_summary
    summary["advertisement_seen"] = any(item.get("seen") for item in name_summary["names"].values())

    if args.restore_current:
        restore_artifact = args.restore_current.resolve()
        restore_manifest = args.restore_manifest.resolve() if args.restore_manifest else None
        summary["restore"] = flash_artifact(cwd, restore_artifact, restore_manifest, port, out_dir / "restore_current", "local")

    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    notes = [
        f"# Firmware BLE Provenance Witness: {args.mode}",
        "",
        f"- Artifact: `{artifact}`",
        f"- SHA256: `{summary['artifact_sha256']}`",
        f"- Port: `{port}`",
        f"- Advertisement seen: `{summary['advertisement_seen']}`",
        f"- Serial responded: `{summary['serial_responded']}`",
        f"- Windows total advertisements: `{watcher.get('total_advertisements')}`",
        f"- Windows unique addresses: `{watcher.get('unique_addresses')}`",
    ]
    for name, result in name_summary["names"].items():
        notes.append(f"- `{name}` seen: `{result['seen']}` addresses={result['addresses']}")
    (out_dir / "operator_notes.md").write_text("\n".join(notes) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
