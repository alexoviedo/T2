#!/usr/bin/env python3
"""Run deterministic virtual normalized-input live bridge witnesses."""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import tempfile
import time
from typing import Any

from asap_demo_rehearsal import (
    CommandRecord,
    SerialPort,
    find_latest_capture_file,
    parse_int_field,
    parse_semicolon_fields,
    print_record,
    start_witness_server,
    utc_stamp,
)
from configure_board import import_json, preset_config
from xbox_host_visible_witness import axis_values, button_values, changed_indices


DEFAULT_PORT = "/dev/cu.usbmodem5B5E0200881"
DEFAULT_WITNESS_PORT = 8790
DEFAULT_RESET_COMMAND = "espflash reset --chip esp32s3 --port {port} --non-interactive"

PERSONAS = {
    "generic": {
        "persona_id": "generic_gamepad",
        "preset": "flight-pack-generic",
        "device_name": "USB2BLE Gamepad",
        "mapping_command": "GET_GENERIC_GAMEPAD_MAPPING",
        "report_command": "GET_GENERIC_GAMEPAD_REPORT",
        "expected": {
            "stick_left": {"surface": "axis", "index": 0, "direction": "negative", "label": "A0 x"},
            "stick_right": {"surface": "axis", "index": 0, "direction": "positive", "label": "A0 x"},
            "stick_forward": {"surface": "axis", "index": 1, "direction": "negative", "label": "A1 y"},
            "stick_back": {"surface": "axis", "index": 1, "direction": "positive", "label": "A1 y"},
            "throttle_min": {"surface": "axis", "index": 2, "direction": "negative", "label": "A2 z"},
            "throttle_max": {"surface": "axis", "index": 2, "direction": "positive", "label": "A2 z"},
            "rudder_left": {"surface": "axis", "index": 3, "direction": "positive", "label": "A3 rx"},
            "rudder_right": {"surface": "axis", "index": 3, "direction": "negative", "label": "A3 rx"},
            "left_toe_released": {"surface": "axis", "index": 4, "direction": "negative", "label": "A4 ry"},
            "left_toe_pressed": {"surface": "axis", "index": 4, "direction": "positive", "label": "A4 ry"},
            "right_toe_released": {"surface": "axis", "index": 5, "direction": "negative", "label": "A5 rz"},
            "right_toe_pressed": {"surface": "axis", "index": 5, "direction": "positive", "label": "A5 rz"},
        },
    },
    "xbox": {
        "persona_id": "xbox_wireless_controller",
        "preset": "flight-pack-xbox",
        "device_name": "Xbox Wireless Controller",
        "mapping_command": "GET_XBOX_GAMEPAD_MAPPING",
        "report_command": "GET_XBOX_GAMEPAD_REPORT",
        "expected": {
            "stick_left": {"surface": "axis", "index": 0, "direction": "negative", "label": "A0 left_x"},
            "stick_right": {"surface": "axis", "index": 0, "direction": "positive", "label": "A0 left_x"},
            "stick_forward": {"surface": "axis", "index": 1, "direction": "negative", "label": "A1 left_y"},
            "stick_back": {"surface": "axis", "index": 1, "direction": "positive", "label": "A1 left_y"},
            "rudder_left": {"surface": "axis", "index": 2, "direction": "positive", "label": "A2 right_x"},
            "rudder_right": {"surface": "axis", "index": 2, "direction": "negative", "label": "A2 right_x"},
            "left_toe_pressed": {"surface": "button", "index": 6, "direction": "positive", "label": "B6 left_trigger"},
            "right_toe_pressed": {"surface": "button", "index": 7, "direction": "positive", "label": "B7 right_trigger"},
        },
    },
}

SCENARIO_SETS = {
    "generic": {
        "all": [
            "neutral",
            "throttle_max",
            "throttle_min",
            "rudder_left",
            "rudder_right",
            "left_toe_pressed",
            "left_toe_released",
            "right_toe_pressed",
            "right_toe_released",
            "stick_left",
            "stick_right",
            "stick_forward",
            "stick_back",
        ],
    },
    "xbox": {
        "all": [
            "neutral",
            "stick_left",
            "stick_right",
            "stick_forward",
            "stick_back",
            "rudder_left",
            "rudder_right",
            "left_toe_released",
            "left_toe_pressed",
            "right_toe_released",
            "right_toe_pressed",
        ],
    },
}

