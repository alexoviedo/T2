#!/usr/bin/env python3
"""Diagnose ESP32 BLE advertising start with a raw GAP smoke advertisement."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import subprocess
import sys
import time
from typing import Any

from serial_command import SerialPort


DEFAULT_NAME = "USB2BLE_ADV_TEST"
DEFAULT_ROOT = pathlib.Path("target/ble-advertising-start-fix")
JSON_PREFIXES = (
    "BLE_ADV_SMOKE_TEST_STATUS_JSON:",
    "BLE_ADVERTISING_EVENTS_JSON:",
)


def local_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def powershell_lines(script: str) -> list[str]:
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-Command", script],
        check=False,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def serial_port_names() -> list[str]:
    lines = powershell_lines("[System.IO.Ports.SerialPort]::GetPortNames()")
    return sorted({line for line in lines if re.fullmatch(r"COM\d+", line, re.IGNORECASE)})


def run_serial_commands(port: str, commands: list[str], timeout: float, transcript: list[str]) -> list[str]:
    serial = SerialPort(port)
    responses: list[str] = []
    try:
        for command in commands:
            transcript.append(f">> {command}")
            lines = serial.command_response(command, timeout)
            if lines:
                responses.extend(lines)
                transcript.extend(lines)
            else:
                transcript.append("<no matching response>")
    finally:
        serial.close()
    return responses


def autodetect_port(timeout: float, transcript: list[str]) -> str:
    candidates = serial_port_names()
    transcript.append(f"candidate_ports={candidates}")
    for candidate in candidates:
        try:
            responses = run_serial_commands(candidate, ["GET_INFO", "GET_STATUS"], timeout, transcript)
        except Exception as exc:
            transcript.append(f"{candidate}: probe_error={exc!r}")
            continue
        if any(line.startswith("INFO:") and "usb2ble" in line.lower() for line in responses):
            return candidate
    raise RuntimeError("No USB2BLE serial control-plane port detected")


def parse_json_payload(line: str) -> tuple[str, dict[str, Any]] | None:
    for prefix in JSON_PREFIXES:
        if line.startswith(prefix):
            payload = line[len(prefix) :].strip()
            try:
                return prefix.rstrip(":"), json.loads(payload)
            except json.JSONDecodeError:
                return prefix.rstrip(":"), {"parse_error": True, "raw": payload}
    return None


def last_prefixed_json(lines: list[str], prefix: str) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for line in lines:
        item = parse_json_payload(line)
        if item and item[0] == prefix:
            parsed = item[1]
    return parsed


def transport_status(smoke_json: dict[str, Any]) -> dict[str, Any]:
    value = smoke_json.get("transport_status")
    return value if isinstance(value, dict) else {}


def first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def classify_failure(summary: dict[str, Any]) -> str | None:
    if summary.get("windows_watcher_seen"):
        return None
    if not summary.get("adv_config_complete_success"):
        return "target_adv_payload_config"
    if not summary.get("adv_start_success"):
        return "target_ble_stack_start"
    return "windows_adapter_or_scanner"


def run_windows_watcher(attempt_dir: pathlib.Path, duration: float) -> dict[str, Any]:
    watcher = pathlib.Path("tools/windows_ble_advertising_watcher.py")
    result = subprocess.run(
        [
            sys.executable,
            str(watcher),
            "--out-dir",
            str(attempt_dir),
            "--run-name",
            "windows_ble_scan",
            "--duration",
            str(duration),
            "--mode",
            "active",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    (attempt_dir / "windows_ble_watcher_stdout.txt").write_text(result.stdout, encoding="utf-8")
    (attempt_dir / "windows_ble_watcher_stderr.txt").write_text(result.stderr, encoding="utf-8")
    summary_path = attempt_dir / "windows_ble_scan" / "scan_summary.json"
    if summary_path.exists():
        return json.loads(summary_path.read_text(encoding="utf-8"))
    return {"error": "scan_summary_missing", "returncode": result.returncode}


def next_attempt_dir(root: pathlib.Path) -> pathlib.Path:
    root.mkdir(parents=True, exist_ok=True)
    for index in range(1, 100):
        attempt = root / f"raw_smoke_attempt_{index}"
        if not attempt.exists():
            attempt.mkdir(parents=True)
            return attempt
    raise RuntimeError("Too many raw smoke attempts in artifact root")


def run_attempt(args: argparse.Namespace) -> dict[str, Any]:
    root = args.artifact_root or DEFAULT_ROOT / f"ble_adv_start_fix_{local_stamp()}"
    attempt_dir = next_attempt_dir(root)
    transcript: list[str] = []
    port = args.port or autodetect_port(args.timeout, transcript)

    pre_commands = [
        "STOP_BLE_ADV_SMOKE_TEST",
        "GET_BLE_ADVERTISING_EVENTS",
        f"START_BLE_ADV_SMOKE_TEST {args.name}",
    ]
    responses = run_serial_commands(port, pre_commands, args.timeout, transcript)
    start_response = responses[-1] if responses else ""

    poll_lines: list[str] = []
    deadline = time.monotonic() + args.poll_seconds
    while time.monotonic() < deadline:
        poll_lines.extend(
            run_serial_commands(
                port,
                ["GET_BLE_ADV_SMOKE_TEST_STATUS", "GET_BLE_ADVERTISING_EVENTS"],
                args.timeout,
                transcript,
            )
        )
        smoke = last_prefixed_json(poll_lines, "BLE_ADV_SMOKE_TEST_STATUS_JSON")
        status = transport_status(smoke)
        if status.get("active") is True or status.get("smoke_state") == "failed":
            break
        time.sleep(0.5)

    watcher_summary = run_windows_watcher(attempt_dir, args.duration)
    final_lines = run_serial_commands(
        port,
        ["GET_BLE_ADV_SMOKE_TEST_STATUS", "GET_BLE_ADVERTISING_EVENTS", "STOP_BLE_ADV_SMOKE_TEST"],
        args.timeout,
        transcript,
    )
    all_json_lines = responses + poll_lines + final_lines
    smoke_json = last_prefixed_json(all_json_lines, "BLE_ADV_SMOKE_TEST_STATUS_JSON")
    events_json = last_prefixed_json(all_json_lines, "BLE_ADVERTISING_EVENTS_JSON")
    status = transport_status(smoke_json)

    summary = {
        "artifact_dir": str(attempt_dir),
        "selected_port": port,
        "requested_name": args.name,
        "start_command_returned_success": start_response.startswith("BLE_ADV_SMOKE_TEST_STATUS_JSON:"),
        "adv_config_return": first_present(
            status.get("last_adv_config_return"), events_json.get("last_adv_config_return")
        ),
        "adv_config_complete_status": first_present(
            status.get("last_adv_raw_config_status"), events_json.get("last_adv_raw_config_status")
        ),
        "adv_config_complete_success": (
            (status.get("last_adv_raw_config_status") == 0)
            or (events_json.get("last_adv_raw_config_status") == 0)
        ),
        "scan_rsp_config_return": events_json.get("last_scan_rsp_config_return"),
        "scan_rsp_config_complete_status": events_json.get("last_scan_rsp_raw_config_status"),
        "adv_start_return": first_present(
            status.get("last_adv_start_return"), events_json.get("last_adv_start_return")
        ),
        "adv_start_complete_status": first_present(
            status.get("last_adv_start_status"), events_json.get("last_adv_start_status")
        ),
        "adv_start_success": (
            (status.get("last_adv_start_status") == 0) or (events_json.get("last_adv_start_status") == 0)
        ),
        "target_smoke_state": status.get("smoke_state"),
        "target_owner": status.get("owner") or events_json.get("owner"),
        "windows_watcher_seen": bool(watcher_summary.get("usb2ble_seen")),
        "local_name_seen": args.name in watcher_summary.get("matched_local_names", []),
        "watcher_summary": watcher_summary,
        "target_smoke_status": smoke_json,
        "target_events": events_json,
    }
    summary["failure_layer"] = classify_failure(summary)

    (attempt_dir / "serial_transcript.txt").write_text("\n".join(transcript) + "\n", encoding="utf-8")
    (attempt_dir / "raw_smoke_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", type=pathlib.Path, default=None)
    parser.add_argument("--port", default=None)
    parser.add_argument("--name", default=DEFAULT_NAME)
    parser.add_argument("--duration", type=float, default=20.0)
    parser.add_argument("--poll-seconds", type=float, default=6.0)
    parser.add_argument("--timeout", type=float, default=3.0)
    return parser.parse_args()


def main() -> int:
    run_attempt(parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
