#!/usr/bin/env python3
"""Capture refined Generic Flight Pack live-bridge browser evidence."""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any

from asap_demo_rehearsal import (
    CommandRecord,
    SerialPort,
    find_latest_capture_file,
    open_browser,
    parse_usb_devices,
    print_record,
    response_with_prefix,
    run_commands,
    start_witness_server,
    utc_stamp,
)


DEFAULT_PORT = "/dev/cu.usbmodem5B5E0200881"
DEFAULT_OUT_DIR = "target/refined-generic-live-bridge-witness"
DEFAULT_BROWSER_PORT = 8765
REQUIRED_DEVICES = {
    "HooToo hub": ("2109", "2813"),
    "T.16000M stick": ("044f", "b10a"),
    "TWCS/RJ12": ("044f", "b687"),
}


@dataclass(frozen=True)
class MovementStep:
    key: str
    label: str
    instruction: str
    expected_axis_index: int
    generic_target: str
    source_control_id: str


STEPS = [
    MovementStep(
        "throttle_min",
        "TWCS throttle minimum",
        "Move only the TWCS throttle to minimum and hold it.",
        2,
        "z",
        "axis_01_32",
    ),
    MovementStep(
        "throttle_max",
        "TWCS throttle maximum",
        "Move only the TWCS throttle to maximum and hold it.",
        2,
        "z",
        "axis_01_32",
    ),
    MovementStep(
        "rudder_left",
        "TFRP/RJ12 rudder left",
        "Press only physical rudder LEFT / nose-left and hold it.",
        3,
        "rx",
        "axis_01_36",
    ),
    MovementStep(
        "rudder_right",
        "TFRP/RJ12 rudder right",
        "Press only physical rudder RIGHT / nose-right and hold it.",
        3,
        "rx",
        "axis_01_36",
    ),
    MovementStep(
        "left_toe_released",
        "Left toe brake released",
        "Release the left toe brake and keep the other controls still.",
        4,
        "ry",
        "axis_01_34",
    ),
    MovementStep(
        "left_toe_pressed",
        "Left toe brake pressed",
        "Press only the left toe brake fully and hold it.",
        4,
        "ry",
        "axis_01_34",
    ),
    MovementStep(
        "right_toe_released",
        "Right toe brake released",
        "Release the right toe brake and keep the other controls still.",
        5,
        "rz",
        "axis_01_33",
    ),
    MovementStep(
        "right_toe_pressed",
        "Right toe brake pressed",
        "Press only the right toe brake fully and hold it.",
        5,
        "rz",
        "axis_01_33",
    ),
]


