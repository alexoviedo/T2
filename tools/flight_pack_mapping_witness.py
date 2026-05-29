#!/usr/bin/env python3
"""Capture focused Flight Pack mapping/report evidence over USB serial."""

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
    parse_usb_devices,
    print_record,
    response_with_prefix,
    run_commands,
    utc_stamp,
)
from flight_pack_calibration_witness import (
    T16000_PID,
    TWCS_PID,
    MovementStep,
    changed_summary,
    parse_mapping_targets,
    parse_normalized,
    source_for_device,
    write_transcript,
)


DEFAULT_PORT = "/dev/cu.usbmodem5B5E0200881"
DEFAULT_OUT_DIR = "target/flight-pack-mapping-witness"
REQUIRED_DEVICE_IDS = {
    "HooToo hub": ("2109", "2813"),
    "T.16000M stick": ("044f", "b10a"),
    "TWCS/RJ12": ("044f", "b687"),
}


@dataclass(frozen=True)
class MappingStep:
    key: str
    label: str
    source_kind: str
    instruction: str
    source_control_id: str
    generic_target: str | None
    xbox_target: str | None
    expected_generic_reason: str | None
    expected_xbox_reason: str | None


STEPS = [
    MappingStep(
        "throttle_min",
        "TWCS throttle minimum",
        "twcs",
        "Move only the TWCS throttle to its minimum position and hold it.",
        "axis_01_32",
        "z",
        None,
        "profile_rule_inverted",
        "profile_unmapped",
    ),
    MappingStep(
        "throttle_max",
        "TWCS throttle maximum",
        "twcs",
        "Move only the TWCS throttle to its maximum position and hold it.",
        "axis_01_32",
        "z",
        None,
        "profile_rule_inverted",
        "profile_unmapped",
    ),
    MappingStep(
        "rudder_left_rj12",
        "TFRP/RJ12 rudder left",
        "twcs",
        "Press only full RJ12 rudder left and hold it.",
        "axis_01_36",
        "rx",
        "right_x",
        "profile_rule",
        "profile_rule",
    ),
    MappingStep(
        "rudder_right_rj12",
        "TFRP/RJ12 rudder right",
        "twcs",
        "Press only full RJ12 rudder right and hold it.",
        "axis_01_36",
        "rx",
        "right_x",
        "profile_rule",
        "profile_rule",
    ),
    MappingStep(
        "left_toe_released",
        "TFRP/RJ12 left toe brake released",
        "twcs",
        "Release the left toe brake and keep all other pedal axes still.",
        "axis_01_34",
        "ry",
        "left_trigger",
        "profile_rule_inverted",
        "profile_rule_calibrated",
    ),
    MappingStep(
        "left_toe_pressed",
        "TFRP/RJ12 left toe brake pressed",
        "twcs",
        "Press only the left toe brake fully and hold it.",
        "axis_01_34",
        "ry",
        "left_trigger",
        "profile_rule_inverted",
        "profile_rule_calibrated",
    ),
    MappingStep(
        "right_toe_released",
        "TFRP/RJ12 right toe brake released",
        "twcs",
        "Release the right toe brake and keep all other pedal axes still.",
        "axis_01_33",
        "rz",
        "right_trigger",
        "profile_rule_inverted",
        "profile_rule_calibrated",
    ),
    MappingStep(
        "right_toe_pressed",
        "TFRP/RJ12 right toe brake pressed",
        "twcs",
        "Press only the right toe brake fully and hold it.",
        "axis_01_33",
        "rz",
        "right_trigger",
        "profile_rule_inverted",
        "profile_rule_calibrated",
    ),
]