PAIRED_PREDECESSORS = {
    "generic": {
        "throttle_min": "throttle_max",
        "left_toe_released": "left_toe_pressed",
        "right_toe_released": "right_toe_pressed",
    },
}


def likely_ports() -> list[str]:
    paths = sorted(pathlib.Path("/dev").glob("cu.*")) + sorted(pathlib.Path("/dev").glob("tty.*"))
    return [
        str(path)
        for path in paths
        if any(token in path.name.lower() for token in ("usb", "wch", "modem", "serial"))
    ]


def select_port(requested: str | None, timeout: float) -> str:
    candidates = [requested] if requested else []
    if not candidates:
        preferred = pathlib.Path(DEFAULT_PORT)
        if preferred.exists():
            candidates.append(str(preferred))
        candidates.extend(port for port in likely_ports() if port not in candidates and "/cu." in port)
    for port in candidates:
        try:
            serial = SerialPort(port)
            try:
                responses = serial.command_response("GET_INFO", timeout)
            finally:
                serial.close()
        except OSError:
            continue
        if any(response.startswith("INFO:") for response in responses):
            return port
    raise SystemExit(f"No USB2BLE control-plane port responded. Candidates: {', '.join(candidates)}")


def send(serial: SerialPort, records: list[CommandRecord], command: str, timeout: float) -> CommandRecord:
    record = CommandRecord(command, serial.command_response(command, timeout))
    print_record(record)
    records.append(record)
    return record


