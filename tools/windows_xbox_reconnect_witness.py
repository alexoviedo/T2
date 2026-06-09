#!/usr/bin/env python3
"""Capture Windows Xbox BLE reconnect diagnostics without physical input.

This helper is intentionally conservative. It can prepare the USB2BLE Xbox
persona, attempt WinRT pairing, sample Windows XInput, run deterministic Xbox
test reports, and exercise software-reset reconnect behavior. It does not ask
for or require HOTAS/pedal movement.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import subprocess
import sys
import time
from typing import Any

import windows_ble_advertising_watcher as ble_watcher
import windows_bluetooth_pairing_witness as pairing_witness
import windows_ble_cache_witness as cache_witness
from serial_command import SerialPort
from windows_gamepad_probe import collect_pnp_inventory, collect_raw_input_devices, collect_xinput_slots


DEFAULT_OUT_DIR = pathlib.Path("target/windows-xbox-reconnect")
DEFAULT_RESET_COMMAND = "espflash reset --chip esp32s3 --port {port} --non-interactive"
XBOX_DEVICE_NAME = "Xbox Wireless Controller"
XBOX_ADDRESS = "CB:B3:AE:FA:FC:EF"
TOPOLOGY_IDS = {("2109", "2813"), ("044f", "b10a"), ("044f", "b687")}
TARGET_DIAGNOSTIC_COMMANDS = [
    "GET_STATUS",
    "GET_BLE_IDENTITY_INFO",
    "GET_BLE_CONNECTION_INFO",
    "GET_BLE_BOND_INFO",
    "GET_BLE_ADVERTISING_INFO",
    "GET_BLE_COMPAT_PROFILE",
    "GET_BRIDGE_STATUS",
    "GET_BLE_ADVERTISING_EVENTS",
    "GET_CONFIG_STATUS",
]
XINPUT_SANITY_SCENARIOS = [
    "neutral",
    "left_stick_right",
    "left_trigger_max",
    "right_trigger_max",
    "button_a",
]


def utc_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def run_command(command: list[str], timeout: float = 30.0, shell: bool = False) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command if not shell else " ".join(command),
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        return {"command": command, "returncode": None, "output": str(exc), "ok": False}
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "returncode": None,
            "output": exc.stdout or "",
            "ok": False,
            "timeout": True,
        }
    return {"command": command, "returncode": result.returncode, "output": result.stdout, "ok": result.returncode == 0}


def write_json(path: pathlib.Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_kv_payload(line: str) -> dict[str, str]:
    if ":" not in line:
        return {}
    payload = line.split(":", 1)[1]
    fields: dict[str, str] = {}
    for part in payload.split(";"):
        if not part or "=" not in part:
            continue
        key, value = part.split("=", 1)
        fields[key] = value
    return fields


def json_payload(line: str) -> dict[str, Any] | None:
    if ":" not in line:
        return None
    try:
        value = json.loads(line.split(":", 1)[1])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def command_record(command: str, responses: list[str]) -> dict[str, Any]:
    return {
        "at": iso_now(),
        "command": command,
        "responses": responses,
        "ok": bool(responses) and not any(response.startswith("ERROR:") for response in responses),
    }


def send(serial: SerialPort, command: str, timeout: float, transcript: list[dict[str, Any]]) -> dict[str, Any]:
    responses = serial.command_response(command, timeout)
    record = command_record(command, responses)
    transcript.append(record)
    print(f">> {command}")
    for response in responses or ["<no matching response>"]:
        print(response)
    return record


def powershell_json(script: str, timeout: float = 20.0) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    result = run_command(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ],
        timeout=timeout,
    )
    text = str(result.get("output", "")).strip()
    if not text:
        return [], result
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        result["json_error"] = "could not parse PowerShell JSON output"
        return [], result
    if isinstance(parsed, dict):
        return [parsed], result
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)], result
    return [], result


def serial_ports() -> dict[str, Any]:
    names_command = run_command(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            "[System.IO.Ports.SerialPort]::GetPortNames() | ConvertTo-Json",
        ],
        timeout=20.0,
    )
    names_text: list[str] = []
    text = str(names_command.get("output", "")).strip()
    if text:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = text.splitlines()
        if isinstance(parsed, str):
            names_text = [parsed]
        elif isinstance(parsed, list):
            names_text = [str(item) for item in parsed]
    devices, devices_command = powershell_json(
        "Get-CimInstance Win32_SerialPort | Select-Object DeviceID,Name,Description,PNPDeviceID,Manufacturer | ConvertTo-Json -Depth 5"
    )
    return {"port_names": sorted(set(names_text)), "devices": devices, "commands": [names_command, devices_command]}


def probe_port(port: str, timeout: float) -> dict[str, Any]:
    transcript: list[dict[str, Any]] = []
    try:
        serial = SerialPort(port)
    except Exception as exc:
        return {"port": port, "ok": False, "error": repr(exc), "transcript": transcript}
    try:
        send(serial, "GET_INFO", timeout, transcript)
        send(serial, "GET_STATUS", timeout, transcript)
    finally:
        serial.close()
    ok = any(response.startswith("INFO:") for record in transcript for response in record["responses"])
    return {"port": port, "ok": ok, "transcript": transcript}


def select_port(requested: str, timeout: float, discovery: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    if requested.lower() != "auto":
        return requested, [probe_port(requested, timeout)]
    probes = [probe_port(port, timeout) for port in discovery.get("port_names", [])]
    for probe in probes:
        if probe.get("ok"):
            return str(probe["port"]), probes
    raise RuntimeError("could not autodetect a USB2BLE serial port")


def collect_target_diagnostics(serial: SerialPort, timeout: float, transcript: list[dict[str, Any]]) -> dict[str, Any]:
    records = [send(serial, command, timeout, transcript) for command in TARGET_DIAGNOSTIC_COMMANDS]
    parsed: dict[str, Any] = {}
    for record in records:
        for response in record["responses"]:
            prefix = response.split(":", 1)[0]
            if response.endswith("}") and "_JSON:" in response:
                parsed[prefix] = json_payload(response)
            else:
                parsed[prefix] = parse_kv_payload(response)
    return {"records": records, "parsed": parsed}


def usb_topology_present(serial: SerialPort, timeout: float, transcript: list[dict[str, Any]]) -> dict[str, Any]:
    records = [send(serial, "GET_USB_STATUS", timeout, transcript), send(serial, "LIST_USB_DEVICES", timeout, transcript)]
    devices: list[dict[str, str]] = []
    for response in records[-1]["responses"]:
        if not response.startswith("USB_DEVICES:"):
            continue
        payload = response.split(":", 1)[1]
        for item in payload.split("|"):
            fields = {}
            for part in item.split(","):
                if "=" in part:
                    key, value = part.split("=", 1)
                    fields[key] = value
            if fields:
                devices.append(fields)
    observed = {(device.get("vid", "").lower(), device.get("pid", "").lower()) for device in devices}
    return {"records": records, "devices": devices, "expected_present": TOPOLOGY_IDS <= observed}


def collect_windows_state() -> dict[str, Any]:
    return {
        "captured_at": iso_now(),
        "pnp": collect_pnp_inventory(),
        "raw_input": collect_raw_input_devices(),
        "xinput": collect_xinput_slots(),
    }


def xinput_slot(xinput: dict[str, Any], slot_index: int = 0) -> dict[str, Any] | None:
    for slot in xinput.get("slots", []):
        if isinstance(slot, dict) and slot.get("slot") == slot_index:
            return slot
    return None


def slot_connected(slot: dict[str, Any] | None) -> bool:
    return isinstance(slot, dict) and slot.get("connected") is True


def summarize_xinput_samples(samples: list[dict[str, Any]]) -> dict[str, Any]:
    slots = [sample.get("slot0") for sample in samples if isinstance(sample.get("slot0"), dict)]
    connected = [slot for slot in slots if slot.get("connected") is True]
    if not connected:
        return {"sample_count": len(samples), "connected_count": 0, "slot0_connected": False}
    return {
        "sample_count": len(samples),
        "connected_count": len(connected),
        "slot0_connected": True,
        "left_thumb_x_min": min(int(slot.get("left_thumb", [0, 0])[0]) for slot in connected),
        "left_thumb_x_max": max(int(slot.get("left_thumb", [0, 0])[0]) for slot in connected),
        "right_thumb_x_min": min(int(slot.get("right_thumb", [0, 0])[0]) for slot in connected),
        "right_thumb_x_max": max(int(slot.get("right_thumb", [0, 0])[0]) for slot in connected),
        "left_trigger_max": max(int(slot.get("left_trigger", 0)) for slot in connected),
        "right_trigger_max": max(int(slot.get("right_trigger", 0)) for slot in connected),
        "buttons_observed": sorted({int(slot.get("buttons", 0)) for slot in connected}),
    }


def scenario_passed(scenario: str, samples: list[dict[str, Any]]) -> bool:
    slots = [sample.get("slot0") for sample in samples if isinstance(sample.get("slot0"), dict)]
    connected = [slot for slot in slots if slot.get("connected") is True]
    if not connected:
        return False
    if scenario == "neutral":
        return True
    if scenario == "left_stick_right":
        return max(int(slot.get("left_thumb", [0, 0])[0]) for slot in connected) > 10000
    if scenario == "left_trigger_max":
        return max(int(slot.get("left_trigger", 0)) for slot in connected) >= 200
    if scenario == "right_trigger_max":
        return max(int(slot.get("right_trigger", 0)) for slot in connected) >= 200
    if scenario == "button_a":
        return any((int(slot.get("buttons", 0)) & 0x1000) != 0 for slot in connected)
    return False


def sample_xinput(samples_file: pathlib.Path, scenario: str, phase: str, started: float) -> dict[str, Any]:
    xinput = collect_xinput_slots()
    sample = {
        "at": iso_now(),
        "elapsed_s": round(time.monotonic() - started, 3),
        "scenario": scenario,
        "phase": phase,
        "xinput": xinput,
        "slot0": xinput_slot(xinput),
    }
    with samples_file.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(sample, sort_keys=True, separators=(",", ":")) + "\n")
    return sample


def wait_for_xinput(
    out_dir: pathlib.Path,
    timeout_seconds: float,
    interval_seconds: float,
    label: str,
) -> dict[str, Any]:
    samples_file = out_dir / f"{label}_xinput_wait.jsonl"
    started = time.monotonic()
    samples: list[dict[str, Any]] = []
    while time.monotonic() - started <= timeout_seconds:
        sample = sample_xinput(samples_file, label, "wait", started)
        samples.append(sample)
        if slot_connected(sample.get("slot0")):
            break
        time.sleep(interval_seconds)
    summary = summarize_xinput_samples(samples)
    summary["wait_seconds"] = round(time.monotonic() - started, 3)
    summary["samples_file"] = str(samples_file)
    return summary


def run_xinput_sanity(
    serial: SerialPort,
    out_dir: pathlib.Path,
    timeout: float,
    transcript: list[dict[str, Any]],
    label: str,
) -> dict[str, Any]:
    samples_file = out_dir / f"{label}_xinput_samples.jsonl"
    started = time.monotonic()
    send(serial, "STOP_BRIDGE", timeout, transcript)
    results: list[dict[str, Any]] = []
    for scenario in XINPUT_SANITY_SCENARIOS:
        if scenario != "neutral":
            send(serial, "PUBLISH_XBOX_TEST_REPORT neutral", timeout, transcript)
            time.sleep(0.25)
            sample_xinput(samples_file, scenario, "neutral_before", started)
        send(serial, f"PUBLISH_XBOX_TEST_REPORT {scenario}", timeout, transcript)
        time.sleep(0.35)
        scenario_samples = [sample_xinput(samples_file, scenario, "hold", started) for _ in range(3)]
        send(serial, "GET_XBOX_GAMEPAD_REPORT", timeout, transcript)
        send(serial, "GET_BRIDGE_STATUS", timeout, transcript)
        results.append(
            {
                "scenario": scenario,
                "passed": scenario_passed(scenario, scenario_samples),
                "summary": summarize_xinput_samples(scenario_samples),
            }
        )
    send(serial, "PUBLISH_XBOX_TEST_REPORT neutral", timeout, transcript)
    all_samples = []
    if samples_file.exists():
        for line in samples_file.read_text(encoding="utf-8").splitlines():
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                all_samples.append(value)
    summary = {
        "label": label,
        "samples_file": str(samples_file),
        "scenario_results": results,
        "passed": all(result["passed"] for result in results),
        "overall": summarize_xinput_samples(all_samples),
    }
    write_json(out_dir / f"{label}_xinput_sanity_summary.json", summary)
    return summary


def run_ble_scan(out_dir: pathlib.Path, duration_seconds: float) -> dict[str, Any]:
    scan_dir = out_dir / "ble_scan"
    try:
        records, final_status = ble_watcher.run_watcher(duration_seconds, "active")
        error = None
    except Exception as exc:
        records = []
        final_status = "error"
        error = repr(exc)
    summary = ble_watcher.summarize(records, duration_seconds, "active")
    summary["watcher_final_status"] = final_status
    summary["error"] = error
    ble_watcher.write_outputs(scan_dir, records, summary)
    return {"summary": summary, "scan_dir": str(scan_dir)}


def attempt_pair(out_dir: pathlib.Path, duration_seconds: float, expected_name: str) -> dict[str, Any]:
    pair_dir = out_dir / "pairing_attempt"
    records, watcher_status = ble_watcher.run_watcher(duration_seconds, "active")
    advertisement = pairing_witness.summarize_name_records(records, expected_name)
    pairing: dict[str, Any] = {"available": False, "manual_required": True, "reason": "advertisement was not seen"}
    if advertisement["addresses"]:
        pairing = pairing_witness.resolve_and_pair(str(advertisement["addresses"][0]), True)
    summary = {
        "captured_at": utc_stamp(),
        "expected_name": expected_name,
        "duration_seconds": duration_seconds,
        "watcher_final_status": watcher_status,
        "advertisement": advertisement,
        "pairing": pairing,
        "windows_inventory_after_attempt": pairing_witness.collect_windows_inventory(),
    }
    pairing_witness.write_outputs(pair_dir, summary, records)
    return {"summary": summary, "pair_dir": str(pair_dir)}


def run_reset(port: str, command_template: str, wait_seconds: float) -> dict[str, Any]:
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
    return {"command": command, "returncode": result.returncode, "output": result.stdout, "ok": result.returncode == 0}


def run_cache_cleanup(out_dir: pathlib.Path, associated_addresses: tuple[str, ...], remove: bool) -> dict[str, Any]:
    cache_dir = out_dir / "cache_cleanup"
    before = cache_witness.collect_inventory()
    candidates = cache_witness.find_candidates(before, associated_addresses)
    removal_results = cache_witness.remove_candidates(candidates, dry_run=not remove) if candidates else []
    after = cache_witness.collect_inventory() if remove else None
    summary = {
        "captured_at": utc_stamp(),
        "associated_addresses": associated_addresses,
        "removal_attempted": remove,
        "dry_run": not remove,
        "inventory_before": before,
        "candidates": candidates,
        "removal_results": removal_results,
        "inventory_after": after,
        "manual_cleanup_recommended": remove and any(not result.get("ok") for result in removal_results),
    }
    cache_witness.write_outputs(cache_dir, summary)
    return {"summary": summary, "cache_dir": str(cache_dir)}


def prepare_xbox(
    serial: SerialPort,
    timeout: float,
    transcript: list[dict[str, Any]],
    clear_bonds: bool,
) -> dict[str, Any]:
    commands = ["STOP_BRIDGE", "STOP_VIRTUAL_INPUT", "STOP_BLE_PERSONA"]
    if clear_bonds:
        commands.append("FORGET_BLE_BONDS")
    commands.extend(
        [
            "SET_BLE_IDENTITY_STRATEGY persona_static_random_experimental",
            "START_BLE_XBOX_CONTROLLER",
            "GET_BLE_IDENTITY_INFO",
            "GET_BLE_CONNECTION_INFO",
            "GET_BLE_BOND_INFO",
            "GET_BLE_ADVERTISING_INFO",
            "GET_STATUS",
        ]
    )
    return {"records": [send(serial, command, timeout, transcript) for command in commands]}


def classify_reconnect(
    wait_summary: dict[str, Any],
    sanity: dict[str, Any] | None,
    manual_windows_action: bool,
    target_restart_required: bool = False,
) -> str:
    if (
        wait_summary.get("slot0_connected")
        and sanity
        and sanity.get("passed")
        and not manual_windows_action
        and not target_restart_required
    ):
        return "reconnect_pass_auto"
    if wait_summary.get("slot0_connected") and sanity and sanity.get("passed") and not manual_windows_action:
        return "reconnect_pass_after_target_restart"
    if manual_windows_action:
        return "reconnect_requires_windows_manual_connect"
    return "reconnect_fail"


def write_operator_notes(run_dir: pathlib.Path, args: argparse.Namespace) -> None:
    notes = [
        "# Windows Xbox Reconnect Witness Helper",
        "",
        "This run captures single-persona Xbox BLE-compatible reconnect diagnostics on Windows.",
        "It does not use physical HOTAS controls.",
        "",
        f"- clean_cache: {args.clean_cache}",
        f"- skip_cache_clean: {args.skip_cache_clean}",
        f"- manual_pair_ok: {args.manual_pair_ok}",
        f"- assume_paired: {args.assume_paired}",
        f"- skip_prepare: {args.skip_prepare}",
        f"- soft_reset: {args.soft_reset}",
        f"- target_reboot: {args.target_reboot}",
        f"- windows_only_probe: {args.windows_only_probe}",
    ]
    (run_dir / "operator_notes.md").write_text("\n".join(notes) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    run_dir = args.out_dir / f"windows_xbox_reconnect_witness_{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    write_operator_notes(run_dir, args)

    discovery = serial_ports()
    port, probes = select_port(args.port, args.serial_timeout, discovery)
    transcript: list[dict[str, Any]] = []
    associated_addresses = cache_witness.normalize_associated_addresses([args.expected_address])

    summary: dict[str, Any] = {
        "captured_at": iso_now(),
        "run_dir": str(run_dir),
        "port": port,
        "expected_name": XBOX_DEVICE_NAME,
        "expected_address": args.expected_address,
        "physical_controls_used": False,
        "serial_discovery": discovery,
        "serial_probes": probes,
        "manual_actions_required": [],
        "tests": {},
    }

    if args.clean_cache and not args.skip_cache_clean:
        cache = run_cache_cleanup(run_dir, associated_addresses, remove=True)
        summary["cache_cleanup"] = cache["summary"]
        if cache["summary"].get("manual_cleanup_recommended"):
            summary["manual_actions_required"].append(
                'Open Windows Bluetooth settings. Remove/Forget "Xbox Wireless Controller" if it is associated with USB2BLE. Also remove USB2BLE Gamepad/U6 only if they are present and associated with USB2BLE. Do not remove unrelated devices. Then press Enter.'
            )
            write_json(run_dir / "summary.json", summary)
            print(json.dumps(summary, indent=2, sort_keys=True))
            return 3

    if args.windows_only_probe:
        summary["windows_state"] = collect_windows_state()
        write_json(run_dir / "summary.json", summary)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0

    if args.soft_reset or args.target_reboot:
        summary["initial_reset"] = run_reset(port, args.reset_command, args.post_reset_wait_seconds)
        if not summary["initial_reset"].get("ok"):
            write_json(run_dir / "summary.json", summary)
            print(json.dumps(summary, indent=2, sort_keys=True))
            return 2

    serial = SerialPort(port)
    try:
        summary["topology"] = usb_topology_present(serial, args.serial_timeout, transcript)
        if args.skip_prepare:
            summary["prepare_xbox"] = {
                "skipped": True,
                "reason": "caller asserted the target is already in the desired Xbox paired/connected state",
            }
        else:
            summary["prepare_xbox"] = prepare_xbox(serial, args.serial_timeout, transcript, clear_bonds=args.clean_cache)
        summary["target_after_prepare"] = collect_target_diagnostics(serial, args.serial_timeout, transcript)
    finally:
        serial.close()

    if args.assume_paired:
        summary["advertisement"] = {
            "skipped": True,
            "reason": "already-paired connected devices may not advertise while connected",
        }
        summary["pairing_attempt"] = {
            "skipped": True,
            "reason": "manual Windows Settings pairing was completed before this continuation run",
        }
    else:
        summary["advertisement"] = run_ble_scan(run_dir, args.scan_duration)
        summary["pairing_attempt"] = attempt_pair(run_dir, args.scan_duration, XBOX_DEVICE_NAME)
        pair_summary = summary["pairing_attempt"]["summary"]["pairing"]
        if pair_summary.get("manual_required") and args.manual_pair_ok:
            summary["manual_actions_required"].append('Open Windows Bluetooth settings. Pair/connect "Xbox Wireless Controller", then press Enter.')
            write_json(run_dir / "summary.json", summary)
            print(json.dumps(summary, indent=2, sort_keys=True))
            return 3
        if pair_summary.get("manual_required"):
            write_json(run_dir / "summary.json", summary)
            print(json.dumps(summary, indent=2, sort_keys=True))
            return 3

    summary["windows_after_pair_attempt"] = collect_windows_state()
    baseline_dir = run_dir / "baseline_pair"
    baseline_dir.mkdir(exist_ok=True)
    summary["baseline_wait"] = wait_for_xinput(baseline_dir, args.baseline_wait_seconds, 1.0, "baseline")
    if not summary["baseline_wait"].get("slot0_connected"):
        write_json(run_dir / "summary.json", summary)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 4

    serial = SerialPort(port)
    try:
        summary["baseline_target"] = collect_target_diagnostics(serial, args.serial_timeout, transcript)
        summary["baseline_sanity"] = run_xinput_sanity(serial, baseline_dir, args.serial_timeout, transcript, "baseline")

        test_a_dir = run_dir / "test_a_stop_start"
        test_a_dir.mkdir(exist_ok=True)
        test_a_transcript: list[dict[str, Any]] = []
        target_before = collect_target_diagnostics(serial, args.serial_timeout, test_a_transcript)
        stop_result = send(serial, "STOP_BLE_PERSONA", args.serial_timeout, test_a_transcript)
        target_after_stop = collect_target_diagnostics(serial, args.serial_timeout, test_a_transcript)
        start_result = send(serial, "START_BLE_XBOX_CONTROLLER", args.serial_timeout, test_a_transcript)
        target_after_start = collect_target_diagnostics(serial, args.serial_timeout, test_a_transcript)
        wait_summary = wait_for_xinput(test_a_dir, args.reconnect_wait_seconds, 1.0, "stop_start")
        sanity = None
        if wait_summary.get("slot0_connected"):
            sanity = run_xinput_sanity(serial, test_a_dir, args.serial_timeout, test_a_transcript, "stop_start")
        summary["tests"]["test_a_stop_start"] = {
            "target_before": target_before,
            "stop_result": stop_result,
            "target_after_stop": target_after_stop,
            "start_result": start_result,
            "target_after_start": target_after_start,
            "xinput_wait": wait_summary,
            "xinput_sanity": sanity,
            "manual_windows_action": False,
            "classification": classify_reconnect(
                wait_summary,
                sanity,
                manual_windows_action=False,
                target_restart_required=True,
            ),
        }
        (test_a_dir / "serial_transcript.json").write_text(
            json.dumps(test_a_transcript, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        test_b_dir = run_dir / "test_b_disconnect_reconnect"
        test_b_dir.mkdir(exist_ok=True)
        test_b_transcript: list[dict[str, Any]] = []
        disconnect_target_before = collect_target_diagnostics(serial, args.serial_timeout, test_b_transcript)
        disconnect_result = send(serial, "DISCONNECT_BLE_HOST", args.serial_timeout, test_b_transcript)
        disconnect_target_after = collect_target_diagnostics(serial, args.serial_timeout, test_b_transcript)
        disconnect_wait = wait_for_xinput(test_b_dir, args.reconnect_wait_seconds, 1.0, "disconnect_reconnect")
        disconnect_sanity = None
        if disconnect_wait.get("slot0_connected"):
            disconnect_sanity = run_xinput_sanity(
                serial,
                test_b_dir,
                args.serial_timeout,
                test_b_transcript,
                "disconnect_reconnect",
            )
        summary["tests"]["test_b_disconnect_reconnect"] = {
            "target_before": disconnect_target_before,
            "disconnect_result": disconnect_result,
            "target_after_disconnect": disconnect_target_after,
            "xinput_wait": disconnect_wait,
            "xinput_sanity": disconnect_sanity,
            "manual_windows_action": False,
            "classification": "disconnect_unsupported"
            if not disconnect_result.get("ok")
            else classify_reconnect(
                disconnect_wait,
                disconnect_sanity,
                manual_windows_action=False,
                target_restart_required=False,
            ),
        }
        (test_b_dir / "serial_transcript.json").write_text(
            json.dumps(test_b_transcript, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    finally:
        serial.close()

    test_c_dir = run_dir / "test_c_soft_reset"
    test_c_dir.mkdir(exist_ok=True)
    pre_reset_state = collect_windows_state()
    reset_result = run_reset(port, args.reset_command, args.post_reset_wait_seconds)
    summary["tests"]["test_c_soft_reset"] = {
        "pre_reset_windows": pre_reset_state,
        "reset_result": reset_result,
        "manual_windows_action": False,
    }
    if reset_result.get("ok"):
        serial = SerialPort(port)
        try:
            post_reset_transcript: list[dict[str, Any]] = []
            post_reset_target_before = collect_target_diagnostics(serial, args.serial_timeout, post_reset_transcript)
            prepare_after_reset = prepare_xbox(serial, args.serial_timeout, post_reset_transcript, clear_bonds=False)
            post_reset_target_after = collect_target_diagnostics(serial, args.serial_timeout, post_reset_transcript)
        finally:
            serial.close()
        (test_c_dir / "serial_transcript.json").write_text(
            json.dumps(post_reset_transcript, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        wait_summary = wait_for_xinput(test_c_dir, args.reconnect_wait_seconds, 1.0, "soft_reset")
        sanity = None
        if wait_summary.get("slot0_connected"):
            serial = SerialPort(port)
            try:
                post_sanity_transcript: list[dict[str, Any]] = []
                sanity = run_xinput_sanity(serial, test_c_dir, args.serial_timeout, post_sanity_transcript, "soft_reset")
            finally:
                serial.close()
            (test_c_dir / "sanity_serial_transcript.json").write_text(
                json.dumps(post_sanity_transcript, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        summary["tests"]["test_c_soft_reset"].update(
            {
                "target_before_restart": post_reset_target_before,
                "prepare_after_reset": prepare_after_reset,
                "target_after_restart": post_reset_target_after,
                "xinput_wait": wait_summary,
                "xinput_sanity": sanity,
                "classification": classify_reconnect(
                    wait_summary,
                    sanity,
                    manual_windows_action=False,
                    target_restart_required=True,
                ),
            }
        )

    if args.target_reboot:
        test_d_dir = run_dir / "test_d_power_cycle_surrogate"
        test_d_dir.mkdir(exist_ok=True)
        summary["tests"]["test_d_power_cycle_surrogate"] = {
            "classification": "not_run",
            "detail": "A true hard power-cycle requires an operator action and is intentionally left out unless needed after A/B.",
        }

    (run_dir / "serial_transcript.json").write_text(
        json.dumps(transcript, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_json(run_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="auto")
    parser.add_argument("--out-dir", type=pathlib.Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--expected-address", default=XBOX_ADDRESS)
    parser.add_argument("--clean-cache", action="store_true")
    parser.add_argument("--manual-pair-ok", action="store_true")
    parser.add_argument("--assume-paired", action="store_true")
    parser.add_argument("--skip-cache-clean", action="store_true")
    parser.add_argument("--skip-prepare", action="store_true")
    parser.add_argument("--no-physical-input", action="store_true")
    parser.add_argument("--soft-reset", action="store_true")
    parser.add_argument("--target-reboot", action="store_true")
    parser.add_argument("--windows-only-probe", action="store_true")
    parser.add_argument("--serial-timeout", type=float, default=3.0)
    parser.add_argument("--scan-duration", type=float, default=20.0)
    parser.add_argument("--baseline-wait-seconds", type=float, default=45.0)
    parser.add_argument("--reconnect-wait-seconds", type=float, default=90.0)
    parser.add_argument("--reset-command", default=DEFAULT_RESET_COMMAND)
    parser.add_argument("--post-reset-wait-seconds", type=float, default=8.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    return run(parse_args(sys.argv[1:] if argv is None else argv))


if __name__ == "__main__":
    raise SystemExit(main())
