#!/usr/bin/env python3
"""Run an iPhone Safari Generic Gamepad compatibility witness workflow."""

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
    parse_int_field,
    parse_semicolon_fields,
    response_with_prefix,
    run_commands,
    utc_stamp,
)
from generic_axis_exposure_witness import select_port


DEFAULT_OUT_DIR = "target/iphone-compat"
DEFAULT_TEST_URL = "https://alexoviedo.github.io/T2/iphone-compat.html"


def write_transcript(path: pathlib.Path, records: list[CommandRecord]) -> None:
    lines: list[str] = []
    for record in records:
        lines.append(f">> {record.command}")
        lines.extend(record.responses or ["<no matching response>"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_jsonl(path: pathlib.Path, values: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for value in values:
            handle.write(json.dumps(value, sort_keys=True) + "\n")


def system_output(command: list[str]) -> str:
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
    return result.stdout.strip()


def bridge_status(record: CommandRecord) -> dict[str, str]:
    return parse_semicolon_fields(response_with_prefix([record], "BRIDGE_STATUS:"))


def field_delta(samples: list[dict[str, Any]], field: str) -> tuple[int | None, int | None, int | None]:
    values = [
        value
        for sample in samples
        for value in [parse_int_field(sample.get("bridge_status") or {}, field)]
        if value is not None
    ]
    if not values:
        return None, None, None
    return values[0], values[-1], values[-1] - values[0]


def poll_serial(serial: SerialPort, duration: float, interval: float, timeout: float) -> tuple[list[dict[str, Any]], list[CommandRecord]]:
    records: list[CommandRecord] = []
    samples: list[dict[str, Any]] = []
    start = time.monotonic()
    next_sample = start
    index = 0
    while time.monotonic() - start < duration:
        now = time.monotonic()
        if now < next_sample:
            time.sleep(min(0.1, next_sample - now))
            continue
        status_record = CommandRecord("GET_STATUS", serial.command_response("GET_STATUS", timeout))
        bridge_record = CommandRecord("GET_BRIDGE_STATUS", serial.command_response("GET_BRIDGE_STATUS", timeout))
        records.extend([status_record, bridge_record])
        samples.append(
            {
                "sample": index,
                "elapsed_seconds": round(now - start, 3),
                "status": parse_semicolon_fields(response_with_prefix([status_record], "STATUS:")),
                "bridge_status": bridge_status(bridge_record),
            }
        )
        index += 1
        next_sample += interval
    return samples, records


def parse_pasted_json(raw: str) -> tuple[dict[str, Any] | None, str | None]:
    text = raw.strip()
    if not text:
        return None, "no iPhone evidence JSON was pasted"
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, f"invalid iPhone evidence JSON: {exc}"
    if not isinstance(value, dict):
        return None, "iPhone evidence JSON was not an object"
    return value, None


def axis_delta(evidence: dict[str, Any], axis_name: str) -> float | None:
    summary = evidence.get("axis_summary")
    if not isinstance(summary, dict):
        return None
    axis = summary.get(axis_name)
    if not isinstance(axis, dict):
        return None
    value = axis.get("delta")
    return float(value) if isinstance(value, (int, float)) else None


def iphone_success(evidence: dict[str, Any] | None, published_delta: int | None) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if evidence is None:
        errors.append("missing iPhone evidence JSON")
        return False, errors
    if evidence.get("gamepad_api_supported") is not True:
        errors.append("iPhone Safari evidence did not report Gamepad API support")
    if evidence.get("connected") is not True:
        errors.append("iPhone Safari evidence did not report a connected gamepad")
    if not evidence.get("gamepad_id"):
        errors.append("iPhone Safari evidence did not include a gamepad id")
    if int(evidence.get("samples") or 0) <= 0:
        errors.append("iPhone Safari evidence did not include samples")
    for axis in ("A2", "A3", "A4", "A5"):
        delta = axis_delta(evidence, axis)
        if delta is None or delta <= 0.2:
            errors.append(f"iPhone Safari evidence did not show meaningful {axis} movement")
    mini_app = evidence.get("mini_app")
    if not isinstance(mini_app, dict) or mini_app.get("missionComplete") is not True:
        errors.append("iPhone mini app mission did not complete")
    if published_delta is None or published_delta <= 0:
        errors.append("bridge published counter did not increase during iPhone test")
    return not errors, errors


def prompt_action(message: str) -> None:
    print()
    print("=" * 78)
    print(message)
    print("=" * 78)
    input("Press Enter here after completing that action...")


def read_multiline_json() -> str:
    print()
    print("=" * 78)
    print("Paste the copied iPhone evidence JSON below.")
    print("Finish with a line containing only EOF.")
    print("=" * 78)
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "EOF":
            break
        lines.append(line)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="auto", help="Serial port or 'auto'.")
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--poll-seconds", type=float, default=90.0)
    parser.add_argument("--poll-interval-seconds", type=float, default=5.0)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--test-url", default=DEFAULT_TEST_URL)
    parser.add_argument("--evidence-json-file", type=pathlib.Path)
    parser.add_argument("--skip-iphone", action="store_true", help="Prepare artifacts and print instructions without prompting for iPhone actions.")
    args = parser.parse_args()

    stamp = utc_stamp()
    run_dir = pathlib.Path(args.out_dir) / f"iphone_safari_generic_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    port = select_port(args.port, args.timeout)
    records: list[CommandRecord] = []
    samples: list[dict[str, Any]] = []
    errors: list[str] = []
    iphone_evidence: dict[str, Any] | None = None
    pasted_error: str | None = None

    serial = SerialPort(port)
    try:
        preflight = run_commands(
            serial,
            [
                "GET_INFO",
                "GET_STATUS",
                "GET_USB_STATUS",
                "LIST_USB_DEVICES",
                "GET_CONFIG_STATUS",
                "GET_BRIDGE_STATUS",
                "START_CONFIGURED",
                "GET_STATUS",
                "GET_BRIDGE_STATUS",
            ],
            args.timeout,
        )
        records.extend(preflight)
        if not args.skip_iphone:
            prompt_action("On your iPhone, open Settings > Bluetooth and connect to `USB2BLE Gamepad`.")
            prompt_action(f"Open this URL in Safari and tap Start/Arm:\n{args.test_url}")
            print()
            print("Move the TWCS throttle min to max, rudder left/right, and press/release both toe brakes.")
            print("Then tap Copy Evidence JSON on the iPhone page.")
            print(f"Serial bridge polling will run for {args.poll_seconds:.0f} seconds now.")
        samples, poll_records = poll_serial(serial, args.poll_seconds, args.poll_interval_seconds, args.timeout)
        records.extend(poll_records)
        final_records = run_commands(serial, ["GET_BRIDGE_STATUS", "GET_STATUS"], args.timeout)
        records.extend(final_records)
    finally:
        serial.close()

    if args.evidence_json_file:
        raw = args.evidence_json_file.read_text(encoding="utf-8")
        iphone_evidence, pasted_error = parse_pasted_json(raw)
    elif not args.skip_iphone:
        raw = read_multiline_json()
        (run_dir / "iphone_evidence_pasted_raw.txt").write_text(raw + "\n", encoding="utf-8")
        iphone_evidence, pasted_error = parse_pasted_json(raw)

    if iphone_evidence is not None:
        (run_dir / "iphone_evidence.json").write_text(json.dumps(iphone_evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if pasted_error:
        errors.append(pasted_error)

    published_start, published_end, published_delta = field_delta(samples, "published")
    not_connected_start, not_connected_end, not_connected_delta = field_delta(samples, "skipped_not_connected")
    not_ready_start, not_ready_end, not_ready_delta = field_delta(samples, "skipped_not_ready")
    config_status = parse_semicolon_fields(response_with_prefix(records, "CONFIG_STATUS:"))
    usb_devices = response_with_prefix(records, "USB_DEVICES:") or ""
    last_errors = sorted({(sample.get("bridge_status") or {}).get("last_error", "none") for sample in samples})

    if config_status.get("persona") != "generic_gamepad":
        errors.append("loaded config was not generic_gamepad")
    if config_status.get("profile") != "custom_runtime":
        errors.append("loaded config was not custom_runtime")
    if config_status.get("mappings") != "6":
        errors.append("loaded config did not report six mappings")
    if "vid=2109,pid=2813" not in usb_devices:
        errors.append("HooToo hub not observed")
    if "vid=044f,pid=b10a" not in usb_devices:
        errors.append("T.16000M stick not observed")
    if "vid=044f,pid=b687" not in usb_devices:
        errors.append("TWCS/RJ12 not observed")
    if not_connected_delta not in (0, None):
        errors.append("skipped_not_connected increased during iPhone test")
    if not_ready_delta not in (0, None):
        errors.append("skipped_not_ready increased during iPhone test")
    if any(value != "none" for value in last_errors):
        errors.append("bridge last_error was not none")

    passed, iphone_errors = iphone_success(iphone_evidence, published_delta)
    errors.extend(iphone_errors)
    passed = not errors
    summary = {
        "run_dir": str(run_dir),
        "captured_at": stamp,
        "commit_sha": system_output(["git", "rev-parse", "HEAD"]),
        "git_dirty": bool(system_output(["git", "status", "--short"])),
        "selected_port": port,
        "test_url": args.test_url,
        "host_os": system_output(["sw_vers"]),
        "firmware_info": parse_semicolon_fields(response_with_prefix(records, "INFO:")),
        "config_status": config_status,
        "usb_devices": usb_devices,
        "bridge_sample_count": len(samples),
        "published_start": published_start,
        "published_end": published_end,
        "published_delta": published_delta,
        "skipped_not_connected_start": not_connected_start,
        "skipped_not_connected_end": not_connected_end,
        "skipped_not_connected_delta": not_connected_delta,
        "skipped_not_ready_start": not_ready_start,
        "skipped_not_ready_end": not_ready_end,
        "skipped_not_ready_delta": not_ready_delta,
        "last_error_values": last_errors,
        "iphone_evidence_present": iphone_evidence is not None,
        "iphone_gamepad_api_supported": None if iphone_evidence is None else iphone_evidence.get("gamepad_api_supported"),
        "iphone_gamepad_connected": None if iphone_evidence is None else iphone_evidence.get("connected"),
        "iphone_gamepad_id": None if iphone_evidence is None else iphone_evidence.get("gamepad_id"),
        "iphone_samples": None if iphone_evidence is None else iphone_evidence.get("samples"),
        "iphone_axis_deltas": None
        if iphone_evidence is None
        else {axis: axis_delta(iphone_evidence, axis) for axis in ("A2", "A3", "A4", "A5")},
        "iphone_mini_app": None if iphone_evidence is None else iphone_evidence.get("mini_app"),
        "iphone_safari_generic_gamepad_passed": passed,
        "errors": errors,
        "claim_boundary": [
            "single iPhone Safari Gamepad API smoke only if passed",
            "not broad iOS compatibility",
            "not native App Store game compatibility",
            "not BLE bond persistence",
            "not final calibration quality",
        ],
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_jsonl(run_dir / "bridge_status_samples.jsonl", samples)
    write_transcript(run_dir / "serial_transcript.txt", records)
    (run_dir / "operator_notes.md").write_text(
        "# iPhone Safari Generic Gamepad Witness Notes\n\n"
        f"- Test URL: {args.test_url}\n"
        f"- Selected serial port: {port}\n"
        f"- iPhone actions skipped: {args.skip_iphone}\n"
        f"- Result: {'pass' if passed else 'fail'}.\n"
        "- This workflow is a single iPhone Safari/Gamepad API smoke only.\n",
        encoding="utf-8",
    )
    print(json.dumps({"run_dir": str(run_dir), "passed": passed, "errors": errors}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        raise SystemExit(130)
