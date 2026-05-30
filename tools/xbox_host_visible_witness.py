#!/usr/bin/env python3
"""Capture macOS/Chrome host-visible evidence for Xbox BLE diagnostic reports."""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import shutil
import subprocess
import sys
import time
from typing import Any

from asap_demo_rehearsal import (
    CommandRecord,
    SerialPort,
    find_latest_capture_file,
    is_port_free,
    parse_semicolon_fields,
    read_capture_tail,
    response_with_prefix,
    run_commands,
    start_witness_server,
    utc_stamp,
)
from generic_axis_exposure_witness import select_port


DEFAULT_OUT_DIR = "target/xbox-host-visible-witness"
DEFAULT_WITNESS_PORT = 8767
DEFAULT_RESET_COMMAND = "espflash reset --chip esp32s3 --port {port} --non-interactive"
XBOX_PERSONA = "xbox_wireless_controller"
XBOX_DEVICE_NAME = "Xbox Wireless Controller"
XBOX_ID_PATTERNS = ("xbox wireless controller", "vendor: 045e product: 0b13")
DEFAULT_SCENARIOS = [
    "neutral",
    "left_stick_left",
    "left_stick_right",
    "left_stick_up",
    "left_stick_down",
    "right_stick_left",
    "right_stick_right",
    "right_stick_up",
    "right_stick_down",
    "left_trigger_min",
    "left_trigger_max",
    "right_trigger_min",
    "right_trigger_max",
    "hat_up",
    "hat_right",
    "hat_down",
    "hat_left",
    "button_a",
    "button_b",
    "button_x",
    "button_y",
    "button_lb",
    "button_rb",
    "button_view",
    "button_menu",
    "button_left_stick_press",
    "button_right_stick_press",
    "button_nexus",
    "button_paddle_1",
    "button_paddle_2",
    "button_paddle_3",
    "button_share",
]
SCENARIO_SETS = {
    "all": DEFAULT_SCENARIOS,
    "core": [
        "neutral",
        "left_stick_right",
        "right_stick_right",
        "left_trigger_max",
        "right_trigger_max",
        "button_a",
    ],
}
STANDARD_EXPECTED_CONTROLS = {
    "left_stick_left": {"surface": "axis", "index": 0, "direction": "negative", "label": "A0 left stick X"},
    "left_stick_right": {"surface": "axis", "index": 0, "direction": "positive", "label": "A0 left stick X"},
    "left_stick_up": {"surface": "axis", "index": 1, "direction": "negative", "label": "A1 left stick Y"},
    "left_stick_down": {"surface": "axis", "index": 1, "direction": "positive", "label": "A1 left stick Y"},
    "right_stick_left": {"surface": "axis", "index": 2, "direction": "negative", "label": "A2 right stick X"},
    "right_stick_right": {"surface": "axis", "index": 2, "direction": "positive", "label": "A2 right stick X"},
    "right_stick_up": {"surface": "axis", "index": 3, "direction": "negative", "label": "A3 right stick Y"},
    "right_stick_down": {"surface": "axis", "index": 3, "direction": "positive", "label": "A3 right stick Y"},
    "left_trigger_max": {"surface": "button", "index": 6, "direction": "positive", "label": "B6 left trigger"},
    "right_trigger_max": {"surface": "button", "index": 7, "direction": "positive", "label": "B7 right trigger"},
    "button_a": {"surface": "button", "index": 0, "direction": "positive", "label": "B0 A"},
    "button_b": {"surface": "button", "index": 1, "direction": "positive", "label": "B1 B"},
    "button_x": {"surface": "button", "index": 2, "direction": "positive", "label": "B2 X"},
    "button_y": {"surface": "button", "index": 3, "direction": "positive", "label": "B3 Y"},
    "button_lb": {"surface": "button", "index": 4, "direction": "positive", "label": "B4 LB"},
    "button_rb": {"surface": "button", "index": 5, "direction": "positive", "label": "B5 RB"},
    "button_view": {"surface": "button", "index": 8, "direction": "positive", "label": "B8 View/Back"},
    "button_menu": {"surface": "button", "index": 9, "direction": "positive", "label": "B9 Menu/Start"},
    "button_left_stick_press": {"surface": "button", "index": 10, "direction": "positive", "label": "B10 left stick press"},
    "button_right_stick_press": {"surface": "button", "index": 11, "direction": "positive", "label": "B11 right stick press"},
    "hat_up": {"surface": "button", "index": 12, "direction": "positive", "label": "B12 D-pad up"},
    "hat_down": {"surface": "button", "index": 13, "direction": "positive", "label": "B13 D-pad down"},
    "hat_left": {"surface": "button", "index": 14, "direction": "positive", "label": "B14 D-pad left"},
    "hat_right": {"surface": "button", "index": 15, "direction": "positive", "label": "B15 D-pad right"},
}
STANDARD_CORE_SCENARIOS = (
    "left_stick_right",
    "right_stick_right",
    "left_trigger_max",
    "right_trigger_max",
    "button_a",
)