def reset_board(port: str, reset_command: str) -> tuple[bool, str]:
    command = reset_command.format(port=port)
    result = subprocess.run(
        command,
        shell=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return result.returncode == 0, result.stdout.strip()


def response_with_prefix(records: list[CommandRecord], prefix: str) -> str | None:
    for record in reversed(records):
        for response in record.responses:
            if response.startswith(prefix):
                return response
    return None


def json_response(record: CommandRecord, prefix: str) -> dict[str, Any] | None:
    for response in record.responses:
        if response.startswith(prefix + ":"):
            try:
                value = json.loads(response.split(":", 1)[1])
            except json.JSONDecodeError:
                return None
            return value if isinstance(value, dict) else None
    return None


def status_field(record: CommandRecord, key: str) -> str | None:
    for response in record.responses:
        if response.startswith("STATUS:"):
            fields = parse_semicolon_fields(response)
            value = fields.get(key)
            return str(value) if value is not None else None
    return None


def status_persona(record: CommandRecord) -> str | None:
    return status_field(record, "persona")


def status_ble_connected(record: CommandRecord) -> bool:
    return status_field(record, "ble") == "Connected"


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


def latest_connected_capture(captures: list[dict[str, Any]]) -> dict[str, Any] | None:
    for capture in reversed(captures):
        if capture.get("connected") is True and str(capture.get("id", "")):
            return capture
    return None


def capture_matches_persona(capture: dict[str, Any] | None, persona: str) -> bool:
    if not capture or capture.get("connected") is not True:
        return False
    if capture.get("stale") is True or capture.get("expected_match") is False:
        return False
    mapping = str(capture.get("mapping", ""))
    gamepad_id = str(capture.get("id", ""))
    axes_count = len(capture.get("axes", []))
    buttons_count = len(capture.get("buttons", []))
    if persona == "generic":
        return mapping == "" and axes_count >= 6 and "STANDARD GAMEPAD" not in gamepad_id
    if persona == "xbox":
        return mapping == "standard" and axes_count >= 4 and buttons_count >= 8
    return True


def latest_usable_capture(
    captures: list[dict[str, Any]],
    persona: str,
    min_sample_seq: int | None = None,
) -> dict[str, Any] | None:
    for capture in reversed(captures):
        if min_sample_seq is not None:
            try:
                sample_seq = int(capture.get("sample_seq", 0))
            except (TypeError, ValueError):
                sample_seq = 0
            if sample_seq <= min_sample_seq:
                continue
        if capture_matches_persona(capture, persona):
            return capture
    return None


def stale_capture_count(captures: list[dict[str, Any]]) -> int:
    return sum(1 for capture in captures if capture.get("stale") is True or capture.get("type") in {"stale", "stale_connected"})


def wait_for_capture(
    capture_dir: pathlib.Path,
    capture_file: pathlib.Path | None,
    timeout: float,
    persona: str,
    min_sample_seq: int | None = None,
) -> tuple[pathlib.Path | None, dict[str, Any] | None]:
    deadline = time.monotonic() + timeout
    current = capture_file
    while time.monotonic() < deadline:
        if current is None:
            current = find_latest_capture_file(capture_dir)
        capture = latest_usable_capture(load_captures(current), persona, min_sample_seq)
        if capture is not None:
            return current, capture
        time.sleep(0.2)
    return current, latest_usable_capture(load_captures(current), persona, min_sample_seq)


def try_arm_chrome() -> None:
    if sys.platform != "darwin":
        return
    script = (
        'tell application "Google Chrome"\n'
        "  activate\n"
        '  tell active tab of front window to execute javascript "document.querySelector(\\"#armButton\\")?.click()"\n'
        "end tell\n"
    )
    subprocess.run(["osascript", "-e", script], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def witness_url(port: int, persona: str, session_label: str, browser_url: str | None = None) -> str:
    if browser_url:
        return browser_url
    if persona == "generic":
        expected_mapping = "none"
        expected_id = "Vendor: 303a"
    else:
        expected_mapping = "standard"
        expected_id = ""
    params = {
        "autostart": "1",
        "autoArm": "1",
        "expectedPersona": persona,
        "expectedMapping": expected_mapping,
        "rejectStale": "1",
        "sessionLabel": session_label,
        "captureMode": "continuous",
        "continuousEveryMs": "150",
    }
    if expected_id:
        params["expectedIdContains"] = expected_id
    query = "&".join(f"{key}={value.replace(' ', '%20').replace(':', '%3A')}" for key, value in params.items())
    return f"http://127.0.0.1:{port}/?{query}"


def open_witness_browser(
    port: int,
    persona: str,
    session_label: str,
    browser_url: str | None,
    chrome_mode: str,
    chrome_app: str,
) -> dict[str, Any]:
    url = witness_url(port, persona, session_label, browser_url)
    if sys.platform == "darwin":
        if chrome_mode == "temp-profile":
            temp_profile = tempfile.mkdtemp(prefix="usb2ble-virtual-bridge-chrome-")
            command = [
                "open",
                "-na",
                chrome_app,
                "--args",
                f"--user-data-dir={temp_profile}",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-background-timer-throttling",
                "--disable-renderer-backgrounding",
                "--disable-backgrounding-occluded-windows",
                url,
            ]
        else:
            temp_profile = None
            command = ["open", "-a", chrome_app, url]
        result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        return {
            "url": url,
            "chrome_mode": chrome_mode,
            "chrome_app": chrome_app,
            "command": command,
            "ok": result.returncode == 0,
            "output": result.stdout,
            "temp_profile": temp_profile,
        }
    else:
        print(f"Open browser witness: {url}")
        return {
            "url": url,
            "chrome_mode": "manual",
            "chrome_app": chrome_app,
            "command": None,
            "ok": True,
            "output": "",
            "temp_profile": None,
        }


def browser_capture_seen(captures: list[dict[str, Any]]) -> bool:
    return latest_connected_capture(captures) is not None


def scenario_names(persona: str, value: str) -> list[str]:
    if value in SCENARIO_SETS[persona]:
        return list(SCENARIO_SETS[persona][value])
    names = [part.strip() for part in value.split(",") if part.strip()]
    known = set(SCENARIO_SETS[persona]["all"])
    unknown = [name for name in names if name not in known]
    if unknown:
        raise SystemExit(f"Unknown scenario(s): {', '.join(unknown)}")
    return names


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


def value_matches_direction(value: float, direction: str, threshold: float = 0.5) -> bool:
    if direction == "positive":
        return value > threshold
    if direction == "negative":
        return value < -threshold
    if direction == "any":
        return abs(value) > threshold
    return False


def pair_predecessor(persona: str, scenario: str) -> str | None:
    return PAIRED_PREDECESSORS.get(persona, {}).get(scenario)


def should_reset_to_neutral(persona: str, scenario: str, previous_scenario: str | None) -> bool:
    if scenario == "neutral":
        return False
    predecessor = pair_predecessor(persona, scenario)
    return predecessor is None or previous_scenario != predecessor


def axis_or_button_values(capture: dict[str, Any] | None, surface: str) -> list[float]:
    if surface == "axis":
        return axis_values(capture)
    return button_values(capture)


def endpoint_value(capture: dict[str, Any] | None, surface: str, index: int) -> float | None:
    values = axis_or_button_values(capture, surface)
    if index < len(values):
        try:
            return float(values[index])
        except (TypeError, ValueError):
            return None
    return None


def movement_matches_direction(before: float | None, after: float | None, direction: str, threshold: float) -> bool:
    if before is None or after is None:
        return False
    delta = after - before
    if direction == "positive":
        return delta > threshold
    if direction == "negative":
        return delta < -threshold
    if direction == "any":
        return abs(delta) > threshold
    return False


def evaluate_expected(
    scenario: str,
    expected: dict[str, dict[str, Any]],
    axis_changes: list[dict[str, Any]],
    button_changes: list[dict[str, Any]],
    after_capture: dict[str, Any] | None = None,
    before_capture: dict[str, Any] | None = None,
    paired_predecessor: str | None = None,
    threshold: float = 0.2,
) -> dict[str, Any]:
    control = expected.get(scenario)
    if control is None:
        return {
            "expected": None,
            "matched": None,
            "observed_change": None,
            "observed_value": None,
            "raw_result": {"status": "not_applicable", "matched": None},
            "semantic_result": {"status": "not_applicable", "matched": None},
        }
    changes = axis_changes if control["surface"] == "axis" else button_changes
    observed = find_change(changes, int(control["index"]), str(control["direction"]))
    raw_observed = observed
    observed_value = None
    before_value = endpoint_value(before_capture, str(control["surface"]), int(control["index"]))
    after_value = endpoint_value(after_capture, str(control["surface"]), int(control["index"]))
    if observed is None and after_capture is not None:
        values = axis_values(after_capture) if control["surface"] == "axis" else button_values(after_capture)
        index = int(control["index"])
        if index < len(values):
            observed_value = values[index]
            if value_matches_direction(float(observed_value), str(control["direction"])):
                observed = {
                    "index": index,
                    "before": None,
                    "after": observed_value,
                    "delta": None,
                    "mode": "held_value",
                }
    raw_matched = raw_observed is not None
    raw_status = "pass" if raw_matched else "fail"
    semantic_status = raw_status
    semantic_reason = "raw_delta_or_held_value"
    semantic_matched = raw_matched
    semantic_observed = observed
    if not raw_matched:
        direction = str(control["direction"])
        if observed is not None and paired_predecessor is None:
            semantic_matched = True
            semantic_status = "pass"
            semantic_reason = "held_value"
            semantic_observed = observed
        elif movement_matches_direction(before_value, after_value, direction, threshold):
            semantic_matched = True
            semantic_status = "pass"
            semantic_reason = "paired_endpoint_transition" if paired_predecessor else "direct_transition"
            semantic_observed = {
                "index": int(control["index"]),
                "before": before_value,
                "after": after_value,
                "delta": None if before_value is None or after_value is None else after_value - before_value,
                "mode": semantic_reason,
            }
        elif paired_predecessor and before_value is not None and after_value is not None:
            if abs(after_value - before_value) <= threshold:
                semantic_status = "inconclusive"
                semantic_reason = "already_at_or_near_endpoint"
            elif value_matches_direction(after_value, direction, threshold):
                semantic_matched = True
                semantic_status = "pass"
                semantic_reason = "paired_endpoint_value"
                semantic_observed = {
                    "index": int(control["index"]),
                    "before": before_value,
                    "after": after_value,
                    "delta": after_value - before_value,
                    "mode": semantic_reason,
                }
        elif paired_predecessor and before_value is not None and after_value is not None and abs(after_value - before_value) <= threshold:
            semantic_status = "inconclusive"
            semantic_reason = "no_meaningful_movement"
    return {
        "expected": control,
        "matched": semantic_matched,
        "observed_change": observed,
        "observed_value": observed_value if observed_value is not None else after_value,
        "before_value": before_value,
        "after_value": after_value,
        "paired_predecessor": paired_predecessor,
        "raw_result": {
            "status": raw_status,
            "matched": raw_matched,
            "observed_change": raw_observed,
            "observed_value": observed_value if observed_value is not None else after_value,
        },
        "semantic_result": {
            "status": semantic_status,
            "matched": semantic_matched,
            "reason": semantic_reason,
            "observed_change": semantic_observed,
            "before_value": before_value,
            "after_value": after_value,
        },
    }


def summarize_expected_results(scenario_results: list[dict[str, Any]]) -> dict[str, Any]:
    expected_results = [
        (result["scenario"], result["expected_result"])
        for result in scenario_results
        if (result.get("expected_result") or {}).get("expected") is not None
    ]
    matched = [result for _, result in expected_results if result.get("matched")]
    failed = [scenario for scenario, result in expected_results if not result.get("matched")]
    inconclusive = [
        scenario
        for scenario, result in expected_results
        if (result.get("semantic_result") or {}).get("status") == "inconclusive"
    ]
    raw_failed = [
        scenario
        for scenario, result in expected_results
        if not (result.get("raw_result") or {}).get("matched")
    ]
    return {
        "expected_count": len(expected_results),
        "matched_expected_count": len(matched),
        "failed_expected_scenarios": failed,
        "raw_failed_expected_scenarios": raw_failed,
        "inconclusive_expected_scenarios": inconclusive,
    }


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
    parser.add_argument("--persona", choices=sorted(PERSONAS), required=True)
    parser.add_argument(
        "--variant",
        default="generic_default",
        help="Compatibility variant for --persona generic (default: generic_default).",
    )
    parser.add_argument("--scenarios", default="all")
    parser.add_argument("--duration-per-scenario", type=float, default=0.8)
    parser.add_argument("--timeout", type=float, default=4.0)
    parser.add_argument("--browser-timeout", type=float, default=12.0)
    parser.add_argument("--wait-for-browser-seconds", type=float, dest="browser_timeout")
    parser.add_argument("--witness-port", type=int, default=DEFAULT_WITNESS_PORT)
    parser.add_argument("--out-dir", type=pathlib.Path, default=pathlib.Path("target/virtual-input-bridge-witness"))
    parser.add_argument("--run-prefix", help="Artifact directory prefix; defaults to '<persona>_virtual_bridge'")
    parser.add_argument("--reset-command", default=DEFAULT_RESET_COMMAND)
    parser.add_argument("--no-reset-on-persona-mismatch", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--assume-connected", action="store_true")
    parser.add_argument("--assume-bluetooth-connected", action="store_true", dest="assume_connected")
    parser.add_argument("--auto-arm", action="store_true", default=True)
    parser.add_argument("--no-auto-arm", action="store_false", dest="auto_arm")
    parser.add_argument("--no-human", action="store_true")
    parser.add_argument("--reuse-browser", action="store_true")
    parser.add_argument("--browser-url")
    parser.add_argument("--no-open", action="store_true")
    parser.add_argument("--manual-arm", action="store_true")
    parser.add_argument("--no-physical-input", action="store_true")
    parser.add_argument(
        "--chrome-mode",
        choices=["existing-profile", "temp-profile"],
        default="existing-profile",
        help="Browser launch mode. temp-profile avoids stale Chrome Gamepad API session/cache state.",
    )
    parser.add_argument("--chrome-app", default="Google Chrome")
    parser.add_argument(
        "--browser-wake-self-test",
        action="store_true",
        help="Publish a diagnostic BLE self-test report before browser capture to wake Gamepad API exposure.",
    )
    args = parser.parse_args()

    persona_spec = PERSONAS[args.persona]
    scenarios = scenario_names(args.persona, args.scenarios)
    stamp = utc_stamp()
    variant_safe = args.variant.replace("/", "_").replace(" ", "_")
    session_label = f"{args.persona}-{variant_safe}-{stamp}"
    run_prefix = args.run_prefix or (
        f"{args.persona}_{variant_safe}_virtual_bridge"
        if args.persona == "generic" and args.variant != "generic_default"
        else f"{args.persona}_virtual_bridge"
    )
    run_dir = args.out_dir / f"{run_prefix}_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    capture_dir = run_dir / "gamepad-witness"
    port = select_port(args.port, args.timeout)

    records: list[CommandRecord] = []
    scenario_results: list[dict[str, Any]] = []
    reset_records: list[dict[str, Any]] = []
    human_prompted = False
    auto_arm_attempted = False
    browser_wake_self_test_sent = False
    browser_launch: dict[str, Any] | None = None
    target_ble_connected = False
    server = None
    server_lines: list[str] = []
    capture_file: pathlib.Path | None = None

    if not args.no_browser:
        server, server_lines, capture_file = start_witness_server(args.witness_port, capture_dir)
        if not args.no_open and not args.reuse_browser:
            browser_launch = open_witness_browser(
                args.witness_port,
                args.persona,
                session_label,
                args.browser_url,
                args.chrome_mode,
                args.chrome_app,
            )
            time.sleep(1.0)
            if args.auto_arm:
                auto_arm_attempted = True
                try_arm_chrome()

    def open_serial() -> SerialPort:
        return SerialPort(port)

    serial = open_serial()
    try:
        send(serial, records, "GET_INFO", args.timeout)
        status = send(serial, records, "GET_STATUS", args.timeout)
        active_persona = status_persona(status)
        if (
            active_persona
            and active_persona not in {"none", str(persona_spec["persona_id"])}
            and not args.no_reset_on_persona_mismatch
        ):
            send(serial, records, "STOP_BRIDGE", args.timeout)
            send(serial, records, "STOP_VIRTUAL_INPUT", args.timeout)
            serial.close()
            ok, output = reset_board(port, args.reset_command)
            reset_records.append(
                {
                    "reason": "persona_mismatch",
                    "previous_persona": active_persona,
                    "requested_persona": persona_spec["persona_id"],
                    "command": args.reset_command.format(port=port),
                    "ok": ok,
                    "output": output,
                }
            )
            if not ok:
                raise SystemExit(f"Reset command failed before persona switch:\n{output}")
            time.sleep(4.0)
            serial = open_serial()
            send(serial, records, "GET_INFO", args.timeout)
            send(serial, records, "GET_STATUS", args.timeout)
        import_json(
            serial,
            records,
            json.dumps(preset_config(str(persona_spec["preset"])), separators=(",", ":")).encode("utf-8"),
            args.timeout,
        )
        send(serial, records, "GET_CONFIG_STATUS", args.timeout)
        if args.persona == "generic" and args.variant != "generic_default":
            start_command = f"START_BLE_GENERIC_GAMEPAD_VARIANT {args.variant}"
        else:
            start_command = "START_CONFIGURED"
        start_configured = send(serial, records, start_command, args.timeout)
        if any(response == "ERROR:PersonaAlreadyActive" for response in start_configured.responses):
            already_active_status = send(serial, records, "GET_STATUS", args.timeout)
            can_reuse_active_persona = (
                status_persona(already_active_status) == str(persona_spec["persona_id"])
                and not (args.persona == "generic" and args.variant != "generic_default")
            )
            if can_reuse_active_persona:
                reset_records.append(
                    {
                        "reason": "persona_already_active_reused",
                        "requested_persona": persona_spec["persona_id"],
                        "ok": True,
                        "output": "matching persona was already active; reused existing BLE connection",
                    }
                )
                start_configured = CommandRecord(
                    start_command,
                    [
                        "CONFIG_ACTION:action=start_configured;state=already_active_reused;"
                        f"detail=persona={persona_spec['persona_id']};bridge=false;;"
                    ],
                )
                print_record(start_configured)
                records.append(start_configured)
            else:
                serial.close()
                ok, output = reset_board(port, args.reset_command)
                reset_records.append(
                    {
                        "reason": "persona_already_active",
                        "requested_persona": persona_spec["persona_id"],
                        "command": args.reset_command.format(port=port),
                        "ok": ok,
                        "output": output,
                    }
                )
                if not ok:
                    raise SystemExit(f"Reset command failed after PersonaAlreadyActive:\n{output}")
                time.sleep(4.0)
                serial = open_serial()
                send(serial, records, "GET_INFO", args.timeout)
                send(serial, records, "GET_STATUS", args.timeout)
                import_json(
                    serial,
                    records,
                    json.dumps(preset_config(str(persona_spec["preset"])), separators=(",", ":")).encode("utf-8"),
                    args.timeout,
                )
                send(serial, records, "GET_CONFIG_STATUS", args.timeout)
                start_configured = send(serial, records, start_command, args.timeout)
        if any(response.startswith("ERROR:") for response in start_configured.responses):
            raise SystemExit(f"{start_command} failed: " + "; ".join(start_configured.responses))
        send(serial, records, "GET_BLE_COMPAT_PROFILE", args.timeout)
        send(serial, records, "START_VIRTUAL_INPUT", args.timeout)
        send(serial, records, "PUBLISH_VIRTUAL_INPUT_FRAME neutral", args.timeout)
        send(serial, records, "GET_VIRTUAL_INPUT_STATUS", args.timeout)
        send(serial, records, "START_BRIDGE", args.timeout)
        bridge_started = send(serial, records, "GET_BRIDGE_STATUS", args.timeout)
        current_status = send(serial, records, "GET_STATUS", args.timeout)
        target_ble_connected = status_ble_connected(current_status)
        if args.browser_wake_self_test and target_ble_connected:
            wake_command = "SEND_XBOX_SELF_TEST_REPORT" if args.persona == "xbox" else "SEND_BLE_SELF_TEST_REPORT"
            send(serial, records, wake_command, args.timeout)
            time.sleep(0.25)
            send(serial, records, wake_command, args.timeout)
            time.sleep(0.5)
            browser_wake_self_test_sent = True

        browser_gamepad = None
        if not args.no_browser:
            capture_file, browser_gamepad = wait_for_capture(capture_dir, capture_file, args.browser_timeout, args.persona)
            if browser_gamepad is None and args.auto_arm:
                auto_arm_attempted = True
                try_arm_chrome()
                capture_file, browser_gamepad = wait_for_capture(
                    capture_dir, capture_file, min(args.browser_timeout, 4.0), args.persona
                )
            if browser_gamepad is None and args.manual_arm and not args.no_human:
                human_prompted = True
                print()
                print("Click Arm in the browser Gamepad witness page, then press Enter here.")
                input()
                capture_file, browser_gamepad = wait_for_capture(capture_dir, capture_file, args.browser_timeout, args.persona)
            if (
                browser_gamepad is None
                and not args.assume_connected
                and not target_ble_connected
                and not args.no_human
            ):
                human_prompted = True
                print()
                print(
                    f'Open macOS Bluetooth settings and connect "{persona_spec["device_name"]}", then press Enter.'
                )
                if sys.stdin.isatty():
                    input()
                else:
                    print("No interactive stdin available; continuing after a short pause.")
                    time.sleep(2.0)
                if args.auto_arm:
                    auto_arm_attempted = True
                    try_arm_chrome()
                capture_file, browser_gamepad = wait_for_capture(capture_dir, capture_file, args.browser_timeout, args.persona)

        previous_capture = browser_gamepad
        previous_scenario = None
        for scenario in scenarios:
            reset_before_scenario = should_reset_to_neutral(args.persona, scenario, previous_scenario)
            if reset_before_scenario:
                send(serial, records, "PUBLISH_VIRTUAL_INPUT_FRAME neutral", args.timeout)
                time.sleep(args.duration_per_scenario)
                if not args.no_browser:
                    previous_capture = latest_usable_capture(load_captures(capture_file), args.persona) or previous_capture

            min_sample_seq = None
            if isinstance(previous_capture, dict):
                try:
                    min_sample_seq = int(previous_capture.get("sample_seq", 0))
                except (TypeError, ValueError):
                    min_sample_seq = None

            send(serial, records, f"PUBLISH_VIRTUAL_INPUT_FRAME {scenario}", args.timeout)
            time.sleep(args.duration_per_scenario)
            status = send(serial, records, "GET_VIRTUAL_INPUT_STATUS", args.timeout)
            mapping = send(serial, records, str(persona_spec["mapping_command"]), args.timeout)
            report = send(serial, records, str(persona_spec["report_command"]), args.timeout)
            bridge = send(serial, records, "GET_BRIDGE_STATUS", args.timeout)

            after_capture = None
            axis_changes: list[dict[str, Any]] = []
            button_changes: list[dict[str, Any]] = []
            if not args.no_browser:
                capture_file, after_capture = wait_for_capture(
                    capture_dir,
                    capture_file,
                    min(args.browser_timeout, 3.0),
                    args.persona,
                    min_sample_seq,
                )
                axis_changes = changed_indices(axis_values(previous_capture), axis_values(after_capture), 0.05)
                button_changes = changed_indices(button_values(previous_capture), button_values(after_capture), 0.05)

            scenario_results.append(
                {
                    "scenario": scenario,
                    "reset_before_scenario": reset_before_scenario,
                    "paired_predecessor": pair_predecessor(args.persona, scenario),
                    "virtual_status": json_response(status, "VIRTUAL_INPUT_STATUS_JSON"),
                    "mapping_response": mapping.responses,
                    "report_response": report.responses,
                    "bridge_status": parse_semicolon_fields(response_with_prefix([bridge], "BRIDGE_STATUS:")),
                    "browser_before": previous_capture,
                    "browser_after": after_capture,
                    "changed_axis_indices": axis_changes,
                    "changed_button_indices": button_changes,
                    "expected_result": None
                    if args.no_browser
                    else evaluate_expected(
                        scenario,
                        dict(persona_spec["expected"]),
                        axis_changes,
                        button_changes,
                        after_capture,
                        previous_capture,
                        pair_predecessor(args.persona, scenario),
                    ),
                }
            )
            if not args.no_browser:
                previous_capture = after_capture
            previous_scenario = scenario

        stop_records = [
            send(serial, records, "GET_BRIDGE_STATUS", args.timeout),
            send(serial, records, "STOP_BRIDGE", args.timeout),
            send(serial, records, "STOP_VIRTUAL_INPUT", args.timeout),
            send(serial, records, "GET_VIRTUAL_INPUT_STATUS", args.timeout),
        ]
    finally:
        serial.close()
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                server.kill()

    bridge_statuses = [
        result["bridge_status"]
        for result in scenario_results
        if isinstance(result.get("bridge_status"), dict)
    ]
    published_values = [
        value
        for fields in bridge_statuses
        for value in [parse_int_field(fields, "published")]
        if value is not None
    ]
    published_delta = published_values[-1] - published_values[0] if len(published_values) >= 2 else 0
    expected_summary = summarize_expected_results(scenario_results)

    captures = load_captures(capture_file)
    latest_browser_gamepad = latest_usable_capture(captures, args.persona)
    if browser_gamepad is None:
        browser_gamepad = latest_browser_gamepad
    target_errors = [
        response
        for record in records
        for response in record.responses
        if response.startswith("ERROR:")
    ]
    target_only_passed = args.no_browser and published_delta > 0 and not target_errors
    summary = {
        "captured_at": stamp,
        "port": port,
        "persona": args.persona,
        "variant": args.variant if args.persona == "generic" else "n/a",
        "persona_id": persona_spec["persona_id"],
        "run_dir": str(run_dir),
        "capture_file": str(capture_file) if capture_file else None,
        "browser_session_label": session_label,
        "browser_gamepad": browser_gamepad,
        "latest_browser_gamepad": latest_browser_gamepad,
        "browser_capture_count": len(captures),
        "browser_stale_capture_count": stale_capture_count(captures),
        "browser_gamepad_seen": browser_capture_seen(captures),
        "browser_expected_gamepad_seen": latest_browser_gamepad is not None,
        "target_ble_connected": target_ble_connected,
        "human_prompted": human_prompted,
        "auto_arm_attempted": auto_arm_attempted,
        "browser_wake_self_test_sent": browser_wake_self_test_sent,
        "browser_launch": browser_launch,
        "browser_url": witness_url(args.witness_port, args.persona, session_label, args.browser_url),
        "scenarios": scenarios,
        "expected_count": expected_summary["expected_count"],
        "matched_expected_count": expected_summary["matched_expected_count"],
        "failed_expected_scenarios": expected_summary["failed_expected_scenarios"],
        "raw_failed_expected_scenarios": expected_summary["raw_failed_expected_scenarios"],
        "inconclusive_expected_scenarios": expected_summary["inconclusive_expected_scenarios"],
        "published_delta": published_delta,
        "target_only_passed": target_only_passed,
        "target_errors": target_errors,
        "reset_records": reset_records,
        "virtual_bridge_witness_passed": bool(
            target_only_passed
            or (
                published_delta > 0
                and expected_summary["expected_count"] > 0
                and expected_summary["matched_expected_count"] == expected_summary["expected_count"]
                and browser_gamepad is not None
            )
        ),
        "no_browser": args.no_browser,
        "no_human": args.no_human,
        "no_physical_input": args.no_physical_input,
        "reuse_browser": args.reuse_browser,
        "server_output": server_lines,
        "stop_records": [record.to_json() for record in stop_records],
    }

    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (run_dir / "scenario_results.json").write_text(
        json.dumps(scenario_results, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (run_dir / "transcript.json").write_text(
        json.dumps([record.to_json() for record in records], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_transcript(run_dir / "serial_transcript.txt", records)
    notes = [
        "# Virtual Input Bridge Witness Notes",
        "",
        f"- Persona: `{args.persona}`",
        f"- Port: `{port}`",
        f"- Browser capture file: `{capture_file}`",
        f"- Published delta: `{published_delta}`",
        f"- Expected controls matched: `{expected_summary['matched_expected_count']}/{expected_summary['expected_count']}`",
        f"- Passed: `{summary['virtual_bridge_witness_passed']}`",
        "",
        "This witness uses diagnostic virtual normalized-input replay, not physical USB movement.",
    ]
    (run_dir / "operator_notes.md").write_text("\n".join(notes) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["virtual_bridge_witness_passed"] or args.no_browser else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        raise SystemExit(130)
