#!/usr/bin/env python3
"""Run a timed Xbox virtual-input app witness on Windows.

This helper assumes the target is already paired/connected as the Xbox persona.
It does not automate the app UI and it does not use physical controls. It
publishes virtual normalized-input frames, samples XInput slot state, and writes
artifact files that can be paired with a real app/game observation.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import pathlib
import sys
import time
from typing import Any

from configure_board import preset_config
from serial_command import SerialPort
from windows_gamepad_probe import collect_xinput_slots


DEFAULT_OUT_DIR = pathlib.Path("target/windows-game-compatibility/windows-xbox-app-witness")
CONFIG_CHUNK_BYTES = 72
DEFAULT_SCENARIOS = [
    "neutral",
    "stick_left",
    "stick_right",
    "stick_forward",
    "stick_back",
    "rudder_left",
    "rudder_right",
    "left_toe_pressed",
    "left_toe_released",
    "right_toe_pressed",
    "right_toe_released",
]


def utc_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def xinput_slot(xinput: dict[str, Any], slot_index: int = 0) -> dict[str, Any] | None:
    slots = xinput.get("slots")
    if not isinstance(slots, list):
        return None
    for slot in slots:
        if isinstance(slot, dict) and slot.get("slot") == slot_index:
            return slot
    return None


def command_record(command: str, responses: list[str]) -> dict[str, Any]:
    return {
        "at": iso_now(),
        "command": command,
        "responses": responses,
        "ok": not any(response.startswith("ERROR:") for response in responses),
    }


def send(serial: SerialPort, command: str, timeout: float, transcript: list[dict[str, Any]]) -> dict[str, Any]:
    responses = serial.command_response(command, timeout)
    record = command_record(command, responses)
    transcript.append(record)
    print(f">> {command}")
    if responses:
        for response in responses:
            print(response)
    else:
        print("<no matching response>")
    return record


def import_config_json(
    serial: SerialPort,
    payload: bytes,
    timeout: float,
    transcript: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    chunks = [
        base64.urlsafe_b64encode(payload[index : index + CONFIG_CHUNK_BYTES]).decode("ascii").rstrip("=")
        for index in range(0, len(payload), CONFIG_CHUNK_BYTES)
    ]
    checksum = hashlib.sha256(payload).hexdigest()
    for command in [f"BEGIN_CONFIG_JSON {len(chunks)} {checksum}"] + [
        f"CONFIG_JSON_CHUNK {index} {chunk}" for index, chunk in enumerate(chunks)
    ] + ["COMMIT_CONFIG_JSON"]:
        record = send(serial, command, timeout, transcript)
        records.append(record)
    return records


def sample_xinput(
    samples_file: pathlib.Path,
    scenario: str,
    phase: str,
    started_at: float,
) -> dict[str, Any]:
    xinput = collect_xinput_slots()
    slot0 = xinput_slot(xinput, 0)
    sample = {
        "at": iso_now(),
        "elapsed_s": round(time.monotonic() - started_at, 3),
        "scenario": scenario,
        "phase": phase,
        "xinput": xinput,
        "slot0": slot0,
    }
    with samples_file.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(sample, separators=(",", ":"), sort_keys=True) + "\n")
    return sample


def connected_slot0(sample: dict[str, Any]) -> bool:
    slot0 = sample.get("slot0")
    return isinstance(slot0, dict) and slot0.get("connected") is True


def summarize_slot_samples(samples: list[dict[str, Any]]) -> dict[str, Any]:
    slots = [sample.get("slot0") for sample in samples if isinstance(sample.get("slot0"), dict)]
    connected_slots = [slot for slot in slots if slot.get("connected") is True]
    if not connected_slots:
        return {
            "sample_count": len(samples),
            "connected_count": 0,
            "slot0_connected": False,
        }
    left_x = [int(slot.get("left_thumb", [0, 0])[0]) for slot in connected_slots]
    left_y = [int(slot.get("left_thumb", [0, 0])[1]) for slot in connected_slots]
    right_x = [int(slot.get("right_thumb", [0, 0])[0]) for slot in connected_slots]
    right_y = [int(slot.get("right_thumb", [0, 0])[1]) for slot in connected_slots]
    left_trigger = [int(slot.get("left_trigger", 0)) for slot in connected_slots]
    right_trigger = [int(slot.get("right_trigger", 0)) for slot in connected_slots]
    buttons = [int(slot.get("buttons", 0)) for slot in connected_slots]
    return {
        "sample_count": len(samples),
        "connected_count": len(connected_slots),
        "slot0_connected": True,
        "left_thumb_x_min": min(left_x),
        "left_thumb_x_max": max(left_x),
        "left_thumb_y_min": min(left_y),
        "left_thumb_y_max": max(left_y),
        "right_thumb_x_min": min(right_x),
        "right_thumb_x_max": max(right_x),
        "right_thumb_y_min": min(right_y),
        "right_thumb_y_max": max(right_y),
        "left_trigger_min": min(left_trigger),
        "left_trigger_max": max(left_trigger),
        "right_trigger_min": min(right_trigger),
        "right_trigger_max": max(right_trigger),
        "buttons_observed": sorted(set(buttons)),
    }


def read_samples(samples_file: pathlib.Path) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    if not samples_file.exists():
        return samples
    for line in samples_file.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            samples.append(value)
    return samples


def write_operator_notes(run_dir: pathlib.Path, args: argparse.Namespace) -> None:
    notes = [
        "# Windows Xbox App Witness Helper",
        "",
        "This helper publishes virtual Xbox-persona input frames and samples XInput.",
        "It does not automate the target app UI and it does not use physical HOTAS controls.",
        "",
        f"- target: {args.target_name}",
        f"- scenarios: {', '.join(args.scenario)}",
        f"- deterministic test report scenarios: {', '.join(args.test_report_scenario) if args.test_report_scenario else 'none'}",
        f"- hold_seconds: {args.hold_seconds}",
        f"- sample_interval_seconds: {args.sample_interval_seconds}",
        f"- publish_interval_seconds: {args.publish_interval_seconds}",
        f"- publish_settle_seconds: {args.publish_settle_seconds}",
        f"- configure_flight_pack_xbox: {args.configure_flight_pack_xbox}",
        "",
        "Pair these artifacts with a separate app/game observation before making any app/game compatibility claim.",
    ]
    (run_dir / "operator_notes.md").write_text("\n".join(notes) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    run_dir = args.out_dir / f"windows_xbox_app_witness_{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    transcript: list[dict[str, Any]] = []
    samples_file = run_dir / "xinput_samples.jsonl"
    started = time.monotonic()

    serial = SerialPort(args.port)
    try:
        send(serial, "GET_STATUS", args.serial_timeout, transcript)
        if args.prepare_virtual:
            if args.configure_flight_pack_xbox:
                payload = json.dumps(preset_config("flight-pack-xbox"), separators=(",", ":")).encode("utf-8")
                import_config_json(serial, payload, args.serial_timeout, transcript)
                send(serial, "GET_CONFIG_STATUS", args.serial_timeout, transcript)
            for command in (
                "START_VIRTUAL_INPUT",
                "PUBLISH_VIRTUAL_INPUT_FRAME neutral",
                "GET_VIRTUAL_INPUT_STATUS",
                "START_BRIDGE",
                "GET_BRIDGE_STATUS",
            ):
                send(serial, command, args.serial_timeout, transcript)

        initial_sample = sample_xinput(samples_file, "preflight", "initial", started)
        if not connected_slot0(initial_sample):
            print("XInput slot 0 is not connected; app witness cannot continue.", file=sys.stderr)
            return 2

        scenario_summaries: list[dict[str, Any]] = []
        for scenario in args.scenario:
            print()
            print(f"Scenario {scenario}: hold for {args.hold_seconds:.1f}s")
            scenario_samples: list[dict[str, Any]] = []
            if scenario != "neutral":
                send(serial, "PUBLISH_VIRTUAL_INPUT_FRAME neutral", args.serial_timeout, transcript)
                time.sleep(args.neutral_settle_seconds)
                scenario_samples.append(sample_xinput(samples_file, scenario, "neutral_before", started))

            deadline = time.monotonic() + args.hold_seconds
            next_publish = time.monotonic()
            while time.monotonic() < deadline:
                now = time.monotonic()
                if now >= next_publish:
                    send(serial, f"PUBLISH_VIRTUAL_INPUT_FRAME {scenario}", args.serial_timeout, transcript)
                    time.sleep(args.publish_settle_seconds)
                    next_publish = time.monotonic() + args.publish_interval_seconds
                scenario_samples.append(sample_xinput(samples_file, scenario, "hold", started))
                remaining = max(0.0, deadline - time.monotonic())
                print(f"  {scenario}: {remaining:.1f}s remaining", end="\r")
                time.sleep(args.sample_interval_seconds)
            print(" " * 80, end="\r")
            send(serial, "GET_VIRTUAL_INPUT_STATUS", args.serial_timeout, transcript)
            send(serial, "GET_XBOX_GAMEPAD_REPORT", args.serial_timeout, transcript)
            send(serial, "GET_BRIDGE_STATUS", args.serial_timeout, transcript)
            scenario_summaries.append(
                {
                    "kind": "virtual_input_frame",
                    "scenario": scenario,
                    "summary": summarize_slot_samples(scenario_samples),
                }
            )

        test_report_summaries: list[dict[str, Any]] = []
        if args.test_report_scenario:
            send(serial, "STOP_BRIDGE", args.serial_timeout, transcript)
            for scenario in args.test_report_scenario:
                print()
                print(f"Test report {scenario}: hold for {args.hold_seconds:.1f}s")
                scenario_samples = []
                send(serial, "PUBLISH_XBOX_TEST_REPORT neutral", args.serial_timeout, transcript)
                time.sleep(args.neutral_settle_seconds)
                scenario_samples.append(sample_xinput(samples_file, scenario, "neutral_before", started))
                send(serial, f"PUBLISH_XBOX_TEST_REPORT {scenario}", args.serial_timeout, transcript)
                time.sleep(args.publish_settle_seconds)
                deadline = time.monotonic() + args.hold_seconds
                while time.monotonic() < deadline:
                    scenario_samples.append(sample_xinput(samples_file, scenario, "hold", started))
                    remaining = max(0.0, deadline - time.monotonic())
                    print(f"  {scenario}: {remaining:.1f}s remaining", end="\r")
                    time.sleep(args.sample_interval_seconds)
                print(" " * 80, end="\r")
                send(serial, "GET_XBOX_GAMEPAD_REPORT", args.serial_timeout, transcript)
                test_report_summaries.append(
                    {
                        "kind": "deterministic_xbox_test_report",
                        "scenario": scenario,
                        "summary": summarize_slot_samples(scenario_samples),
                    }
                )

        send(serial, "PUBLISH_VIRTUAL_INPUT_FRAME neutral", args.serial_timeout, transcript)
        if args.test_report_scenario:
            send(serial, "PUBLISH_XBOX_TEST_REPORT neutral", args.serial_timeout, transcript)
        sample_xinput(samples_file, "postflight", "neutral", started)
        if args.stop_after:
            send(serial, "STOP_BRIDGE", args.serial_timeout, transcript)
            send(serial, "STOP_VIRTUAL_INPUT", args.serial_timeout, transcript)
    finally:
        serial.close()

    samples = read_samples(samples_file)
    summary = {
        "captured_at": iso_now(),
        "target_name": args.target_name,
        "port": args.port,
        "run_dir": str(run_dir),
        "scenario_count": len(args.scenario),
        "sample_count": len(samples),
        "configured_runtime_preset": "flight-pack-xbox" if args.configure_flight_pack_xbox else None,
        "xinput_overall": summarize_slot_samples(samples),
        "scenarios": scenario_summaries,
        "test_report_scenarios": test_report_summaries,
        "physical_controls_used": False,
        "claim_boundary": "virtual Xbox XInput app witness helper only; app/game behavior requires separate observation",
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (run_dir / "serial_transcript.json").write_text(
        json.dumps(transcript, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_operator_notes(run_dir, args)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--out-dir", type=pathlib.Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--target-name", default="unspecified app/game target")
    parser.add_argument("--scenario", action="append", default=None)
    parser.add_argument("--test-report-scenario", action="append", default=None)
    parser.add_argument("--hold-seconds", type=float, default=2.0)
    parser.add_argument("--neutral-settle-seconds", type=float, default=0.25)
    parser.add_argument("--sample-interval-seconds", type=float, default=0.20)
    parser.add_argument("--publish-interval-seconds", type=float, default=0.65)
    parser.add_argument("--publish-settle-seconds", type=float, default=0.30)
    parser.add_argument("--serial-timeout", type=float, default=3.0)
    parser.add_argument("--skip-prepare", dest="prepare_virtual", action="store_false")
    parser.add_argument("--skip-configure", dest="configure_flight_pack_xbox", action="store_false")
    parser.add_argument("--stop-after", action="store_true")
    parser.set_defaults(prepare_virtual=True)
    parser.set_defaults(configure_flight_pack_xbox=True)
    args = parser.parse_args(argv)
    if args.scenario is None:
        args.scenario = list(DEFAULT_SCENARIOS)
    if args.test_report_scenario is None:
        args.test_report_scenario = []
    return args


def main(argv: list[str] | None = None) -> int:
    return run(parse_args(sys.argv[1:] if argv is None else argv))


if __name__ == "__main__":
    raise SystemExit(main())
