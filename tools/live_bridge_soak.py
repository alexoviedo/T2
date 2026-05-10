#!/usr/bin/env python3
"""Run a repeatable live bridge soak and save serial/browser evidence."""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import time
from typing import Any

from asap_demo_rehearsal import (
    CommandRecord,
    SerialPort,
    find_latest_capture_file,
    open_browser,
    parse_int_field,
    parse_semicolon_fields,
    print_record,
    read_capture_tail,
    run_commands,
    start_witness_server,
    utc_stamp,
)


DEFAULT_PORT = "/dev/cu.usbmodem5B5E0200881"
DEFAULT_WITNESS_PORT = 8767

PERSONAS = {
    "generic": {
        "start_command": "START_BLE_GENERIC_GAMEPAD",
        "persona_id": "generic_gamepad",
        "device_name": "USB2BLE Gamepad",
    },
    "xbox": {
        "start_command": "START_BLE_XBOX_CONTROLLER",
        "persona_id": "xbox_wireless_controller",
        "device_name": "Xbox Wireless Controller",
    },
}


def maybe_prompt(message: str, assume_ready: bool) -> None:
    print()
    print(message)
    if assume_ready:
        return
    try:
        input("Press Enter when ready...")
    except EOFError:
        print("No interactive stdin available; continuing after a short pause.")
        time.sleep(2.0)


def has_ble_connected(records: list[CommandRecord]) -> bool:
    return any(
        "ble=Connected" in response
        for record in records
        for response in record.responses
        if response.startswith("STATUS:")
    )


def wait_for_connected(
    serial: SerialPort,
    records: list[CommandRecord],
    persona: str,
    timeout: float,
    attempts: int,
    assume_ready: bool,
) -> bool:
    if has_ble_connected(records):
        return True

    device_name = str(PERSONAS[persona]["device_name"])
    print()
    print(f"BLE is advertising as: {device_name}")
    print("Pair/connect that Bluetooth device on the Mac, then recheck status.")
    for attempt in range(1, attempts + 1):
        if assume_ready:
            time.sleep(2.0)
        else:
            try:
                input(f"Press Enter to recheck BLE connection ({attempt}/{attempts})...")
            except EOFError:
                print("No interactive stdin available; rechecking after a short pause.")
                time.sleep(2.0)
        record = CommandRecord("GET_STATUS", serial.command_response("GET_STATUS", timeout))
        print_record(record)
        records.append(record)
        if has_ble_connected([record]):
            return True
    return False


def first_response(record: CommandRecord, prefix: str) -> str | None:
    return next((line for line in record.responses if line.startswith(prefix)), None)


def bridge_status(record: CommandRecord) -> dict[str, str]:
    return parse_semicolon_fields(first_response(record, "BRIDGE_STATUS:"))


def status_connected(record: CommandRecord) -> bool:
    return any(
        "ble=Connected" in response
        for response in record.responses
        if response.startswith("STATUS:")
    )


def status_persona(record: CommandRecord) -> str | None:
    for response in record.responses:
        if not response.startswith("STATUS:"):
            continue
        fields = parse_semicolon_fields(response)
        return fields.get("persona")
    return None


def read_browser_events(capture_file: pathlib.Path | None) -> list[dict[str, Any]]:
    if capture_file is None or not capture_file.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in capture_file.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            events.append(value)
    return events