def command_output(command: list[str]) -> str:
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    return result.stdout.strip()


def scenario_names(value: str) -> list[str]:
    if value in SCENARIO_SETS:
        return list(SCENARIO_SETS[value])
    names = [part.strip() for part in value.split(",") if part.strip()]
    unknown = [name for name in names if name not in DEFAULT_SCENARIOS]
    if unknown:
        raise ValueError(f"unknown scenario(s): {', '.join(unknown)}")
    return names


def load_expected_standard_layout(path: pathlib.Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return STANDARD_EXPECTED_CONTROLS
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("--expected-standard-layout must be a JSON object")
    controls = data.get("controls", data)
    if not isinstance(controls, dict):
        raise ValueError("expected layout JSON must contain an object or controls object")
    return {str(key): value for key, value in controls.items() if isinstance(value, dict)}


def write_transcript(path: pathlib.Path, records: list[CommandRecord]) -> None:
    lines: list[str] = []
    for record in records:
        lines.append(f">> {record.command}")
        lines.extend(record.responses or ["<no matching response>"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def open_chrome(port: int) -> str:
    url = f"http://127.0.0.1:{port}/"
    if sys.platform == "darwin":
        result = subprocess.run(
            ["open", "-a", "Google Chrome", url],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return url
        subprocess.run(["open", url], check=False)
        return url
    subprocess.run(["xdg-open", url], check=False)
    return url


def try_arm_chrome() -> dict[str, Any]:
    if sys.platform != "darwin":
        return {"attempted": False, "reason": "not macOS"}
    script = (
        'tell application "Google Chrome"\n'
        "  activate\n"
        '  tell active tab of front window to execute javascript "document.querySelector(\\"#armButton\\")?.click()"\n'
        "end tell\n"
    )
    result = subprocess.run(
        ["osascript", "-e", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    return {
        "attempted": True,
        "returncode": result.returncode,
        "output": result.stdout.strip(),
    }


def notify(message: str) -> None:
    if sys.platform != "darwin":
        return
    safe = message.replace("\\", "\\\\").replace('"', '\\"')
    subprocess.run(
        ["osascript", "-e", f'display notification "{safe}" with title "USB2BLE Xbox witness"'],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def maybe_prompt(message: str, assume_ready: bool) -> None:
    print()
    print("=" * 78)
    print(message)
    notify(message)
    if assume_ready:
        time.sleep(1.0)
        return
    input("Press Enter when done...")


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


def load_captures(path: pathlib.Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    captures: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            captures.append(value)
    return captures


def is_xbox_capture(capture: dict[str, Any]) -> bool:
    if capture.get("connected") is not True:
        return False
    gamepad_id = str(capture.get("id", "")).lower()
    return any(pattern in gamepad_id for pattern in XBOX_ID_PATTERNS)


def is_connected_gamepad_capture(capture: dict[str, Any]) -> bool:
    return capture.get("connected") is True and bool(str(capture.get("id", "")))


def capture_with_id(captures: list[dict[str, Any]], gamepad_id: str | None) -> dict[str, Any] | None:
    for capture in reversed(captures):
        if not is_connected_gamepad_capture(capture):
            continue
        if gamepad_id is None or capture.get("id") == gamepad_id:
            return capture
    return None


def wait_for_xbox_capture(
    capture_dir: pathlib.Path,
    capture_file: pathlib.Path | None,
    timeout: float,
) -> tuple[pathlib.Path | None, dict[str, Any] | None, list[dict[str, Any]]]:
    deadline = time.monotonic() + timeout
    current_file = capture_file
    captures: list[dict[str, Any]] = []
    while time.monotonic() < deadline:
        if current_file is None:
            current_file = find_latest_capture_file(capture_dir)
        captures = load_captures(current_file)
        for capture in reversed(captures):
            if is_xbox_capture(capture):
                return current_file, capture, captures
        time.sleep(0.2)
    return current_file, None, captures


def fallback_connected_capture(captures: list[dict[str, Any]]) -> dict[str, Any] | None:
    return capture_with_id(captures, None)


def choose_witness_port(requested: int) -> int:
    port = requested
    while port < requested + 20:
        if is_port_free(port):
            return port
        port += 1
    raise RuntimeError(f"no free browser witness port found near {requested}")


def wait_for_capture_file(capture_dir: pathlib.Path, capture_file: pathlib.Path | None) -> pathlib.Path | None:
    if capture_file is not None:
        return capture_file
    deadline = time.monotonic() + 3.0
    current = None
    while time.monotonic() < deadline:
        current = find_latest_capture_file(capture_dir)
        if current is not None:
            return current
        time.sleep(0.1)
    return current


def report_line(records: list[CommandRecord], action: str) -> str | None:
    prefix = f"BLE_ACTION:action={action};"
    return response_with_prefix(records, prefix)


def report_bytes(line: str | None) -> str | None:
    if line is None:
        return None
    match = re.search(r"(?:^|;)bytes=([0-9a-fA-F]+);", line)
    return match.group(1).lower() if match else None


def is_connected_report(line: str | None) -> bool:
    return (
        line is not None
        and "state=Connected;" in line
        and f"persona={XBOX_PERSONA};" in line
        and "report_id=1;" in line
        and (bytes_hex := report_bytes(line)) is not None
        and len(bytes_hex) == 32
    )


def axis_values(capture: dict[str, Any] | None) -> list[float]:
    axes = capture.get("axes") if capture else None
    if not isinstance(axes, list):
        return []
    return [float(value) for value in axes if isinstance(value, (int, float))]


def button_values(capture: dict[str, Any] | None) -> list[float]:
    buttons = capture.get("buttons") if capture else None
    values: list[float] = []
    if not isinstance(buttons, list):
        return values
    for button in buttons:
        if isinstance(button, dict) and isinstance(button.get("value"), (int, float)):
            values.append(float(button["value"]))
        elif isinstance(button, (int, float)):
            values.append(float(button))
    return values


def changed_indices(before: list[float], after: list[float], threshold: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index in range(max(len(before), len(after))):
        b = before[index] if index < len(before) else None
        a = after[index] if index < len(after) else None
        if b is None or a is None:
            continue
        delta = a - b
        if abs(delta) >= threshold:
            rows.append({"index": index, "before": b, "after": a, "delta": delta})
    return rows


def primary_change(
    axis_changes: list[dict[str, Any]],
    button_changes: list[dict[str, Any]],
) -> dict[str, Any] | None:
    changes = [{"surface": "axis", **change} for change in axis_changes] + [
        {"surface": "button", **change} for change in button_changes
    ]
    if not changes:
        return None
    return max(changes, key=lambda change: abs(float(change.get("delta", 0.0))))


def discovered_layout_rows(scenario_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in scenario_results:
        scenario = str(result.get("scenario", ""))
        if scenario in {"neutral", "left_trigger_min", "right_trigger_min"}:
            continue
        expected = result.get("standard_control", {}).get("expected")
        observed = primary_change(
            list(result.get("changed_axis_indices") or []),
            list(result.get("changed_button_indices") or []),
        )
        rows.append(
            {
                "scenario": scenario,
                "encoded_report_bytes": result.get("encoded_report_bytes"),
                "expected": expected,
                "observed": observed,
                "matched": None
                if expected is None
                else bool(result.get("standard_control", {}).get("matched")),
            }
        )
    return rows


def layout_diagnosis(scenario_results: list[dict[str, Any]]) -> dict[str, Any]:
    rows = discovered_layout_rows(scenario_results)
    unexpected: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    for row in rows:
        expected = row.get("expected")
        observed = row.get("observed")
        if expected is None:
            if observed is not None:
                unexpected.append(row)
            continue
        if observed is None:
            missing.append(row)
        elif not row.get("matched"):
            unexpected.append(row)
    return {
        "rows": rows,
        "unexpected_button_indices": [
            row for row in unexpected if (row.get("observed") or {}).get("surface") == "button"
        ],
        "unexpected_axis_indices": [
            row for row in unexpected if (row.get("observed") or {}).get("surface") == "axis"
        ],
        "missing_expected_indices": missing,
    }


def format_control(control: dict[str, Any] | None) -> str:
    if not control:
        return "-"
    surface = control.get("surface")
    index = control.get("index")
    direction = control.get("direction")
    if surface == "axis":
        return f"A{index} {direction}"
    if surface == "button":
        return f"B{index} {direction}"
    return str(control)


def format_observed(change: dict[str, Any] | None) -> str:
    if not change:
        return "-"
    prefix = "A" if change.get("surface") == "axis" else "B"
    return (
        f"{prefix}{change.get('index')} "
        f"{change.get('before')}->{change.get('after')} "
        f"(delta {change.get('delta')})"
    )


def write_layout_diagnosis(run_dir: pathlib.Path, diagnosis: dict[str, Any]) -> None:
    (run_dir / "layout_diagnosis.json").write_text(
        json.dumps(diagnosis, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Xbox Standard Layout Diagnosis",
        "",
        "| Scenario | Expected standard control | Observed change | Match |",
        "| --- | --- | --- | --- |",
    ]
    for row in diagnosis["rows"]:
        expected = format_control(row.get("expected"))
        observed = format_observed(row.get("observed"))
        match = row.get("matched")
        status = "n/a" if match is None else ("PASS" if match else "FAIL")
        lines.append(f"| `{row['scenario']}` | {expected} | {observed} | {status} |")
    (run_dir / "layout_diagnosis.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def find_change(changes: list[dict[str, Any]], index: int, direction: str) -> dict[str, Any] | None:
    for change in changes:
        if change.get("index") != index:
            continue
        delta = float(change.get("delta", 0.0))
        if direction == "positive" and delta > 0:
            return change
        if direction == "negative" and delta < 0:
            return change
        if direction == "any" and abs(delta) > 0:
            return change
    return None


def standard_control_result(
    scenario: str,
    axis_changes: list[dict[str, Any]],
    button_changes: list[dict[str, Any]],
    expected_controls: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    expected = (expected_controls or STANDARD_EXPECTED_CONTROLS).get(scenario)
    if expected is None:
        return {"scenario": scenario, "expected": None, "matched": None, "observed_change": None}
    changes = axis_changes if expected["surface"] == "axis" else button_changes
    observed = find_change(changes, int(expected["index"]), str(expected["direction"]))
    return {
        "scenario": scenario,
        "expected": expected,
        "matched": observed is not None,
        "observed_change": observed,
    }


def wait_for_capture_count(path: pathlib.Path | None, minimum: int, timeout: float) -> list[dict[str, Any]]:
    deadline = time.monotonic() + timeout
    captures = load_captures(path)
    while len(captures) < minimum and time.monotonic() < deadline:
        time.sleep(0.2)
        captures = load_captures(path)
    return captures


def publish_wake_sequence(
    serial: SerialPort,
    records: list[CommandRecord],
    timeout: float,
) -> None:
    records.extend(
        run_commands(
            serial,
            [
                "PUBLISH_XBOX_TEST_REPORT neutral",
                "PUBLISH_XBOX_TEST_REPORT button_a",
                "PUBLISH_XBOX_TEST_REPORT neutral",
                "PUBLISH_XBOX_TEST_REPORT left_stick_right",
                "PUBLISH_XBOX_TEST_REPORT neutral",
            ],
            timeout,
        )
    )


def bluetooth_snapshot() -> str:
    if sys.platform != "darwin":
        return command_output(["sh", "-lc", "command -v bluetoothctl >/dev/null && bluetoothctl devices || true"])
    return command_output(["system_profiler", "SPBluetoothDataType"])


def run_checker(out_dir: pathlib.Path) -> dict[str, Any]:
    out_path = out_dir / "xbox_profile_check.json"
    result = subprocess.run(
        [sys.executable, "tools/check_xbox_ble_profile.py", "--out-json", str(out_path), "--quiet"],
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
        "command": "python3 tools/check_xbox_ble_profile.py --out-json xbox_profile_check.json --quiet",
        "returncode": result.returncode,
        "stdout": result.stdout,
        "json_path": str(out_path),
        "json": parsed,
    }


def scenario_expectations() -> dict[str, str]:
    return {
        "left_stick_left": "left_stick",
        "left_stick_right": "left_stick",
        "left_stick_up": "left_stick",
        "left_stick_down": "left_stick",
        "right_stick_left": "right_stick",
        "right_stick_right": "right_stick",
        "right_stick_up": "right_stick",
        "right_stick_down": "right_stick",
        "left_trigger_max": "left_trigger",
        "right_trigger_max": "right_trigger",
        "button_a": "button",
        "button_b": "button",
        "button_x": "button",
        "button_y": "button",
        "button_lb": "button",
        "button_rb": "button",
        "button_view": "button",
        "button_menu": "button",
        "button_left_stick_press": "button",
        "button_right_stick_press": "button",
        "button_nexus": "button",
        "button_paddle_1": "button",
        "button_paddle_2": "button",
        "button_paddle_3": "button",
        "button_share": "button",
    }


def classify_scenario(scenario: str, axis_changes: list[dict[str, Any]], button_changes: list[dict[str, Any]]) -> bool:
    expected = scenario_expectations().get(scenario)
    if expected is None:
        return True
    if expected in ("left_stick", "right_stick"):
        return bool(axis_changes)
    if expected in ("left_trigger", "right_trigger", "button"):
        return bool(button_changes or axis_changes)
    return False


def browser_profile(capture: dict[str, Any] | None) -> dict[str, Any]:
    axes = axis_values(capture)
    buttons = button_values(capture)
    mapping = "" if capture is None else str(capture.get("mapping") or "")
    return {
        "id": None if capture is None else capture.get("id"),
        "mapping": mapping,
        "axes_count": len(axes),
        "buttons_count": len(buttons),
        "is_standard_mapping": mapping == "standard",
    }


def classify_standard_layout(
    browser: dict[str, Any],
    scenario_results: list[dict[str, Any]],
    xbox_like_identity_observed: bool,
    expected_controls: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    expected_controls = expected_controls or STANDARD_EXPECTED_CONTROLS
    checks = {
        result["scenario"]: result.get("standard_control", {})
        for result in scenario_results
        if result.get("standard_control", {}).get("expected") is not None
    }
    matched = {
        scenario: bool(check.get("matched"))
        for scenario, check in checks.items()
    }
    core_pass = all(matched.get(scenario, False) for scenario in STANDARD_CORE_SCENARIOS)
    required_pass = all(matched.values()) if matched else False
    any_pass = any(matched.values())
    standard_mapping = bool(browser.get("is_standard_mapping"))

    if standard_mapping and required_pass and xbox_like_identity_observed:
        result = "standard_layout_pass"
    elif standard_mapping and required_pass and not xbox_like_identity_observed:
        result = "identity_string_mismatch_only"
    elif standard_mapping and any_pass:
        result = "standard_layout_partial"
    else:
        result = "host_visible_failure"

    return {
        "classification": result,
        "standard_mapping": standard_mapping,
        "xbox_like_identity_observed": xbox_like_identity_observed,
        "core_scenarios": list(STANDARD_CORE_SCENARIOS),
        "core_pass": core_pass,
        "required_pass": required_pass,
        "matched_count": sum(1 for passed in matched.values() if passed),
        "required_count": len([scenario for scenario in expected_controls if scenario in checks]),
        "scenario_matches": matched,
        "failed_standard_scenarios": [scenario for scenario, passed in matched.items() if not passed],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="auto")
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--witness-port", type=int, default=DEFAULT_WITNESS_PORT)
    parser.add_argument("--browser-timeout", type=float, default=25.0)
    parser.add_argument("--scenario-settle-seconds", type=float, default=0.7)
    parser.add_argument("--reset-first", action="store_true")
    parser.add_argument("--reset-command", default=DEFAULT_RESET_COMMAND)
    parser.add_argument("--post-reset-wait-seconds", type=float, default=8.0)
    parser.add_argument("--assume-ready", action="store_true")
    parser.add_argument("--no-open", action="store_true")
    parser.add_argument(
        "--scenarios",
        default="all",
        help="Scenario set name (all/core) or comma-separated scenario names.",
    )
    parser.add_argument("--diagnose-layout", action="store_true")
    parser.add_argument("--discover-layout", action="store_true")
    parser.add_argument("--expected-standard-layout", type=pathlib.Path)
    parser.add_argument("--no-live-bridge", action="store_true")
    args = parser.parse_args()

    stamp = utc_stamp()
    run_dir = pathlib.Path(args.out_dir) / f"xbox_host_visible_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    capture_dir = run_dir / "gamepad-witness"
    transcript_file = run_dir / "serial_transcript.txt"
    browser_copy = run_dir / "browser_captures.jsonl"
    scenario_results_file = run_dir / "scenario_results.json"
    summary_file = run_dir / "summary.json"
    records: list[CommandRecord] = []
    scenario_results: list[dict[str, Any]] = []
    reset_result: dict[str, Any] | None = None
    server: subprocess.Popen[str] | None = None
    server_lines: list[str] = []
    capture_file: pathlib.Path | None = None
    browser_url: str | None = None
    arm_result: dict[str, Any] | None = None

    print("USB2BLE Xbox host-visible witness")
    print(f"Artifact directory: {run_dir}")
    port = select_port(args.port, args.timeout)
    scenarios = scenario_names(args.scenarios)
    expected_controls = load_expected_standard_layout(args.expected_standard_layout)

    try:
        if args.reset_first:
            reset_result = reset_board(port, args.reset_command, args.post_reset_wait_seconds)

        checker = run_checker(run_dir)
        witness_port = choose_witness_port(args.witness_port)
        if witness_port != args.witness_port:
            print(f"Browser witness port {args.witness_port} is busy; using {witness_port}.")
        server, server_lines, capture_file = start_witness_server(witness_port, capture_dir)
        capture_file = wait_for_capture_file(capture_dir, capture_file)
        if capture_file is None:
            raise RuntimeError("browser witness server did not create a capture file")
        if not args.no_open:
            browser_url = open_chrome(witness_port)
            time.sleep(1.5)
            arm_result = try_arm_chrome()

        serial = SerialPort(port)
        try:
            records.extend(
                run_commands(
                    serial,
                    [
                        "GET_INFO",
                        "GET_STATUS",
                        "GET_BLE_ADVERTISING_INFO",
                        "GET_BLE_COMPAT_PROFILE",
                        "GET_XBOX_GAMEPAD_REPORT",
                        "GET_BRIDGE_STATUS",
                        "START_BLE_XBOX_CONTROLLER",
                        "GET_STATUS",
                        "GET_BLE_ADVERTISING_INFO",
                        "GET_BLE_COMPAT_PROFILE",
                        "GET_XBOX_GAMEPAD_REPORT",
                        "GET_BRIDGE_STATUS",
                    ],
                    args.timeout,
                )
            )

            capture_file, xbox_capture, captures = wait_for_xbox_capture(
                capture_dir,
                capture_file,
                args.browser_timeout,
            )
            if xbox_capture is None:
                publish_wake_sequence(serial, records, args.timeout)
                capture_file, xbox_capture, captures = wait_for_xbox_capture(
                    capture_dir,
                    capture_file,
                    5.0,
                )
            active_capture = xbox_capture
            if active_capture is None:
                active_capture = fallback_connected_capture(captures)

            if active_capture is None:
                (run_dir / "bluetooth_state_before_prompt.txt").write_text(
                    bluetooth_snapshot() + "\n",
                    encoding="utf-8",
                )
                maybe_prompt(
                    f'Open macOS Bluetooth settings, connect "{XBOX_DEVICE_NAME}", '
                    "then click Arm in the Chrome witness page if needed.",
                    args.assume_ready,
                )
                arm_result = try_arm_chrome()
                records.append(CommandRecord("GET_STATUS", serial.command_response("GET_STATUS", args.timeout)))
                publish_wake_sequence(serial, records, args.timeout)
                capture_file, xbox_capture, captures = wait_for_xbox_capture(
                    capture_dir,
                    capture_file,
                    args.browser_timeout,
                )
                active_capture = xbox_capture or fallback_connected_capture(captures)

            active_gamepad_id = None if active_capture is None else str(active_capture.get("id"))

            if active_capture is not None:
                for scenario in scenarios:
                    before_captures = load_captures(capture_file)
                    before = capture_with_id(before_captures, active_gamepad_id) or active_capture
                    command = f"PUBLISH_XBOX_TEST_REPORT {scenario}"
                    scenario_records = run_commands(serial, [command], args.timeout)
                    records.extend(scenario_records)
                    time.sleep(args.scenario_settle_seconds)
                    after_captures = wait_for_capture_count(
                        capture_file,
                        len(before_captures) + 1,
                        max(1.0, args.scenario_settle_seconds + 1.0),
                    )
                    after = capture_with_id(after_captures, active_gamepad_id) or before
                    line = report_line(scenario_records, "publish_xbox_test_report")
                    axis_changes = changed_indices(axis_values(before), axis_values(after), 0.05)
                    button_changes = changed_indices(button_values(before), button_values(after), 0.05)
                    standard_control = standard_control_result(
                        scenario,
                        axis_changes,
                        button_changes,
                        expected_controls,
                    )
                    scenario_results.append(
                        {
                            "scenario": scenario,
                            "serial_line": line,
                            "encoded_report_bytes": report_bytes(line),
                            "serial_report_connected": is_connected_report(line),
                            "browser_before": before,
                            "browser_after": after,
                            "changed_axis_indices": axis_changes,
                            "changed_button_indices": button_changes,
                            "standard_control": standard_control,
                            "browser_changed_expected_surface": classify_scenario(
                                scenario,
                                axis_changes,
                                button_changes,
                            ),
                        }
                    )
                    if scenario != "neutral":
                        neutral_records = run_commands(
                            serial,
                            ["PUBLISH_XBOX_TEST_REPORT neutral"],
                            args.timeout,
                        )
                        records.extend(neutral_records)
                        time.sleep(0.25)

            records.extend(
                run_commands(serial, ["GET_STATUS", "GET_BRIDGE_STATUS"], args.timeout)
            )
        finally:
            serial.close()

        if capture_file is not None and capture_file.exists():
            shutil.copyfile(capture_file, browser_copy)
        write_transcript(transcript_file, records)

        observed_identity = None
        xbox_like_identity_observed = False
        active_browser_capture: dict[str, Any] | None = None
        all_captures = load_captures(capture_file)
        for capture in reversed(all_captures):
            if is_xbox_capture(capture):
                observed_identity = capture.get("id")
                xbox_like_identity_observed = True
                active_browser_capture = capture
                break
        if observed_identity is None:
            fallback = fallback_connected_capture(all_captures)
            if fallback is not None:
                observed_identity = fallback.get("id")
                active_browser_capture = fallback
        browser = browser_profile(active_browser_capture)
        standard_layout = classify_standard_layout(
            browser,
            scenario_results,
            xbox_like_identity_observed,
            expected_controls,
        )
        layout = layout_diagnosis(scenario_results)
        write_layout_diagnosis(run_dir, layout)

        scenario_passes = {
            result["scenario"]: bool(
                result["serial_report_connected"]
                and result["browser_changed_expected_surface"]
            )
            for result in scenario_results
            if result["scenario"] in scenario_expectations()
        }
        left_stick = any(
            scenario_passes.get(name, False)
            for name in ("left_stick_left", "left_stick_right", "left_stick_up", "left_stick_down")
        )
        right_stick = any(
            scenario_passes.get(name, False)
            for name in ("right_stick_left", "right_stick_right", "right_stick_up", "right_stick_down")
        )
        left_trigger = scenario_passes.get("left_trigger_max", False)
        right_trigger = scenario_passes.get("right_trigger_max", False)
        one_button = any(
            scenario_passes.get(name, False)
            for name in (
                "button_a",
                "button_b",
                "button_x",
                "button_y",
                "button_lb",
                "button_rb",
                "button_view",
                "button_menu",
                "button_left_stick_press",
                "button_right_stick_press",
                "button_nexus",
                "button_paddle_1",
                "button_paddle_2",
                "button_paddle_3",
                "button_share",
            )
        )
        success = bool(
            standard_layout["classification"]
            in ("standard_layout_pass", "identity_string_mismatch_only")
            and left_stick
            and right_stick
            and left_trigger
            and right_trigger
            and one_button
            and checker["returncode"] == 0
        )
        errors: list[str] = []
        if not observed_identity:
            errors.append("Chrome Gamepad API did not expose an Xbox-like controller")
        elif not xbox_like_identity_observed and not standard_layout["standard_mapping"]:
            errors.append(f"Chrome Gamepad API exposed non-Xbox identity: {observed_identity}")
        if standard_layout["classification"] == "standard_layout_partial":
            errors.append(
                "Chrome Gamepad API exposed a standard mapping but not all expected standard Xbox positions matched"
            )
        if checker["returncode"] != 0:
            errors.append("Xbox profile checker failed")
        for name, passed in {
            "left_stick": left_stick,
            "right_stick": right_stick,
            "left_trigger": left_trigger,
            "right_trigger": right_trigger,
            "one_button": one_button,
        }.items():
            if not passed:
                errors.append(f"missing browser-visible scenario coverage: {name}")

        scenario_results_file.write_text(
            json.dumps(scenario_results, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        summary = {
            "captured_at": stamp,
            "run_dir": str(run_dir),
            "commit_sha": command_output(["git", "rev-parse", "HEAD"]),
            "git_dirty": bool(command_output(["git", "status", "--short"])),
            "selected_port": port,
            "browser_url": browser_url,
            "browser_identity_observed": observed_identity,
            "browser_identity_matched_xbox": xbox_like_identity_observed,
            "browser_gamepad": browser,
            "standard_layout": standard_layout,
            "layout_diagnosis": {
                "path_json": str(run_dir / "layout_diagnosis.json"),
                "path_markdown": str(run_dir / "layout_diagnosis.md"),
                "unexpected_button_indices": layout["unexpected_button_indices"],
                "missing_expected_indices": layout["missing_expected_indices"],
            },
            "scenarios": scenarios,
            "diagnose_layout": args.diagnose_layout,
            "discover_layout": args.discover_layout,
            "expected_standard_layout": None if args.expected_standard_layout is None else str(args.expected_standard_layout),
            "no_live_bridge": args.no_live_bridge,
            "browser_capture_file": str(browser_copy) if browser_copy.exists() else None,
            "serial_transcript": str(transcript_file),
            "scenario_results": str(scenario_results_file),
            "reset_first": args.reset_first,
            "reset_result": reset_result,
            "server_output": server_lines,
            "arm_result": arm_result,
            "xbox_profile_checker": checker,
            "coverage": {
                "left_stick": left_stick,
                "right_stick": right_stick,
                "left_trigger": left_trigger,
                "right_trigger": right_trigger,
                "one_button": one_button,
            },
            "errors": errors,
            "xbox_host_visible_witness_passed": success,
            "claim_boundary": "macOS/Chrome host-visible Xbox-like BLE HID evidence only",
        }
        summary_file.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (run_dir / "operator_notes.md").write_text(
            "\n".join(
                [
                    "# Xbox Host-Visible Witness Notes",
                    "",
                    "This run publishes deterministic Xbox Report ID 1 diagnostic reports through the same BLE report path used by runtime input.",
                    "It does not claim Xbox console, proprietary Xbox Wireless, Windows, Android, iOS, Linux, or broad game compatibility.",
                    "",
                    f"- Serial port: `{port}`",
                    f"- Browser URL: `{browser_url}`",
                    f"- Browser identity observed: `{observed_identity}`",
                    f"- Passed: `{success}`",
                    f"- Summary: `{summary_file}`",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0 if success else 2
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