def notify(message: str, enabled: bool) -> None:
    if not enabled or sys.platform != "darwin":
        return
    subprocess.run(
        [
            "osascript",
            "-e",
            f'display notification "{message}" with title "USB2BLE live bridge witness"',
        ],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        ["say", message],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def normalize_hex(value: str) -> str:
    value = value.lower().removeprefix("0x")
    return value.zfill(4)


def observed_devices(records: list[CommandRecord]) -> dict[str, bool]:
    devices = parse_usb_devices(response_with_prefix(records, "USB_DEVICES:"))
    result: dict[str, bool] = {}
    for name, (vid, pid) in REQUIRED_DEVICES.items():
        result[name] = any(
            normalize_hex(device.get("vid", "")) == normalize_hex(vid)
            and normalize_hex(device.get("pid", "")) == normalize_hex(pid)
            for device in devices
        )
    return result


def load_captures(capture_file: pathlib.Path | None) -> list[dict[str, Any]]:
    if capture_file is None or not capture_file.exists():
        return []
    captures: list[dict[str, Any]] = []
    for line in capture_file.read_text(encoding="utf-8").splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            captures.append(payload)
    return captures


def latest_connected_capture(capture_file: pathlib.Path | None) -> dict[str, Any] | None:
    for capture in reversed(load_captures(capture_file)):
        if capture.get("connected") is True and isinstance(capture.get("axes"), list):
            return capture
    return None


def wait_for_gamepad(capture_file: pathlib.Path | None, seconds: float) -> dict[str, Any] | None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        capture = latest_connected_capture(capture_file)
        if capture is not None:
            return capture
        time.sleep(0.25)
    return None


def wait_for_capture_file(out_dir: pathlib.Path, seconds: float) -> pathlib.Path | None:
    deadline = time.monotonic() + seconds
    capture_file = find_latest_capture_file(out_dir)
    while capture_file is None and time.monotonic() < deadline:
        time.sleep(0.1)
        capture_file = find_latest_capture_file(out_dir)
    return capture_file


def wait_for_capture_count(
    capture_file: pathlib.Path | None, previous_count: int, seconds: float
) -> list[dict[str, Any]]:
    deadline = time.monotonic() + seconds
    captures = load_captures(capture_file)
    while len(captures) <= previous_count and time.monotonic() < deadline:
        time.sleep(0.25)
        captures = load_captures(capture_file)
    return captures


def prompt_operator(message: str, alerts: bool, assume_ready: bool) -> None:
    print()
    print("=" * 72)
    print(message)
    print("Keep unrelated controls still.")
    notify(message, alerts)
    if assume_ready:
        time.sleep(1.0)
        return
    try:
        input("Press Enter when ready...")
    except EOFError as exc:
        raise RuntimeError("operator input was not available for a required step") from exc


def capture_step(
    serial: SerialPort,
    step: MovementStep,
    capture_file: pathlib.Path | None,
    timeout: float,
    alerts: bool,
    assume_ready: bool,
) -> dict[str, Any]:
    before_count = len(load_captures(capture_file))
    prompt_operator(step.instruction, alerts, assume_ready)
    records = run_commands(
        serial,
        [
            "GET_BRIDGE_STATUS",
            "GET_GENERIC_GAMEPAD_MAPPING",
            "GET_GENERIC_GAMEPAD_REPORT",
            "GET_BRIDGE_STATUS",
        ],
        timeout,
    )
    captures = wait_for_capture_count(capture_file, before_count, 4.0)
    new_captures = captures[before_count:]
    latest = latest_connected_capture(capture_file)
    axes = latest.get("axes", []) if latest else []
    axis_value = (
        axes[step.expected_axis_index]
        if isinstance(axes, list) and len(axes) > step.expected_axis_index
        else None
    )
    fresh_browser_capture = len(new_captures) > 0
    return {
        "step": step.key,
        "label": step.label,
        "generic_target": step.generic_target,
        "source_control_id": step.source_control_id,
        "expected_axis_index": step.expected_axis_index,
        "browser_axis_value": axis_value,
        "fresh_browser_capture": fresh_browser_capture,
        "new_browser_captures": len(new_captures),
        "latest_browser_capture": latest,
        "serial_records": [record.to_json() for record in records],
    }


def write_transcript(path: pathlib.Path, records: list[CommandRecord]) -> None:
    lines: list[str] = []
    for record in records:
        lines.append(f">> {record.command}")
        lines.extend(record.responses or ["<no matching response>"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--browser-port", type=int, default=DEFAULT_BROWSER_PORT)
    parser.add_argument("--assume-ready", action="store_true")
    parser.add_argument("--quiet-alerts", action="store_true")
    parser.add_argument(
        "--steps",
        help="Comma-separated step keys. Default: all focused refined Generic steps.",
    )
    args = parser.parse_args()

    selected = STEPS
    if args.steps:
        wanted = {step.strip() for step in args.steps.split(",") if step.strip()}
        selected = [step for step in STEPS if step.key in wanted]
        missing = wanted - {step.key for step in selected}
        if missing:
            print(f"Unknown step(s): {', '.join(sorted(missing))}", file=sys.stderr)
            return 2

    run_dir = pathlib.Path(args.out_dir) / f"refined_generic_live_bridge_{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    browser_out = run_dir / "browser"

    server, server_lines, capture_file = start_witness_server(args.browser_port, browser_out)
    open_browser(args.browser_port)

    all_records: list[CommandRecord] = []
    step_summaries: list[dict[str, Any]] = []
    errors: list[str] = []
    serial = SerialPort(args.port)

    try:
        preflight = run_commands(
            serial,
            [
                "GET_INFO",
                "GET_STATUS",
                "GET_USB_STATUS",
                "LIST_USB_DEVICES",
                "GET_CONFIG_STATUS",
                "GET_CONFIG_JSON",
            ],
            args.timeout,
        )
        all_records.extend(preflight)

        start_records = run_commands(
            serial,
            ["START_CONFIGURED", "GET_STATUS", "GET_BRIDGE_STATUS"],
            args.timeout,
        )
        all_records.extend(start_records)

        gamepad = wait_for_gamepad(capture_file, 6.0)
        if gamepad is None:
            message = (
                "In the Chrome Gamepad witness page, click Arm if available. "
                "If macOS Bluetooth is disconnected, connect USB2BLE Gamepad, "
                "then move any control once."
            )
            prompt_operator(message, not args.quiet_alerts, args.assume_ready)
            if capture_file is None:
                capture_file = wait_for_capture_file(browser_out, 5.0)
            gamepad = wait_for_gamepad(capture_file, 12.0)
        if gamepad is None:
            errors.append("browser Gamepad witness did not capture a connected gamepad")
            print("Browser Gamepad witness is not connected; stopping before movement steps.")
        else:
            print(f"Browser sees gamepad: {gamepad.get('id')}")

        if gamepad is not None:
            for step in selected:
                summary = capture_step(
                    serial,
                    step,
                    capture_file,
                    args.timeout,
                    not args.quiet_alerts,
                    args.assume_ready,
                )
                all_records.extend(
                    CommandRecord(record["command"], list(record["responses"]))
                    for record in summary["serial_records"]
                )
                if summary["browser_axis_value"] is None:
                    errors.append(f"{step.key}: no browser axis value captured")
                if not summary["fresh_browser_capture"]:
                    errors.append(f"{step.key}: no fresh browser Gamepad capture")
                step_summaries.append(summary)
                print(
                    json.dumps(
                        {
                            k: summary[k]
                            for k in ("step", "browser_axis_value", "new_browser_captures")
                        }
                    )
                )

        final_records = run_commands(serial, ["GET_BRIDGE_STATUS", "GET_STATUS"], args.timeout)
        all_records.extend(final_records)
    finally:
        serial.close()
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=3.0)

    captures = load_captures(capture_file)
    payload = {
        "run_dir": str(run_dir),
        "port": args.port,
        "capture_file": str(capture_file) if capture_file else None,
        "server_output": server_lines,
        "observed_devices": observed_devices(all_records),
        "initial_gamepad": gamepad,
        "capture_count": len(captures),
        "steps": step_summaries,
        "errors": errors,
        "host_visible_generic_evidence": bool(
            not errors
            and captures
            and step_summaries
            and all(step.get("fresh_browser_capture") for step in step_summaries)
        ),
        "serial_records": [record.to_json() for record in all_records],
    }
    (run_dir / "summary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (run_dir / "movement_summaries.json").write_text(
        json.dumps(step_summaries, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_transcript(run_dir / "serial_transcript.txt", all_records)
    (run_dir / "operator_notes.md").write_text(
        "# Refined Generic Live Bridge Witness Notes\n\n"
        "- Browser Gamepad API captures are target artifacts, not game/app compatibility.\n"
        "- Evidence is valid only for the connected browser/host run represented here.\n",
        encoding="utf-8",
    )
    if capture_file and capture_file.exists():
        (run_dir / "browser_captures.jsonl").write_text(
            capture_file.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    print(f"Saved witness artifacts: {run_dir}")
    if errors:
        print("Witness completed with errors; see summary.json.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
