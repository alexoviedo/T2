#!/usr/bin/env python3
"""Run the Xbox BLE persona rehearsal and save serial/browser evidence."""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
import time
from typing import Any

from asap_demo_rehearsal import (
    CommandRecord,
    SerialPort,
    find_latest_capture_file,
    open_browser,
    print_record,
    read_capture_tail,
    run_commands,
    start_witness_server,
    utc_stamp,
)


DEFAULT_PORT = "/dev/cu.usbmodem5B5E0200881"
DEFAULT_WITNESS_PORT = 8766
XBOX_PERSONA = "xbox_wireless_controller"
XBOX_DEVICE_NAME = "Xbox Wireless Controller"


def response_with_prefix(records: list[CommandRecord], prefix: str) -> str | None:
    for record in records:
        for response in record.responses:
            if response.startswith(prefix):
                return response
    return None


def has_ble_connected(records: list[CommandRecord]) -> bool:
    return any(
        "ble=Connected" in response
        for record in records
        for response in record.responses
        if response.startswith("STATUS:")
    )


def wait_for_xbox_connected(
    serial: SerialPort,
    records: list[CommandRecord],
    timeout: float,
    attempts: int,
    assume_ready: bool,
) -> bool:
    if has_ble_connected(records):
        return True

    print()
    print(f"BLE should be advertising as: {XBOX_DEVICE_NAME}")
    print("Pair/connect that Bluetooth device on the Mac, then recheck status.")
    for attempt in range(1, attempts + 1):
        if assume_ready:
            time.sleep(2.0)
        else:
            input(f"Press Enter to recheck BLE connection ({attempt}/{attempts})...")
        record = CommandRecord("GET_STATUS", serial.command_response("GET_STATUS", timeout))
        print_record(record)
        records.append(record)
        if has_ble_connected([record]):
            return True
    return False


def report_bytes(line: str | None) -> str | None:
    if line is None:
        return None
    match = re.search(r"(?:^|;)bytes=([0-9a-fA-F]+);", line)
    if match is None:
        return None
    return match.group(1)


def is_xbox_report(line: str | None, prefix: str) -> bool:
    bytes_hex = report_bytes(line)
    return (
        line is not None
        and line.startswith(prefix)
        and f"persona={XBOX_PERSONA};" in line
        and "report_id=1;" in line
        and bytes_hex is not None
        and len(bytes_hex) == 32
    )


def capture_shows_xbox(capture_tail: list[str]) -> bool:
    for line in capture_tail:
        try:
            capture = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(capture, dict):
            continue
        if capture.get("connected") is True and "Xbox" in str(capture.get("id", "")):
            return True
    return False


def wait_for_capture_tail(
    capture_dir: pathlib.Path,
    capture_file: pathlib.Path | None,
    timeout: float,
) -> tuple[pathlib.Path | None, list[str]]:
    deadline = time.monotonic() + timeout
    current_file = capture_file
    tail: list[str] = []
    while time.monotonic() < deadline:
        if current_file is None:
            current_file = find_latest_capture_file(capture_dir)
        tail = read_capture_tail(current_file)
        if capture_shows_xbox(tail):
            return current_file, tail
        time.sleep(0.2)
    return current_file, tail


def analyze(
    preflight: list[CommandRecord],
    connection: list[CommandRecord],
    self_test: list[CommandRecord],
    live: list[CommandRecord],
    capture_tail: list[str],
    live_required: bool,
) -> dict[str, object]:
    start = next(
        (
            response
            for record in preflight
            for response in record.responses
            if response.startswith("BLE_ACTION:action=start_xbox_controller;")
        ),
        None,
    )
    self_test_reports = [
        response
        for record in self_test
        for response in record.responses
        if response.startswith("BLE_ACTION:action=send_xbox_self_test;")
    ]
    get_report = response_with_prefix(live, "ENCODED_REPORT:")
    publish = next(
        (
            response
            for record in live
            for response in record.responses
            if response.startswith("BLE_ACTION:action=publish_xbox_gamepad;")
        ),
        None,
    )
    status_lines = [
        response
        for records in (preflight, connection, self_test)
        for record in records
        for response in record.responses
        if response.startswith("STATUS:")
    ]
    checks = {
        "start_xbox_advertising_or_connected": start is not None
        and ("state=Advertising" in start or "state=Connected" in start),
        "ble_connected": any("ble=Connected" in line for line in status_lines),
        "self_test_reports_are_xbox_16_byte": len(self_test_reports) >= 2
        and all(
            is_xbox_report(line, "BLE_ACTION:action=send_xbox_self_test;")
            for line in self_test_reports[:2]
        ),
    }
    if live_required:
        checks["get_xbox_report_is_16_byte"] = is_xbox_report(get_report, "ENCODED_REPORT:")
        checks["publish_xbox_report_connected"] = (
            is_xbox_report(publish, "BLE_ACTION:action=publish_xbox_gamepad;")
            and "state=Connected" in str(publish)
        )
    return {
        "checks": checks,
        "start": start,
        "self_test_reports": self_test_reports,
        "get_report": get_report,
        "publish": publish,
        "browser_saw_xbox": capture_shows_xbox(capture_tail),
    }


