#!/usr/bin/env python3
"""Run an iPhone BLE advertising discoverability diagnostic for USB2BLE."""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
from typing import Any

from asap_demo_rehearsal import (
    CommandRecord,
    SerialPort,
    parse_semicolon_fields,
    response_with_prefix,
    run_commands,
    utc_stamp,
)
from generic_axis_exposure_witness import select_port


DEFAULT_OUT_DIR = "target/iphone-compat"
DEFAULT_DEVICE_NAME = "USB2BLE Gamepad"


def write_transcript(path: pathlib.Path, records: list[CommandRecord]) -> None:
    lines: list[str] = []
    for record in records:
        lines.append(f">> {record.command}")
        lines.extend(record.responses or ["<no matching response>"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def system_output(command: list[str]) -> str:
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    return result.stdout.strip()


def run_ble_probe(out_dir: pathlib.Path, seconds: float) -> dict[str, Any]:
    cmd = [
        sys.executable,
        "tools/ble_advertising_probe.py",
        "--out-dir",
        str(out_dir),
        "--duration-seconds",
        str(seconds),
        "--name",
        DEFAULT_DEVICE_NAME,
    ]
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    summary_path = out_dir / "summary.json"
    summary: dict[str, Any] = {}
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    return {
        "command": cmd,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "summary": summary,
    }


def prompt_iphone(device_name: str) -> tuple[str, str]:
    print()
    print("=" * 78)
    print(f"On iPhone, open Settings > Bluetooth and wait 20 seconds.")
    print(f"Do you see `{device_name}` or a USB2BLE-like controller?")
    print("Type yes/no, then press Enter.")
    print("=" * 78)
    answer = input("> ").strip().lower()
    displayed = ""
    if answer.startswith("y"):
        print("Type the exact displayed Bluetooth name, then press Enter.")
        displayed = input("> ").strip()
    return ("yes" if answer.startswith("y") else "no", displayed)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="auto", help="Serial port or 'auto'.")
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--probe-seconds", type=float, default=20.0)
    parser.add_argument(
        "--iphone-result",
        choices=("yes", "no", "unknown"),
        default="unknown",
        help="Manual iPhone discovery result. Use unknown to prompt.",
    )
    parser.add_argument("--iphone-displayed-name", default="")
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    stamp = utc_stamp()
    run_dir = pathlib.Path(args.out_dir) / f"advertising_diagnostic_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    port = select_port(args.port, args.timeout)
    records: list[CommandRecord] = []
    errors: list[str] = []

    serial = SerialPort(port)
    try:
        records.extend(
            run_commands(
                serial,
                [
                    "GET_INFO",
                    "GET_STATUS",
                    "GET_USB_STATUS",
                    "LIST_USB_DEVICES",
                    "GET_CONFIG_STATUS",
                    "FORGET_BLE_BONDS",
                    "START_CONFIGURED",
                    "GET_STATUS",
                    "GET_BRIDGE_STATUS",
                    "GET_BLE_ADVERTISING_INFO",
                ],
                args.timeout,
            )
        )
    finally:
        serial.close()

    advertising_line = response_with_prefix(records, "BLE_ADVERTISING_INFO:")
    advertising_info = parse_semicolon_fields(advertising_line)
    if not advertising_line:
        errors.append("target did not return BLE_ADVERTISING_INFO; firmware may not include the diagnostic command")

    probe_dir = run_dir / "mac_ble_probe_current_generic"
    probe_dir.mkdir(parents=True, exist_ok=True)
    mac_probe = run_ble_probe(probe_dir, args.probe_seconds)
    mac_seen = bool((mac_probe.get("summary") or {}).get("usb2ble_name_observed"))

    iphone_result = args.iphone_result
    iphone_displayed_name = args.iphone_displayed_name
    if iphone_result == "unknown":
        iphone_result, iphone_displayed_name = prompt_iphone(
            advertising_info.get("device_name") or DEFAULT_DEVICE_NAME
        )

    variant_result = {
        "variant": "current_generic",
        "serial_port": port,
        "target_advertising_info": advertising_info,
        "target_reported_advertising_active": advertising_info.get("state") == "Advertising",
        "mac_probe_run_dir": str(probe_dir),
        "mac_probe_returncode": mac_probe["returncode"],
        "mac_saw_usb2ble_name": mac_seen,
        "iphone_manual_result": iphone_result,
        "iphone_displayed_name": iphone_displayed_name,
        "bond_clear_performed": True,
        "notes": args.notes,
    }

    if iphone_result != "yes":
        errors.append("iPhone manual discovery did not see the current Generic advertisement")

    summary = {
        "captured_at": stamp,
        "run_dir": str(run_dir),
        "commit_sha": system_output(["git", "rev-parse", "HEAD"]),
        "git_dirty": bool(system_output(["git", "status", "--short"])),
        "selected_port": port,
        "variants_tested": ["current_generic"],
        "experimental_variants_tested": [],
        "experimental_variant_reason": (
            "Deferred: this chunk adds introspection/scanner diagnostics first; "
            "advertisement layout variants should be evidence-guided and kept behind an explicit firmware option."
        ),
        "variant_results": [variant_result],
        "errors": errors,
        "iphone_discovered_any_variant": iphone_result == "yes",
        "claim_boundary": [
            "diagnostic advertising evidence only",
            "not iPhone compatibility",
            "not Safari/Gamepad API evidence",
            "not BLE bond persistence",
        ],
    }

    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_transcript(run_dir / "serial_transcript.txt", records)
    (run_dir / "variant_results.jsonl").write_text(json.dumps(variant_result, sort_keys=True) + "\n", encoding="utf-8")
    (run_dir / "operator_notes.md").write_text(
        "# iPhone BLE Advertising Diagnostic Notes\n\n"
        f"- Selected serial port: {port}\n"
        "- Variant tested: current Generic BLE HID advertisement.\n"
        f"- Target advertising info: `{advertising_line or 'missing'}`\n"
        f"- Mac probe directory: {probe_dir}\n"
        f"- iPhone discovery result: {iphone_result}\n"
        f"- Displayed name: {iphone_displayed_name or 'none'}\n"
        "- This is diagnostic evidence only; it does not prove iPhone compatibility.\n",
        encoding="utf-8",
    )
    print(json.dumps({"run_dir": str(run_dir), "iphone_seen": iphone_result == "yes", "errors": errors}, indent=2))
    return 0 if iphone_result == "yes" and not errors else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        raise SystemExit(130)