def notify_operator(message: str, enabled: bool) -> None:
    if not enabled:
        return
    subprocess.run(
        [
            "osascript",
            "-e",
            f'display notification "{message}" with title "USB2BLE mapping witness"',
        ],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def prompt(step: MappingStep, assume_ready: bool, alerts: bool) -> None:
    print()
    print("=" * 72)
    print(f"{step.label}")
    print(step.instruction)
    print("Hold only that control; keep all other controls still.")
    notify_operator(step.instruction, alerts)
    if assume_ready:
        time.sleep(1.0)
        return
    input("Press Enter when ready...")


def capture_step(serial: SerialPort, source: str, timeout: float) -> list[CommandRecord]:
    return run_commands(
        serial,
        [
            f"GET_NORMALIZED_INPUT {source}",
            "GET_GENERIC_GAMEPAD_MAPPING",
            "GET_XBOX_GAMEPAD_MAPPING",
            "GET_GENERIC_GAMEPAD_REPORT",
            "GET_XBOX_GAMEPAD_REPORT",
        ],
        timeout,
    )


def normalize_hex(value: str) -> str:
    value = value.lower().removeprefix("0x")
    return value.zfill(4)


def has_device(devices: list[dict[str, str]], vid: str, pid: str) -> bool:
    return any(
        normalize_hex(device.get("vid", "")) == normalize_hex(vid)
        and normalize_hex(device.get("pid", "")) == normalize_hex(pid)
        for device in devices
    )


def mapping_entry(
    mapping: dict[str, dict[str, str]], source_control_id: str
) -> dict[str, str] | None:
    return next(
        (fields for src, fields in mapping.items() if src.endswith(f":{source_control_id}")),
        None,
    )


def target_matches(entry: dict[str, str] | None, expected: str | None) -> bool:
    actual = (entry or {}).get("target")
    normalized_actual = None if actual in (None, "none") else actual
    return normalized_actual == expected


def encoded_reports(records: list[CommandRecord]) -> list[str]:
    return [
        response
        for record in records
        for response in record.responses
        if response.startswith("ENCODED_REPORT:")
    ]


def movement_summary(
    step: MappingStep,
    source: str,
    previous: dict[str, dict[str, int | str]] | None,
    records: list[CommandRecord],
) -> dict[str, Any]:
    normalized = parse_normalized(response_with_prefix(records, "NORMALIZED_INPUT:"))
    generic_mapping = parse_mapping_targets(
        response_with_prefix(records, "GENERIC_GAMEPAD_MAPPING:")
    )
    xbox_mapping = parse_mapping_targets(response_with_prefix(records, "XBOX_GAMEPAD_MAPPING:"))
    movement = changed_summary(
        MovementStep(
            step.key,
            step.label,
            step.source_kind,
            step.instruction,
            step.source_control_id,
        ),
        previous,
        normalized,
        generic_mapping,
        xbox_mapping,
    )
    generic_entry = mapping_entry(generic_mapping, step.source_control_id)
    xbox_entry = mapping_entry(xbox_mapping, step.source_control_id)
    return {
        "step": step.key,
        "label": step.label,
        "source": source,
        "source_control_id": step.source_control_id,
        "expected_generic_target": step.generic_target,
        "expected_xbox_target": step.xbox_target,
        "generic_mapping": generic_entry,
        "xbox_mapping": xbox_entry,
        "generic_target_ok": target_matches(generic_entry, step.generic_target),
        "xbox_target_ok": target_matches(xbox_entry, step.xbox_target),
        "generic_reason_ok": (generic_entry or {}).get("reason") == step.expected_generic_reason,
        "xbox_reason_ok": (xbox_entry or {}).get("reason") == step.expected_xbox_reason,
        "movement": movement,
        "encoded_reports": encoded_reports(records),
        "normalized": normalized,
    }


def write_notes(path: pathlib.Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Flight Pack Mapping Witness Notes",
        "",
        "This run captures target-side mapping diagnostics and encoded report output",
        "for the refined practical RJ12 Flight Pack mapping.",
        "",
        f"- Port: `{payload['port']}`",
        f"- T.16000M source: `{payload['source_map'].get('stick') or 'not observed'}`",
        f"- TWCS/RJ12 source: `{payload['source_map'].get('twcs') or 'not observed'}`",
        f"- Mapping targets proven: `{payload['all_expected_targets_observed']}`",
        f"- High-confidence movement steps: `{', '.join(payload['high_confidence_steps'])}`",
        "",
        "Not proven by this run: browser UI behavior, BLE host input, game/app",
        "compatibility, BLE bond persistence, broad host support, or final",
        "product-quality calibration.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--assume-ready", action="store_true")
    parser.add_argument("--quiet-alerts", action="store_true")
    parser.add_argument(
        "--steps",
        default=",".join(step.key for step in STEPS),
        help="Comma-separated step keys, or 'all'.",
    )
    args = parser.parse_args()

    selected_keys = (
        [step.key for step in STEPS]
        if args.steps == "all"
        else [key.strip() for key in args.steps.split(",") if key.strip()]
    )
    selected_steps = [step for step in STEPS if step.key in selected_keys]
    if not selected_steps:
        print("ERROR: no valid movement steps selected.", file=sys.stderr)
        return 2

    stamp = utc_stamp()
    run_dir = pathlib.Path(args.out_dir) / f"flight_pack_mapping_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    sections: list[tuple[str, list[CommandRecord]]] = []
    summaries: list[dict[str, Any]] = []
    previous_by_source: dict[str, dict[str, dict[str, int | str]]] = {}

    print("USB2BLE Flight Pack mapping witness")
    print(f"Transcript directory: {run_dir}")

    serial = SerialPort(args.port)
    try:
        preflight = run_commands(
            serial,
            ["GET_INFO", "GET_STATUS", "GET_USB_STATUS", "LIST_USB_DEVICES"],
            args.timeout,
        )
        sections.append(("preflight", preflight))
        devices = parse_usb_devices(response_with_prefix(preflight, "USB_DEVICES:"))
        observed_devices = {
            name: has_device(devices, vid, pid)
            for name, (vid, pid) in REQUIRED_DEVICE_IDS.items()
        }
        source_map = {
            "stick": source_for_device(devices, T16000_PID),
            "twcs": source_for_device(devices, TWCS_PID),
        }

        print(f"T.16000M source: {source_map['stick'] or 'not observed'}")
        print(f"TWCS/RJ12 source: {source_map['twcs'] or 'not observed'}")
        if not source_map["twcs"]:
            print("ERROR: TWCS/RJ12 source not observed.", file=sys.stderr)
            return 3

        for index, step in enumerate(selected_steps, start=1):
            source = source_map.get(step.source_kind)
            if source is None:
                print(f"Skipping {step.label}: source {step.source_kind!r} not observed.")
                continue
            print(f"Step {index}/{len(selected_steps)}")
            prompt(step, args.assume_ready, not args.quiet_alerts)
            records = capture_step(serial, source, args.timeout)
            sections.append((step.key, records))
            summary = movement_summary(
                step,
                source,
                previous_by_source.get(step.source_kind),
                records,
            )
            previous_by_source[step.source_kind] = summary["normalized"]
            summaries.append(summary)
            print_record(CommandRecord(f"SUMMARY {step.key}", [json.dumps(summary["movement"])]))
    finally:
        serial.close()

    transcript = run_dir / "serial_transcript.txt"
    line_refs = write_transcript(transcript, sections)
    high_confidence_steps = [
        summary["step"]
        for summary in summaries
        if summary["movement"].get("confidence") == "high"
    ]
    low_confidence_steps = [
        summary["step"]
        for summary in summaries
        if summary["movement"].get("confidence") in {"low", "none"}
    ]
    all_expected_targets_observed = all(
        summary["generic_target_ok"] and summary["xbox_target_ok"] for summary in summaries
    )
    all_expected_reasons_observed = all(
        summary["generic_reason_ok"] and summary["xbox_reason_ok"] for summary in summaries
    )
    payload: dict[str, Any] = {
        "captured_at": stamp,
        "port": args.port,
        "run_dir": str(run_dir),
        "transcript": str(transcript),
        "source_map": source_map,
        "observed_devices": observed_devices,
        "all_expected_targets_observed": all_expected_targets_observed,
        "all_expected_reasons_observed": all_expected_reasons_observed,
        "all_required_steps_captured": len(summaries) == len(selected_steps),
        "high_confidence_steps": high_confidence_steps,
        "low_confidence_steps": low_confidence_steps,
        "line_refs": line_refs,
        "summaries": summaries,
    }
    (run_dir / "summary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (run_dir / "movement_mapping_summary.json").write_text(
        json.dumps(summaries, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_notes(run_dir / "operator_notes.md", payload)

    print()
    print(f"Saved transcript: {transcript}")
    print(f"Saved summary: {run_dir / 'summary.json'}")
    if not all_expected_targets_observed:
        print("ERROR: not all expected mapping targets were observed.", file=sys.stderr)
        return 1
    if low_confidence_steps:
        print(f"WARNING: low-confidence movement steps: {', '.join(low_confidence_steps)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        raise SystemExit(130)
