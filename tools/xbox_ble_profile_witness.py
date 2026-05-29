#!/usr/bin/env python3
"""Capture target-side Xbox BLE profile/report diagnostics."""

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


DEFAULT_OUT_DIR = "target/xbox-ble-profile-v1"


def command_output(command: list[str]) -> str:
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    return result.stdout.strip()


def write_transcript(path: pathlib.Path, records: list[CommandRecord]) -> None:
    lines: list[str] = []
    for record in records:
        lines.append(f">> {record.command}")
        lines.extend(record.responses or ["<no matching response>"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def prefixed_json(line: str, prefix: str) -> dict[str, Any] | None:
    if not line.startswith(prefix):
        return None
    value = json.loads(line.split(":", 1)[1])
    return value if isinstance(value, dict) else None


def run_checker(command: list[str], out_path: pathlib.Path) -> dict[str, Any]:
    result = subprocess.run(
        [*command, "--out-json", str(out_path), "--quiet"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    parsed: dict[str, Any] | None = None
    if out_path.exists():
        value = json.loads(out_path.read_text(encoding="utf-8"))
        if isinstance(value, dict):
            parsed = value
    return {
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "json_path": str(out_path),
        "json": parsed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="auto")
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument(
        "--include-self-test",
        action="store_true",
        help="Also send BLE self-test publish commands; requires a connected BLE host.",
    )
    args = parser.parse_args()

    stamp = utc_stamp()
    run_dir = pathlib.Path(args.out_dir) / f"xbox_profile_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    port = select_port(args.port, args.timeout)

    commands = [
        "GET_INFO",
        "GET_STATUS",
        "GET_USB_STATUS",
        "LIST_USB_DEVICES",
        "GET_CONFIG_STATUS",
        "LIST_BLE_COMPAT_VARIANTS",
        "START_BLE_XBOX_CONTROLLER",
        "GET_STATUS",
        "GET_BLE_ADVERTISING_INFO",
        "GET_BLE_COMPAT_PROFILE",
        "GET_XBOX_GAMEPAD_MAPPING",
        "GET_XBOX_GAMEPAD_REPORT",
    ]
    if args.include_self_test:
        commands.extend(["SEND_XBOX_SELF_TEST_REPORT", "SEND_XBOX_SELF_TEST_REPORT"])

    serial = SerialPort(port)
    try:
        records = run_commands(serial, commands, args.timeout)
    finally:
        serial.close()

    write_transcript(run_dir / "serial_transcript.txt", records)
    profile_line = response_with_prefix(records, "BLE_COMPAT_PROFILE_JSON:")
    advertising = parse_semicolon_fields(response_with_prefix(records, "BLE_ADVERTISING_INFO:"))
    mapping_line = response_with_prefix(records, "XBOX_GAMEPAD_MAPPING:")
    report_line = response_with_prefix(records, "ENCODED_REPORT:")

    profile = prefixed_json(profile_line, "BLE_COMPAT_PROFILE_JSON:")
    profile_path = run_dir / "xbox_compat_profile.json"
    if profile is not None:
        profile_path.write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    ble_profile_check = run_checker(
        [
            sys.executable,
            "tools/check_ble_hid_profile.py",
            "--profile-json",
            str(profile_path),
        ],
        run_dir / "ble_hid_profile_check.json",
    ) if profile_path.exists() else None
    xbox_profile_check = run_checker(
        [
            sys.executable,
            "tools/check_xbox_ble_profile.py",
            "--profile-json",
            str(profile_path),
        ],
        run_dir / "xbox_profile_check.json",
    ) if profile_path.exists() else None

    errors: list[str] = []
    if advertising.get("variant") != "xbox_compatibility":
        errors.append("target did not report xbox_compatibility variant")
    if advertising.get("persona") != "xbox_wireless_controller":
        errors.append("target did not report Xbox persona")
    if ble_profile_check and ble_profile_check["returncode"] != 0:
        errors.append("BLE HID profile checker failed")
    if xbox_profile_check and xbox_profile_check["returncode"] != 0:
        errors.append("Xbox profile checker failed")
    if not report_line.startswith("ENCODED_REPORT:"):
        errors.append("GET_XBOX_GAMEPAD_REPORT did not return an encoded report")

    summary = {
        "captured_at": stamp,
        "run_dir": str(run_dir),
        "commit_sha": command_output(["git", "rev-parse", "HEAD"]),
        "git_dirty": bool(command_output(["git", "status", "--short"])),
        "selected_port": port,
        "commands": commands,
        "target_advertising_info": advertising,
        "compat_profile_path": str(profile_path) if profile_path.exists() else None,
        "mapping_line_present": mapping_line.startswith("XBOX_GAMEPAD_MAPPING:"),
        "report_line": report_line,
        "self_test_included": args.include_self_test,
        "ble_profile_check_returncode": None if ble_profile_check is None else ble_profile_check["returncode"],
        "xbox_profile_check_returncode": None if xbox_profile_check is None else xbox_profile_check["returncode"],
        "errors": errors,
        "xbox_ble_profile_v1_target_witness_passed": not errors,
        "claim_boundary": "target-side Xbox BLE profile/report diagnostics only; not broad host compatibility",
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (run_dir / "operator_notes.md").write_text(
        "\n".join(
            [
                "# Xbox BLE Profile v1 Target Witness",
                "",
                "This target-side witness captures Xbox BLE advertising/profile diagnostics, mapping, and encoded reports.",
                "It does not prove Xbox console, proprietary Xbox Wireless, Windows, Android, iOS, or broad host compatibility.",
                "",
                f"- Serial port: `{port}`",
                f"- Summary: `{run_dir / 'summary.json'}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
