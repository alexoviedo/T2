#!/usr/bin/env python3
"""Diagnose Generic virtual input delivery across target, macOS HID, and Chrome."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import subprocess
import sys
import time
from typing import Any

from asap_demo_rehearsal import CommandRecord, SerialPort, parse_int_field, parse_semicolon_fields, print_record
from configure_board import import_json, preset_config
from virtual_input_bridge_witness import DEFAULT_PORT, select_port


SCENARIOS = [
    "stick_left",
    "stick_right",
    "stick_forward",
    "stick_back",
    "throttle_max",
    "throttle_min",
    "rudder_left",
    "rudder_right",
    "left_toe_pressed",
    "left_toe_released",
    "right_toe_pressed",
    "right_toe_released",
]

EXPECTED_AXIS = {
    "stick_left": 0,
    "stick_right": 0,
    "stick_forward": 1,
    "stick_back": 1,
    "throttle_max": 2,
    "throttle_min": 2,
    "rudder_left": 3,
    "rudder_right": 3,
    "left_toe_pressed": 4,
    "left_toe_released": 4,
    "right_toe_pressed": 5,
    "right_toe_released": 5,
}

EXPECTED_TARGET = {
    "stick_left": "target=x",
    "stick_right": "target=x",
    "stick_forward": "target=y",
    "stick_back": "target=y",
    "throttle_max": "target=z",
    "throttle_min": "target=z",
    "rudder_left": "target=rx",
    "rudder_right": "target=rx",
    "left_toe_pressed": "target=ry",
    "left_toe_released": "target=ry",
    "right_toe_pressed": "target=rz",
    "right_toe_released": "target=rz",
}

BASELINE_ENDPOINT_SCENARIOS = {
    "throttle_min": "throttle_max",
    "left_toe_released": "left_toe_pressed",
    "right_toe_released": "right_toe_pressed",
}


def utc_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_iso(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def run_command(command: list[str], cwd: pathlib.Path | None = None) -> subprocess.Popen[str]:
    return subprocess.Popen(
        command,
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def send(serial: SerialPort, records: list[CommandRecord], command: str, timeout: float) -> CommandRecord:
    record = CommandRecord(command, serial.command_response(command, timeout))
    print_record(record)
    records.append(record)
    return record


def response_with_prefix(record: CommandRecord, prefix: str) -> str | None:
    for response in record.responses:
        if response.startswith(prefix):
            return response
    return None


def encoded_bytes(record: CommandRecord) -> str | None:
    response = response_with_prefix(record, "ENCODED_REPORT:")
    if not response:
        return None
    fields = parse_semicolon_fields(response)
    value = fields.get("bytes")
    return str(value) if value is not None else None


def bridge_published(record: CommandRecord) -> int | None:
    response = response_with_prefix(record, "BRIDGE_STATUS:")
    if not response:
        return None
    return parse_int_field(parse_semicolon_fields(response), "published")


def load_jsonl(path: pathlib.Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def chrome_sample_file(chrome_root: pathlib.Path) -> pathlib.Path | None:
    matches = sorted(chrome_root.glob("chrome_gamepad_probe_*/chrome_gamepad_probe.jsonl"))
    return matches[-1] if matches else None


def hid_event_file(hid_root: pathlib.Path) -> pathlib.Path | None:
    matches = sorted(hid_root.glob("macos_hid_event_probe_*/macos_hid_events.jsonl"))
    return matches[-1] if matches else None


def connected_gamepads(sample: dict[str, Any]) -> list[dict[str, Any]]:
    gamepads = sample.get("gamepads")
    if not isinstance(gamepads, list):
        return []
    return [gamepad for gamepad in gamepads if isinstance(gamepad, dict) and gamepad.get("connected") is True]


def values_in_window(rows: list[dict[str, Any]], start: str, end: str) -> list[dict[str, Any]]:
    start_dt = parse_iso(start)
    end_dt = parse_iso(end)
    if start_dt is None or end_dt is None:
        return []
    selected = []
    for row in rows:
        at = parse_iso(str(row.get("at", "")))
        if at is not None and start_dt <= at <= end_dt:
            selected.append(row)
    return selected


def chrome_axis_changed(samples: list[dict[str, Any]], axis_index: int) -> tuple[bool, bool, list[float]]:
    values: list[float] = []
    timestamp_changed = False
    for sample in samples:
        for gamepad in connected_gamepads(sample):
            axes = gamepad.get("axes")
            if isinstance(axes, list) and axis_index < len(axes):
                try:
                    values.append(float(axes[axis_index]))
                except (TypeError, ValueError):
                    pass
            if gamepad.get("timestamp_changed_since_previous") is True:
                timestamp_changed = True
    if not values:
        return False, timestamp_changed, values
    return max(values) - min(values) > 0.05, timestamp_changed, values


def chrome_axis_active_value_seen(values: list[float]) -> bool:
    return any(abs(value) > 0.25 for value in values)


def classify_scenario(result: dict[str, Any], hid_probe_available: bool) -> str:
    if not result["target_mapping_changed"]:
        return "target_mapping"
    if not result["target_report_changed"] and result.get("endpoint_baseline_expected"):
        return "inconclusive"
    if not result["target_report_changed"]:
        return "target_report"
    if result["bridge_published_delta"] <= 0:
        return "bridge_publish"
    if hid_probe_available and not result["macos_hid_event_seen"]:
        return "macos_hid"
    if result.get("chrome_axis_active_value_seen") and not result["chrome_axes_changed"]:
        return "witness_sampling"
    if not result["chrome_axes_changed"] and not result["chrome_timestamp_changed"]:
        return "chrome_gamepad"
    if not result["chrome_axes_changed"]:
        return "chrome_gamepad"
    return "pass"


def write_transcript(path: pathlib.Path, records: list[CommandRecord]) -> None:
    lines: list[str] = []
    for record in records:
        lines.append(f">> {record.command}")
        lines.extend(record.responses or ["<no matching response>"])
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port")
    parser.add_argument("--timeout", type=float, default=4.0)
    parser.add_argument("--out-dir", type=pathlib.Path, default=pathlib.Path("target/generic-hid-delivery-diagnosis"))
    parser.add_argument("--chrome-port", type=int, default=8880)
    parser.add_argument("--neutral-seconds", type=float, default=1.5)
    parser.add_argument("--scenario-seconds", type=float, default=2.5)
    parser.add_argument("--post-neutral-seconds", type=float, default=1.5)
    parser.add_argument("--sample-ms", type=int, default=75)
    args = parser.parse_args()

    stamp = utc_stamp()
    run_dir = args.out_dir / f"generic_hid_delivery_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    chrome_root = run_dir / "chrome"
    hid_root = run_dir / "macos_hid"
    chrome_root.mkdir()
    hid_root.mkdir()

    port = select_port(args.port or DEFAULT_PORT, args.timeout)
    records: list[CommandRecord] = []
    serial = SerialPort(port)
    scenario_windows: list[dict[str, Any]] = []
    chrome_proc: subprocess.Popen[str] | None = None
    hid_proc: subprocess.Popen[str] | None = None
    chrome_output = ""
    hid_output = ""

    total_duration = len(SCENARIOS) * (args.neutral_seconds + args.scenario_seconds + args.post_neutral_seconds) + 12
    try:
        send(serial, records, "GET_INFO", args.timeout)
        send(serial, records, "GET_STATUS", args.timeout)
        import_json(
            serial,
            records,
            json.dumps(preset_config("flight-pack-generic"), separators=(",", ":")).encode("utf-8"),
            args.timeout,
        )
        send(serial, records, "GET_CONFIG_STATUS", args.timeout)
        start = send(serial, records, "START_CONFIGURED", args.timeout)
        if any(response.startswith("ERROR:") and response != "ERROR:PersonaAlreadyActive" for response in start.responses):
            raise SystemExit("START_CONFIGURED failed: " + "; ".join(start.responses))
        send(serial, records, "START_VIRTUAL_INPUT", args.timeout)
        send(serial, records, "PUBLISH_VIRTUAL_INPUT_FRAME neutral", args.timeout)
        send(serial, records, "START_BRIDGE", args.timeout)
        send(serial, records, "GET_BRIDGE_STATUS", args.timeout)

        chrome_proc = run_command(
            [
                sys.executable,
                "tools/chrome_gamepad_probe.py",
                "--port",
                str(args.chrome_port),
                "--out-dir",
                str(chrome_root),
                "--duration",
                str(total_duration),
                "--sample-ms",
                str(args.sample_ms),
                "--session-label",
                f"generic-hid-delivery-{stamp}",
                "--chrome-mode",
                "temp-profile",
                "--auto-gesture",
            ],
            pathlib.Path("."),
        )
        hid_proc = run_command(
            [
                sys.executable,
                "tools/macos_hid_event_probe.py",
                "--duration",
                str(total_duration),
                "--out-dir",
                str(hid_root),
                "--product-contains",
                "USB2BLE Gamepad",
            ],
            pathlib.Path("."),
        )
        time.sleep(3.0)

        for scenario in SCENARIOS:
            send(serial, records, "PUBLISH_VIRTUAL_INPUT_FRAME neutral", args.timeout)
            baseline_start = now_iso()
            time.sleep(args.neutral_seconds)
            baseline_report = send(serial, records, "GET_GENERIC_GAMEPAD_REPORT", args.timeout)
            baseline_bridge = send(serial, records, "GET_BRIDGE_STATUS", args.timeout)

            active_start = now_iso()
            send(serial, records, f"PUBLISH_VIRTUAL_INPUT_FRAME {scenario}", args.timeout)
            time.sleep(args.scenario_seconds)
            virtual_status = send(serial, records, "GET_VIRTUAL_INPUT_STATUS", args.timeout)
            mapping = send(serial, records, "GET_GENERIC_GAMEPAD_MAPPING", args.timeout)
            report = send(serial, records, "GET_GENERIC_GAMEPAD_REPORT", args.timeout)
            bridge = send(serial, records, "GET_BRIDGE_STATUS", args.timeout)
            active_end = now_iso()

            send(serial, records, "PUBLISH_VIRTUAL_INPUT_FRAME neutral", args.timeout)
            time.sleep(args.post_neutral_seconds)
            scenario_windows.append(
                {
                    "scenario": scenario,
                    "baseline_start": baseline_start,
                    "active_start": active_start,
                    "active_end": active_end,
                    "expected_axis_index": EXPECTED_AXIS[scenario],
                    "expected_target": EXPECTED_TARGET[scenario],
                    "baseline_report_bytes": encoded_bytes(baseline_report),
                    "active_report_bytes": encoded_bytes(report),
                    "baseline_published": bridge_published(baseline_bridge),
                    "active_published": bridge_published(bridge),
                    "virtual_status": virtual_status.responses,
                    "mapping_response": mapping.responses,
                    "report_response": report.responses,
                    "bridge_response": bridge.responses,
                }
            )
    finally:
        try:
            send(serial, records, "GET_BRIDGE_STATUS", args.timeout)
            send(serial, records, "STOP_BRIDGE", args.timeout)
            send(serial, records, "STOP_VIRTUAL_INPUT", args.timeout)
        finally:
            serial.close()
        if chrome_proc is not None:
            try:
                chrome_output, _ = chrome_proc.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                chrome_proc.terminate()
                chrome_output, _ = chrome_proc.communicate(timeout=5)
        if hid_proc is not None:
            try:
                hid_output, _ = hid_proc.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                hid_proc.terminate()
                hid_output, _ = hid_proc.communicate(timeout=5)

    (run_dir / "chrome_probe_stdout.txt").write_text(chrome_output or "", encoding="utf-8", errors="replace")
    (run_dir / "macos_hid_probe_stdout.txt").write_text(hid_output or "", encoding="utf-8", errors="replace")
    write_transcript(run_dir / "serial_transcript.txt", records)

    chrome_file = chrome_sample_file(chrome_root)
    hid_file = hid_event_file(hid_root)
    chrome_rows = load_jsonl(chrome_file) if chrome_file else []
    hid_rows = load_jsonl(hid_file) if hid_file else []
    hid_probe_available = any(row.get("type") == "device" for row in hid_rows)

    scenario_results = []
    active_report_by_scenario = {
        window["scenario"]: window.get("active_report_bytes")
        for window in scenario_windows
        if window.get("active_report_bytes") is not None
    }
    for window in scenario_windows:
        scenario = window["scenario"]
        axis_index = int(window["expected_axis_index"])
        chrome_window = values_in_window(chrome_rows, window["active_start"], window["active_end"])
        hid_window = values_in_window(hid_rows, window["active_start"], window["active_end"])
        chrome_changed, chrome_timestamp, chrome_values = chrome_axis_changed(chrome_window, axis_index)
        baseline_published = window.get("baseline_published")
        active_published = window.get("active_published")
        published_delta = (
            int(active_published) - int(baseline_published)
            if baseline_published is not None and active_published is not None
            else 0
        )
        target_report_changed = window.get("active_report_bytes") != window.get("baseline_report_bytes")
        paired_scenario = BASELINE_ENDPOINT_SCENARIOS.get(scenario)
        paired_report = active_report_by_scenario.get(paired_scenario) if paired_scenario else None
        endpoint_baseline_expected = (
            paired_scenario is not None
            and not target_report_changed
            and paired_report is not None
            and paired_report != window.get("active_report_bytes")
        )
        result = {
            **window,
            "scenario_kind": "baseline_endpoint" if paired_scenario else "active_movement",
            "paired_scenario": paired_scenario,
            "paired_report_bytes": paired_report,
            "endpoint_baseline_expected": endpoint_baseline_expected,
            "target_mapping_changed": window["expected_target"] in " ".join(window["mapping_response"]),
            "target_report_changed": target_report_changed,
            "bridge_published_delta": published_delta,
            "macos_hid_event_seen": any(row.get("type") == "input_value" for row in hid_window),
            "macos_hid_event_count": sum(1 for row in hid_window if row.get("type") == "input_value"),
            "chrome_sample_count": len(chrome_window),
            "chrome_timestamp_changed": chrome_timestamp,
            "chrome_axes_changed": chrome_changed,
            "chrome_axis_active_value_seen": chrome_axis_active_value_seen(chrome_values),
            "chrome_axis_values": chrome_values,
        }
        result["failure_layer"] = classify_scenario(result, hid_probe_available)
        scenario_results.append(result)

    summary = {
        "captured_at": stamp,
        "run_dir": str(run_dir),
        "port": port,
        "chrome_sample_file": str(chrome_file) if chrome_file else None,
        "hid_event_file": str(hid_file) if hid_file else None,
        "hid_probe_available": hid_probe_available,
        "scenario_count": len(scenario_results),
        "pass_count": sum(1 for result in scenario_results if result["failure_layer"] == "pass"),
        "failure_layers": {layer: sum(1 for result in scenario_results if result["failure_layer"] == layer) for layer in sorted({result["failure_layer"] for result in scenario_results})},
        "scenario_results": scenario_results,
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (run_dir / "scenario_results.json").write_text(json.dumps(scenario_results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["pass_count"] == summary["scenario_count"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
