#!/usr/bin/env python3
"""Reset USB2BLE BLE compatibility state and start a selected variant."""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import time
from typing import Any

from asap_demo_rehearsal import CommandRecord, SerialPort, response_with_prefix, run_commands, utc_stamp
from generic_axis_exposure_witness import select_port


DEFAULT_OUT_DIR = "target/ble-compat"
DEFAULT_RESET_COMMAND = "espflash reset --chip esp32s3 --port {port} --non-interactive"
START_COMMANDS = {
    "generic_default": "START_BLE_GENERIC_GAMEPAD",
    "generic_hogp_strict": "START_BLE_GENERIC_GAMEPAD_VARIANT generic_hogp_strict",
    "xbox_compatibility": "START_BLE_XBOX_CONTROLLER",
}


def write_transcript(path: pathlib.Path, records: list[CommandRecord]) -> None:
    lines: list[str] = []
    for record in records:
        lines.append(f">> {record.command}")
        lines.extend(record.responses or ["<no matching response>"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def system_output(command: list[str]) -> str:
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
    return result.stdout.strip()


def reset_board(port: str, command_template: str, wait_seconds: float) -> dict[str, Any]:
    command = command_template.format(port=port)
    result = subprocess.run(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    time.sleep(wait_seconds)
    return {"command": command, "returncode": result.returncode, "output": result.stdout}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="auto", help="Serial port or 'auto'.")
    parser.add_argument("--variant", default="generic_default", choices=sorted(START_COMMANDS))
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--reset-command", default=DEFAULT_RESET_COMMAND)
    parser.add_argument("--post-reset-wait-seconds", type=float, default=8.0)
    args = parser.parse_args()

    stamp = utc_stamp()
    run_dir = pathlib.Path(args.out_dir) / f"reset_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    port = select_port(args.port, args.timeout)
    records: list[CommandRecord] = []

    serial = SerialPort(port)
    try:
        records.extend(run_commands(serial, ["GET_STATUS", "GET_BRIDGE_STATUS", "STOP_BRIDGE", "FORGET_BLE_BONDS"], args.timeout))
    finally:
        serial.close()

    reset_result = reset_board(port, args.reset_command, args.post_reset_wait_seconds)

    start_command = START_COMMANDS[args.variant]
    serial = SerialPort(port)
    try:
        records.extend(
            run_commands(
                serial,
                [
                    "GET_INFO",
                    "GET_STATUS",
                    "GET_CONFIG_STATUS",
                    "LIST_BLE_COMPAT_VARIANTS",
                    start_command,
                    "GET_STATUS",
                    "GET_BLE_ADVERTISING_INFO",
                    "GET_BLE_COMPAT_PROFILE",
                ],
                args.timeout,
            )
        )
    finally:
        serial.close()

    profile_line = response_with_prefix(records, "BLE_COMPAT_PROFILE_JSON:")
    profile_path = run_dir / "compat_profile.json"
    if profile_line.startswith("BLE_COMPAT_PROFILE_JSON:"):
        profile_path.write_text(profile_line.split(":", 1)[1] + "\n", encoding="utf-8")

    checker_json = run_dir / "profile_check.json"
    checker_result = subprocess.run(
        [
            sys.executable,
            "tools/check_ble_hid_profile.py",
            "--profile-json",
            str(profile_path),
            "--out-json",
            str(checker_json),
            "--quiet",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    ) if profile_path.exists() else None

    summary = {
        "captured_at": stamp,
        "run_dir": str(run_dir),
        "commit_sha": system_output(["git", "rev-parse", "HEAD"]),
        "git_dirty": bool(system_output(["git", "status", "--short"])),
        "selected_port": port,
        "variant": args.variant,
        "start_command": start_command,
        "reset_result": reset_result,
        "profile_json": str(profile_path) if profile_path.exists() else None,
        "profile_check_json": str(checker_json) if checker_json.exists() else None,
        "profile_check_returncode": None if checker_result is None else checker_result.returncode,
        "errors": [] if reset_result["returncode"] == 0 and (checker_result is None or checker_result.returncode == 0) else ["reset or profile check failed"],
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_transcript(run_dir / "serial_transcript.txt", records)
    (run_dir / "operator_notes.md").write_text(
        "# BLE Compatibility Reset Notes\n\n"
        f"- Variant: {args.variant}\n"
        f"- Selected port: {port}\n"
        "- Steps: stop bridge, clear bonds, reset target, start variant, dump BLE compatibility profile.\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if not summary["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