def write_transcript(
    transcript_file: pathlib.Path,
    sections: list[tuple[str, list[CommandRecord]]],
) -> None:
    lines: list[str] = []
    for section, records in sections:
        lines.append(f"# {section}")
        for record in records:
            lines.append(f">> {record.command}")
            lines.extend(record.responses or ["<no matching response>"])
        lines.append("")
    transcript_file.write_text("\n".join(lines), encoding="utf-8")


def maybe_prompt(message: str, assume_ready: bool) -> None:
    print()
    print(message)
    if not assume_ready:
        input("Press Enter when ready...")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--timeout", type=float, default=4.0)
    parser.add_argument("--out-dir", default="target/xbox-demo-rehearsal")
    parser.add_argument("--assume-ready", action="store_true")
    parser.add_argument("--connect-attempts", type=int, default=6)
    parser.add_argument("--skip-live-publish", action="store_true")
    parser.add_argument("--browser-witness", action="store_true")
    parser.add_argument("--witness-port", type=int, default=DEFAULT_WITNESS_PORT)
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()

    stamp = utc_stamp()
    run_dir = pathlib.Path(args.out_dir) / f"xbox_demo_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    transcript_file = run_dir / "serial_transcript.txt"
    summary_file = run_dir / "summary.json"
    capture_dir = run_dir / "gamepad-witness"
    capture_file: pathlib.Path | None = None
    capture_tail: list[str] = []
    server: subprocess.Popen[str] | None = None
    server_lines: list[str] = []
    preflight: list[CommandRecord] = []
    connection: list[CommandRecord] = []
    self_test: list[CommandRecord] = []
    live: list[CommandRecord] = []

    print("USB2BLE Xbox BLE demo rehearsal")
    print(f"Transcript directory: {run_dir}")
    print("Required pass evidence is serial firmware proof; browser evidence is optional.")

    try:
        if args.browser_witness:
            server, server_lines, capture_file = start_witness_server(
                args.witness_port,
                capture_dir,
            )
            if not args.no_open:
                open_browser(args.witness_port)
            maybe_prompt(
                (
                    "In the browser witness page, click Arm if available. "
                    "Xbox Gamepad API visibility is useful evidence but not required yet."
                ),
                args.assume_ready,
            )

        serial = SerialPort(args.port)
        try:
            preflight = run_commands(
                serial,
                ["GET_STATUS", "START_BLE_XBOX_CONTROLLER", "GET_STATUS"],
                args.timeout,
            )
            connected = has_ble_connected(preflight) or wait_for_xbox_connected(
                serial,
                connection,
                args.timeout,
                args.connect_attempts,
                args.assume_ready,
            )
            if connected:
                self_test = run_commands(
                    serial,
                    [
                        "SEND_XBOX_SELF_TEST_REPORT",
                        "SEND_XBOX_SELF_TEST_REPORT",
                        "GET_STATUS",
                    ],
                    args.timeout,
                )
                if not args.skip_live_publish:
                    maybe_prompt(
                        (
                            "Move or press one attached USB control, then hold it. "
                            "This live publish step proves the USB-derived Xbox path."
                        ),
                        args.assume_ready,
                    )
                    live = run_commands(
                        serial,
                        ["GET_XBOX_GAMEPAD_REPORT", "PUBLISH_XBOX_GAMEPAD_REPORT"],
                        args.timeout,
                    )
            else:
                print("BLE did not reach Connected; skipping self-test and live publish commands.")
        finally:
            serial.close()

        if args.browser_witness:
            capture_file, capture_tail = wait_for_capture_tail(capture_dir, capture_file, 5.0)

        sections = [
            ("preflight", preflight),
            ("connection", connection),
            ("self_test", self_test),
            ("live", live),
        ]
        write_transcript(transcript_file, sections)
        analysis = analyze(
            preflight,
            connection,
            self_test,
            live,
            capture_tail,
            live_required=not args.skip_live_publish,
        )
        payload: dict[str, Any] = {
            "captured_at": stamp,
            "port": args.port,
            "transcript": str(transcript_file),
            "browser_witness_capture": None if capture_file is None else str(capture_file),
            "browser_witness_tail": capture_tail,
            "server_output": server_lines,
            "live_publish_required": not args.skip_live_publish,
            "analysis": analysis,
            "preflight": [record.to_json() for record in preflight],
            "connection": [record.to_json() for record in connection],
            "self_test": [record.to_json() for record in self_test],
            "live": [record.to_json() for record in live],
        }
        summary_file.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        print()
        print("Checks:")
        checks = analysis["checks"]
        assert isinstance(checks, dict)
        for name, passed in checks.items():
            print(f"  {'PASS' if passed else 'FAIL'} {name}")
        print(f"  {'INFO' if analysis['browser_saw_xbox'] else 'WARN'} browser_saw_xbox")
        print()
        print(f"Saved transcript: {transcript_file}")
        print(f"Saved summary: {summary_file}")
        return 0 if all(bool(value) for value in checks.values()) else 2
    finally:
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=3.0)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        raise SystemExit(130)
