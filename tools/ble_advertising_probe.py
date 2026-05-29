#!/usr/bin/env python3
"""Best-effort BLE advertising probe for USB2BLE diagnostics.

Stock macOS command-line tools do not expose raw BLE advertisement bytes. This
tool captures the Bluetooth summaries that are available without extra
dependencies and records that limitation explicitly.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import shutil
import subprocess
from typing import Any


DEFAULT_OUT_DIR = "target/ble-compat"
DEFAULT_NAMES = ("USB2BLE Gamepad", "USB2BLE", "Xbox Wireless Controller")


def utc_stamp() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")


def run_command(command: list[str], timeout: float = 45.0) -> dict[str, Any]:
    started = dt.datetime.now(dt.UTC).isoformat()
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
            timeout=timeout,
        )
        return {
            "command": command,
            "started_at": started,
            "returncode": result.returncode,
            "output": result.stdout,
        }
    except FileNotFoundError:
        return {
            "command": command,
            "started_at": started,
            "returncode": None,
            "output": "",
            "error": "command not found",
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "started_at": started,
            "returncode": None,
            "output": exc.stdout or "",
            "error": f"timed out after {timeout:.1f}s",
        }


def available_command(name: str) -> bool:
    return shutil.which(name) is not None


def find_names(text: str, names: tuple[str, ...]) -> list[str]:
    return sorted({name for name in names if name.lower() in text.lower()})


def normalize_uuid(value: str) -> str:
    cleaned = value.lower().replace("0x", "").strip("{} ")
    if len(cleaned) == 4:
        return cleaned
    if "0000" in cleaned and "-0000-1000-8000-00805f9b34fb" in cleaned:
        return cleaned[4:8]
    return cleaned


def normalize_manual_scan_text(text: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    stripped = text.strip()
    if not stripped:
        return records

    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        value = None
    if value is not None:
        items = value if isinstance(value, list) else [value]
        for item in items:
            if not isinstance(item, dict):
                continue
            record = {
                "device_name": item.get("name") or item.get("localName") or item.get("deviceName"),
                "address": item.get("address") or item.get("mac") or item.get("id"),
                "rssi": item.get("rssi"),
                "flags": item.get("flags"),
                "service_uuids": [
                    normalize_uuid(str(uuid))
                    for uuid in item.get("serviceUuids", item.get("service_uuids", []))
                    if uuid
                ],
                "appearance": item.get("appearance"),
                "manufacturer_data": item.get("manufacturerData") or item.get("manufacturer_data"),
                "service_data": item.get("serviceData") or item.get("service_data"),
                "raw_bytes": item.get("rawBytes") or item.get("raw_bytes"),
                "source_format": "json",
            }
            records.append({key: val for key, val in record.items() if val not in (None, "", [])})
        return records

    name_match = re.search(
        r"(?:Complete Local Name|Local Name|Device Name|Name)\s*[:=]\s*([^\n\r]+)",
        text,
        re.IGNORECASE,
    )
    address_match = re.search(r"\b([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})\b", text)
    rssi_match = re.search(r"\bRSSI\s*[:=]\s*(-?\d+)", text, re.IGNORECASE)
    flags_match = re.search(r"\bFlags\s*[:=]\s*(0x[0-9a-fA-F]+|\d+)", text, re.IGNORECASE)
    appearance_match = re.search(r"\bAppearance\s*[:=]\s*(0x[0-9a-fA-F]+|\d+)", text, re.IGNORECASE)
    raw_match = re.search(r"\b(?:Raw Bytes|Raw Data|Advertisement Data)\s*[:=]\s*([0-9a-fA-F ]{8,})", text, re.IGNORECASE)
    uuid_candidates = {
        normalize_uuid(match)
        for match in re.findall(r"(?:0x)?([0-9a-fA-F]{4})(?:\b|,)", text)
        if match.lower() not in {"0000", "ffff"}
    }
    record = {
        "device_name": name_match.group(1).strip() if name_match else None,
        "address": address_match.group(1) if address_match else None,
        "rssi": int(rssi_match.group(1)) if rssi_match else None,
        "flags": flags_match.group(1) if flags_match else None,
        "service_uuids": sorted(uuid_candidates),
        "appearance": appearance_match.group(1) if appearance_match else None,
        "raw_bytes": raw_match.group(1).replace(" ", "") if raw_match else None,
        "source_format": "text",
    }
    cleaned = {key: val for key, val in record.items() if val not in (None, "", [])}
    return [cleaned] if len(cleaned) > 1 else []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--duration-seconds", type=float, default=20.0)
    parser.add_argument(
        "--name",
        action="append",
        dest="names",
        help="Device name substring to search for. May be repeated.",
    )
    parser.add_argument(
        "--manual-scan-file",
        type=pathlib.Path,
        action="append",
        default=[],
        help="Optional scanner text/JSON export to include and normalize.",
    )
    args = parser.parse_args()

    names = tuple(args.names) if args.names else DEFAULT_NAMES
    run_dir = pathlib.Path(args.out_dir)
    if run_dir.name == pathlib.Path(DEFAULT_OUT_DIR).name:
        run_dir = run_dir / f"advertising_probe_{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)

    command_results: list[dict[str, Any]] = []
    notes: list[str] = []
    notes.append(
        "Stock macOS tools generally do not expose raw BLE advertising fields; "
        "this probe records visible Bluetooth summaries and tool availability."
    )

    if available_command("system_profiler"):
        command_results.append(
            run_command(["system_profiler", "SPBluetoothDataType"], timeout=max(45.0, args.duration_seconds + 10.0))
        )
    else:
        notes.append("system_profiler is not available.")

    if available_command("blueutil"):
        command_results.append(run_command(["blueutil", "--paired"], timeout=10.0))
        command_results.append(run_command(["blueutil", "--recent"], timeout=10.0))
    else:
        notes.append("blueutil is not installed; skipping paired/recent Bluetooth summaries.")

    if available_command("bluetoothctl"):
        command_results.append(run_command(["bluetoothctl", "devices"], timeout=10.0))
    else:
        notes.append("bluetoothctl is not available on this host.")

    if available_command("ioreg"):
        command_results.append(run_command(["ioreg", "-r", "-c", "IOBluetoothDevice"], timeout=10.0))
    else:
        notes.append("ioreg is not available.")

    manual_outputs: list[dict[str, str]] = []
    for manual_path in args.manual_scan_file:
        if manual_path.exists():
            manual_outputs.append(
                {
                    "path": str(manual_path),
                    "output": manual_path.read_text(encoding="utf-8", errors="replace"),
                }
            )
        else:
            manual_outputs.append({"path": str(manual_path), "output": "", "error": "file not found"})

    normalized_manual = [
        {**record, "source_path": value["path"]}
        for value in manual_outputs
        for record in normalize_manual_scan_text(value.get("output", ""))
    ]

    combined_output = "\n\n".join(
        [
            "$ " + " ".join(result["command"]) + "\n" + (result.get("output") or "")
            for result in command_results
        ]
        + [
            "$ manual " + value["path"] + "\n" + value.get("output", "")
            for value in manual_outputs
        ]
    )
    observed_names = find_names(combined_output, names)
    observed_names.extend(
        name
        for record in normalized_manual
        for name in [record.get("device_name")]
        if isinstance(name, str) and any(target.lower() in name.lower() for target in names)
    )
    observed_names = sorted(set(observed_names))
    summary = {
        "captured_at": utc_stamp(),
        "run_dir": str(run_dir),
        "searched_names": list(names),
        "observed_names": observed_names,
        "usb2ble_name_observed": any("usb2ble" in name.lower() for name in observed_names),
        "raw_advertisement_fields_available": any(record.get("raw_bytes") for record in normalized_manual),
        "normalized_advertisements": normalized_manual,
        "tool_availability": {
            "system_profiler": available_command("system_profiler"),
            "blueutil": available_command("blueutil"),
            "bluetoothctl": available_command("bluetoothctl"),
            "ioreg": available_command("ioreg"),
        },
        "commands": [
            {
                "command": result["command"],
                "returncode": result.get("returncode"),
                "error": result.get("error"),
            }
            for result in command_results
        ],
        "manual_scan_files": [
            {
                "path": value["path"],
                "error": value.get("error"),
                "matched_names": find_names(value.get("output", ""), names),
                "normalized_records": normalize_manual_scan_text(value.get("output", "")),
            }
            for value in manual_outputs
        ],
        "limitations": [
            "No raw advertisement bytes, service UUID list, address, or RSSI are guaranteed from stock macOS CLI tools.",
            "Use nRF Connect, LightBlue Explorer, Android BLE scanner, a second ESP32 scanner, or a BLE sniffer for raw advertisement evidence.",
        ],
    }

    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (run_dir / "scan_output.txt").write_text(combined_output + "\n", encoding="utf-8")
    (run_dir / "operator_notes.md").write_text(
        "# BLE Advertising Probe Notes\n\n"
        + "\n".join(f"- {note}" for note in notes)
        + "\n\n"
        f"- Searched names: {', '.join(names)}\n"
        f"- Observed names: {', '.join(observed_names) if observed_names else 'none'}\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["usb2ble_name_observed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