def write_transcript(
    path: pathlib.Path,
    sections: list[tuple[str, list[CommandRecord]]],
) -> None:
    lines: list[str] = []
    for section, records in sections:
        lines.append(f"# {section}")
        for record in records:
            lines.append(f">> {record.command}")
            lines.extend(record.responses or ["<no matching response>"])
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_samples_jsonl(path: pathlib.Path, samples: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for sample in samples:
            handle.write(json.dumps(sample, sort_keys=True) + "\n")


def analyze(
    persona: str,
    preflight: list[CommandRecord],
    bridge_records: list[CommandRecord],
    samples: list[dict[str, Any]],
    stop_records: list[CommandRecord],
    browser_events: list[dict[str, Any]],
) -> dict[str, Any]:
    persona_id = str(PERSONAS[persona]["persona_id"])
    bridge_statuses = [
        sample["bridge_status"]
        for sample in samples
        if isinstance(sample.get("bridge_status"), dict)
    ]
    published_values = [
        value
        for status in bridge_statuses
        for value in [parse_int_field(status, "published")]
        if value is not None
    ]
    published_delta = (
        published_values[-1] - published_values[0] if len(published_values) >= 2 else 0
    )

    def delta_for(field: str) -> int:
        values = [
            value
            for status in bridge_statuses
            for value in [parse_int_field(status, field)]
            if value is not None
        ]
        return values[-1] - values[0] if len(values) >= 2 else 0

    last_errors = [
        status.get("last_error", "none")
        for status in bridge_statuses
        if status.get("last_error", "none") != "none"
    ]
    status_samples = [
        sample["status_record"]
        for sample in samples
        if isinstance(sample.get("status_record"), dict)
    ]
    connected_samples = [
        any("ble=Connected" in response for response in record.get("responses", []))
        for record in status_samples
    ]
    browser_input_events = [
        event
        for event in browser_events
        if event.get("connected") is True and event.get("type") in {"change", "arm", "connected"}
    ]

    stopped_status = bridge_status(stop_records[-1]) if stop_records else {}
    checks = {
        "persona_started": any(
            str(record.responses).find(f"persona={persona_id}") >= 0
            or record.command == str(PERSONAS[persona]["start_command"])
            for record in preflight
        ),
        "connected_at_start": connected_samples[0] if connected_samples else False,
        "connected_at_end": connected_samples[-1] if connected_samples else False,
        "published_increased": published_delta > 0,
        "last_error_none": not last_errors,
        "no_persona_mismatch": "persona_mismatch" not in last_errors
        and not any(
            "ERROR:PersonaMismatch" in response
            for record in bridge_records + stop_records
            for response in record.responses
        ),
        "bridge_stopped": stopped_status.get("enabled") == "false",
    }

    return {
        "checks": checks,
        "pass": all(bool(value) for value in checks.values()),
        "persona": persona,
        "persona_id": persona_id,
        "published_delta": published_delta,
        "skipped_duplicate_delta": delta_for("skipped_duplicate"),
        "skipped_rate_delta": delta_for("skipped_rate"),
        "skipped_not_connected_delta": delta_for("skipped_not_connected"),
        "skipped_not_ready_delta": delta_for("skipped_not_ready"),
        "last_errors": last_errors,
        "browser_input_count": len(browser_input_events),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--persona", choices=sorted(PERSONAS), required=True)
    parser.add_argument("--duration-seconds", type=float, default=300.0)
    parser.add_argument("--sample-interval-seconds", type=float, default=5.0)
    parser.add_argument("--timeout", type=float, default=4.0)
    parser.add_argument("--connect-attempts", type=int, default=6)
    parser.add_argument("--browser-witness", action="store_true")
    parser.add_argument("--witness-port", type=int, default=DEFAULT_WITNESS_PORT)
    parser.add_argument("--no-open", action="store_true")
    parser.add_argument("--out-dir", default="target/live-bridge-soak")
    parser.add_argument("--assume-ready", action="store_true")
    parser.add_argument("--rate-hz", type=int)
    args = parser.parse_args()

    stamp = utc_stamp()
    run_dir = pathlib.Path(args.out_dir) / f"{args.persona}_soak_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    transcript_file = run_dir / "serial_transcript.txt"
    samples_file = run_dir / "bridge_status_samples.jsonl"
    summary_file = run_dir / "summary.json"
    capture_dir = run_dir / "gamepad-witness"
    capture_file: pathlib.Path | None = None
    server: subprocess.Popen[str] | None = None
    server_lines: list[str] = []
    preflight: list[CommandRecord] = []
    bridge_records: list[CommandRecord] = []
    stop_records: list[CommandRecord] = []
    samples: list[dict[str, Any]] = []

    print("USB2BLE live bridge soak")
    print(f"Transcript directory: {run_dir}")
    print(f"Persona: {args.persona}")

    try:
        if args.browser_witness:
            server, server_lines, capture_file = start_witness_server(
                args.witness_port,
                capture_dir,
            )
            if not args.no_open:
                open_browser(args.witness_port)
            maybe_prompt(
                "In the browser witness page, click Arm if available and keep the tab focused.",
                args.assume_ready,
            )

        serial = SerialPort(args.port)
        try:
            commands = ["GET_STATUS", str(PERSONAS[args.persona]["start_command"]), "GET_STATUS"]
            preflight = run_commands(serial, commands, args.timeout)
            if not wait_for_connected(
                serial,
                preflight,
                args.persona,
                args.timeout,
                args.connect_attempts,
                args.assume_ready,
            ):
                print("ERROR: BLE did not reach Connected; aborting soak.")
                return 2

            if args.rate_hz is not None:
                bridge_records.extend(
                    run_commands(serial, [f"SET_BRIDGE_RATE_HZ {args.rate_hz}"], args.timeout)
                )

            bridge_records.extend(
                run_commands(
                    serial,
                    ["GET_BRIDGE_STATUS", "START_BRIDGE", "GET_BRIDGE_STATUS"],
                    args.timeout,
                )
            )

            start = time.monotonic()
            next_sample = start
            sample_index = 0
            while True:
                now = time.monotonic()
                elapsed = now - start
                if elapsed > args.duration_seconds and sample_index > 0:
                    break
                if now < next_sample:
                    time.sleep(min(0.1, next_sample - now))
                    continue

                status_record = CommandRecord(
                    "GET_STATUS", serial.command_response("GET_STATUS", args.timeout)
                )
                bridge_record = CommandRecord(
                    "GET_BRIDGE_STATUS",
                    serial.command_response("GET_BRIDGE_STATUS", args.timeout),
                )
                print_record(status_record)
                print_record(bridge_record)
                sample = {
                    "sample": sample_index,
                    "elapsed_seconds": round(elapsed, 3),
                    "status_record": status_record.to_json(),
                    "bridge_record": bridge_record.to_json(),
                    "status_connected": status_connected(status_record),
                    "status_persona": status_persona(status_record),
                    "bridge_status": bridge_status(bridge_record),
                }
                samples.append(sample)
                bridge_records.append(status_record)
                bridge_records.append(bridge_record)
                sample_index += 1
                next_sample += args.sample_interval_seconds

            stop_records = run_commands(
                serial,
                ["GET_BRIDGE_STATUS", "STOP_BRIDGE", "GET_BRIDGE_STATUS"],
                args.timeout,
            )
        finally:
            serial.close()

        if args.browser_witness and capture_file is None:
            capture_file = find_latest_capture_file(capture_dir)
        browser_events = read_browser_events(capture_file)
        capture_tail = read_capture_tail(capture_file)
        analysis = analyze(
            args.persona,
            preflight,
            bridge_records,
            samples,
            stop_records,
            browser_events,
        )

        write_transcript(
            transcript_file,
            [
                ("preflight", preflight),
                ("bridge", bridge_records),
                ("stop", stop_records),
            ],
        )
        write_samples_jsonl(samples_file, samples)
        payload = {
            "captured_at": stamp,
            "port": args.port,
            "persona": args.persona,
            "duration_seconds": args.duration_seconds,
            "sample_interval_seconds": args.sample_interval_seconds,
            "rate_hz": args.rate_hz,
            "transcript": str(transcript_file),
            "bridge_status_samples": str(samples_file),
            "browser_witness_capture": None if capture_file is None else str(capture_file),
            "browser_witness_tail": capture_tail,
            "server_output": server_lines,
            "analysis": analysis,
            "preflight": [record.to_json() for record in preflight],
            "stop": [record.to_json() for record in stop_records],
        }
        summary_file.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        print()
        print("Checks:")
        for name, passed in analysis["checks"].items():
            print(f"  {'PASS' if passed else 'FAIL'} {name}")
        print(f"Published delta: {analysis['published_delta']}")
        print(f"Browser input events: {analysis['browser_input_count']}")
        print()
        print(f"Saved transcript: {transcript_file}")
        print(f"Saved samples: {samples_file}")
        print(f"Saved summary: {summary_file}")
        return 0 if analysis["pass"] else 2
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
