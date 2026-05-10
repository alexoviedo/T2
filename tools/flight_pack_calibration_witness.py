#!/usr/bin/env python3
"""Capture Flight Pack movement evidence for calibration and axis labeling."""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time
from dataclasses import dataclass
from typing import Any

from asap_demo_rehearsal import (
    CommandRecord,
    SerialPort,
    normalize_hex_id,
    parse_usb_devices,
    print_record,
    response_with_prefix,
    run_commands,
    utc_stamp,
)


DEFAULT_PORT = "/dev/cu.usbmodem5B5E0200881"
THRUSTMASTER_VID = "044f"
T16000_PID = "b10a"
TWCS_PID = "b687"


@dataclass(frozen=True)
class MovementStep:
    key: str
    label: str
    source_kind: str
    instruction: str
    inferred_label: str


STEPS = [
    MovementStep(
        "stick_center",
        "Stick center",
        "stick",
        "Center the T.16000M stick, release twist, and release all stick buttons.",
        "stick neutral reference",
    ),
    MovementStep(
        "stick_full_left",
        "Stick full left",
        "stick",
        "Move only the T.16000M stick fully left and hold it.",
        "stick roll left/right axis",
    ),
    MovementStep(
        "stick_full_right",
        "Stick full right",
        "stick",
        "Move only the T.16000M stick fully right and hold it.",
        "stick roll left/right axis",
    ),
    MovementStep(
        "stick_full_forward",
        "Stick full forward",
        "stick",
        "Move only the T.16000M stick fully forward and hold it.",
        "stick pitch forward/back axis",
    ),
    MovementStep(
        "stick_full_back",
        "Stick full back",
        "stick",
        "Move only the T.16000M stick fully back and hold it.",
        "stick pitch forward/back axis",
    ),
    MovementStep(
        "stick_twist_left",
        "Stick twist left",
        "stick",
        "Twist only the T.16000M stick fully left and hold it.",
        "stick twist rudder axis",
    ),
    MovementStep(
        "stick_twist_right",
        "Stick twist right",
        "stick",
        "Twist only the T.16000M stick fully right and hold it.",
        "stick twist rudder axis",
    ),
    MovementStep(
        "stick_trigger_release",
        "Stick trigger released",
        "stick",
        "Release the T.16000M trigger and keep every other control still.",
        "stick trigger released",
    ),
    MovementStep(
        "stick_trigger_press",
        "Stick trigger pressed",
        "stick",
        "Press only the T.16000M trigger and hold it.",
        "stick trigger button",
    ),
    MovementStep(
        "throttle_min",
        "TWCS throttle minimum",
        "twcs",
        "Move only the TWCS throttle to its minimum position and hold it.",
        "TWCS throttle axis",
    ),
    MovementStep(
        "throttle_max",
        "TWCS throttle maximum",
        "twcs",
        "Move only the TWCS throttle to its maximum position and hold it.",
        "TWCS throttle axis",
    ),
    MovementStep(
        "rudder_left_rj12",
        "TFRP/RJ12 rudder left",
        "twcs",
        "With pedals connected to TWCS by RJ12, press only full rudder left and hold it.",
        "TFRP RJ12 rudder axis",
    ),
    MovementStep(
        "rudder_right_rj12",
        "TFRP/RJ12 rudder right",
        "twcs",
        "With pedals connected to TWCS by RJ12, press only full rudder right and hold it.",
        "TFRP RJ12 rudder axis",
    ),
    MovementStep(
        "left_toe_brake_min",
        "TFRP/RJ12 left toe brake released",
        "twcs",
        "Release the left toe brake and keep other pedal axes still.",
        "TFRP RJ12 left toe brake axis",
    ),
    MovementStep(
        "left_toe_brake_max",
        "TFRP/RJ12 left toe brake pressed",
        "twcs",
        "Press only the left toe brake fully and hold it.",
        "TFRP RJ12 left toe brake axis",
    ),
    MovementStep(
        "right_toe_brake_min",
        "TFRP/RJ12 right toe brake released",
        "twcs",
        "Release the right toe brake and keep other pedal axes still.",
        "TFRP RJ12 right toe brake axis",
    ),
    MovementStep(
        "right_toe_brake_max",
        "TFRP/RJ12 right toe brake pressed",
        "twcs",
        "Press only the right toe brake fully and hold it.",
        "TFRP RJ12 right toe brake axis",
    ),
]


def prompt(message: str, assume_ready: bool) -> None:
    print()
    print(message)
    if assume_ready:
        time.sleep(1.0)
        return
    try:
        input("Press Enter when ready...")
    except EOFError:
        print("No interactive stdin available; continuing after a short pause.")
        time.sleep(2.0)


def source_for_device(devices: list[dict[str, str]], pid: str) -> str | None:
    target_pid = normalize_hex_id(pid)
    for device in devices:
        if (
            normalize_hex_id(device.get("vid", "")) == THRUSTMASTER_VID
            and normalize_hex_id(device.get("pid", "")) == target_pid
            and "id" in device
        ):
            return f"{device['id']}:0"
    return None


def parse_normalized(line: str | None) -> dict[str, dict[str, int | str]]:
    if line is None or not line.startswith("NORMALIZED_INPUT:"):
        return {}
    values: dict[str, dict[str, int | str]] = {}
    for key, kind, value in re.findall(r"(.*?[^;=])=(axis|button|hat|trigger|unknown):(-?\d+);", line):
        if key == "controls":
            continue
        values[key] = {"kind": kind, "value": int(value)}
    return values


def parse_mapping_targets(line: str | None) -> dict[str, dict[str, str]]:
    if line is None or "mappings=" not in line:
        return {}
    _, _, tail = line.partition("mappings=")
    entries: dict[str, dict[str, str]] = {}
    for raw_entry in tail.rstrip(";").split("|"):
        fields: dict[str, str] = {}
        for raw_field in raw_entry.split(","):
            key, sep, value = raw_field.partition("=")
            if sep:
                fields[key] = value
        src = fields.get("src")
        if src:
            entries[src] = fields
    return entries


def numeric_delta(
    before: dict[str, dict[str, int | str]],
    after: dict[str, dict[str, int | str]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for control_id in sorted(set(before) | set(after)):
        old = before.get(control_id)
        new = after.get(control_id)
        old_value = old.get("value") if old else None
        new_value = new.get("value") if new else None
        if old_value == new_value:
            continue
        delta = (
            None
            if old_value is None or new_value is None
            else int(new_value) - int(old_value)
        )
        rows.append(
            {
                "control_id": control_id,
                "kind": (new or old or {}).get("kind", "unknown"),
                "before": old_value,
                "after": new_value,
                "delta": delta,
                "abs_delta": 0 if delta is None else abs(delta),
            }
        )
    return sorted(rows, key=lambda row: int(row["abs_delta"]), reverse=True)


def changed_summary(
    step: MovementStep,
    previous: dict[str, dict[str, int | str]] | None,
    current: dict[str, dict[str, int | str]],
    generic_mapping: dict[str, dict[str, str]],
    xbox_mapping: dict[str, dict[str, str]],
) -> dict[str, Any]:
    deltas = numeric_delta(previous or {}, current)
    primary = deltas[0] if deltas else None
    confidence = "none"
    if primary is not None:
        abs_delta = int(primary["abs_delta"])
        kind = str(primary["kind"])
        changed_count = sum(1 for row in deltas if int(row["abs_delta"]) > 500)
        if kind == "button":
            confidence = "high" if changed_count <= 1 else "medium"
        elif abs_delta > 10_000 and changed_count <= 2:
            confidence = "high"
        elif abs_delta > 1_000:
            confidence = "medium"
        else:
            confidence = "low"

    control_id = None if primary is None else str(primary["control_id"])
    generic_target = None
    xbox_target = None
    if control_id is not None:
        generic_target = next(
            (
                fields.get("target")
                for src, fields in generic_mapping.items()
                if src.endswith(f":{control_id}")
            ),
            None,
        )
        xbox_target = next(
            (
                fields.get("target")
                for src, fields in xbox_mapping.items()
                if src.endswith(f":{control_id}")
            ),
            None,
        )

    return {
        "step": step.key,
        "label": step.label,
        "expected_inferred_label": step.inferred_label,
        "primary_control_id": control_id,
        "primary_delta": primary,
        "generic_target": generic_target,
        "xbox_target": xbox_target,
        "confidence": confidence,
        "changed_controls": deltas[:8],
    }


def capture_step(
    serial: SerialPort,
    source: str,
    timeout: float,
    include_raw_report: bool,
) -> list[CommandRecord]:
    commands = []
    if include_raw_report:
        commands.append(f"GET_LAST_USB_REPORT {source}")
    commands.extend(
        [
            f"GET_NORMALIZED_INPUT {source}",
            "GET_GENERIC_GAMEPAD_MAPPING",
            "GET_XBOX_GAMEPAD_MAPPING",
        ]
    )
    return run_commands(serial, commands, timeout)


def write_transcript(
    path: pathlib.Path,
    sections: list[tuple[str, list[CommandRecord]]],
) -> dict[str, dict[str, int]]:
    line_refs: dict[str, dict[str, int]] = {}
    lines: list[str] = []
    for section, records in sections:
        lines.append(f"# {section}")
        line_refs[section] = {}
        for record in records:
            lines.append(f">> {record.command}")
            for response in record.responses or ["<no matching response>"]:
                line_number = len(lines) + 1
                lines.append(response)
                prefix = response.split(":", 1)[0] if ":" in response else response
                line_refs[section].setdefault(prefix, line_number)
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return line_refs


def write_markdown_draft(
    path: pathlib.Path,
    stamp: str,
    port: str,
    source_map: dict[str, str | None],
    summaries: list[dict[str, Any]],
    line_refs: dict[str, dict[str, int]],
    transcript_file: pathlib.Path,
) -> None:
    lines = [
        f"# Flight Pack Calibration Witness Draft - {stamp}",
        "",
        "Status: target evidence draft. Do not claim final calibration until reviewed.",
        "",
        f"- Port: `{port}`",
        f"- Transcript: `{transcript_file}`",
        f"- T.16000M source: `{source_map.get('stick') or 'not observed'}`",
        f"- TWCS/RJ12 source: `{source_map.get('twcs') or 'not observed'}`",
        "",
        "| Step | Primary Control | Generic Target | Xbox Target | Confidence | Evidence |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for summary in summaries:
        refs = line_refs.get(str(summary["step"]), {})
        evidence = ", ".join(
            f"{key} L{value}" for key, value in sorted(refs.items()) if key != "<no matching response>"
        )
        lines.append(
            "| {label} | `{control}` | `{generic}` | `{xbox}` | {confidence} | {evidence} |".format(
                label=summary["label"],
                control=summary.get("primary_control_id") or "none",
                generic=summary.get("generic_target") or "none",
                xbox=summary.get("xbox_target") or "none",
                confidence=summary.get("confidence") or "none",
                evidence=evidence or "none",
            )
        )
    lines.extend(
        [
            "",
            "Notes:",
            "- Inferred labels are based on observed movement deltas, not hardcoded truth.",
            "- RJ12 pedal labels remain provisional until left/right toe brake and rudder movements are reviewed.",
            "- Browser/game compatibility is out of scope for this calibration witness.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--out-dir", default="target/flight-pack-calibration")
    parser.add_argument("--assume-ready", action="store_true")
    parser.add_argument("--skip-raw-report", action="store_true")
    parser.add_argument(
        "--steps",
        default=",".join(step.key for step in STEPS),
        help="Comma-separated movement step keys, or 'all'.",
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
    run_dir = pathlib.Path(args.out_dir) / f"flight_pack_calibration_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    transcript_file = run_dir / "serial_transcript.txt"
    summary_file = run_dir / "summary.json"
    parsed_file = run_dir / "movement_deltas.json"
    markdown_file = run_dir / "calibration_evidence_draft.md"

    print("USB2BLE Flight Pack calibration witness")
    print(f"Transcript directory: {run_dir}")

    sections: list[tuple[str, list[CommandRecord]]] = []
    step_payloads: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    previous_by_source: dict[str, dict[str, dict[str, int | str]]] = {}

    serial = SerialPort(args.port)
    try:
        preflight = run_commands(serial, ["GET_USB_STATUS", "LIST_USB_DEVICES"], args.timeout)
        sections.append(("preflight", preflight))
        devices = parse_usb_devices(response_with_prefix(preflight, "USB_DEVICES:"))
        source_map = {
            "stick": source_for_device(devices, T16000_PID),
            "twcs": source_for_device(devices, TWCS_PID),
        }
        print(f"T.16000M source: {source_map['stick'] or 'not observed'}")
        print(f"TWCS/RJ12 source: {source_map['twcs'] or 'not observed'}")

        for index, step in enumerate(selected_steps, start=1):
            source = source_map.get(step.source_kind)
            if source is None:
                print(f"Skipping {step.label}: source {step.source_kind!r} not observed.")
                continue
            prompt(
                f"Step {index}/{len(selected_steps)}: {step.label}\n{step.instruction}",
                args.assume_ready,
            )
            records = capture_step(
                serial,
                source,
                args.timeout,
                include_raw_report=not args.skip_raw_report,
            )
            sections.append((step.key, records))
            normalized = parse_normalized(response_with_prefix(records, "NORMALIZED_INPUT:"))
            generic_mapping = parse_mapping_targets(
                response_with_prefix(records, "GENERIC_GAMEPAD_MAPPING:")
            )
            xbox_mapping = parse_mapping_targets(
                response_with_prefix(records, "XBOX_GAMEPAD_MAPPING:")
            )
            summary = changed_summary(
                step,
                previous_by_source.get(step.source_kind),
                normalized,
                generic_mapping,
                xbox_mapping,
            )
            previous_by_source[step.source_kind] = normalized
            summaries.append(summary)
            step_payloads.append(
                {
                    "step": step.__dict__,
                    "source": source,
                    "records": [record.to_json() for record in records],
                    "normalized": normalized,
                    "summary": summary,
                }
            )
    finally:
        serial.close()

    line_refs = write_transcript(transcript_file, sections)
    payload = {
        "captured_at": stamp,
        "port": args.port,
        "transcript": str(transcript_file),
        "parsed_deltas": str(parsed_file),
        "markdown_draft": str(markdown_file),
        "source_map": source_map,
        "summaries": summaries,
        "steps": step_payloads,
    }
    summary_file.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    parsed_file.write_text(
        json.dumps(summaries, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_markdown_draft(
        markdown_file,
        stamp,
        args.port,
        source_map,
        summaries,
        line_refs,
        transcript_file,
    )

    print()
    print("Inferred movement labels:")
    for summary in summaries:
        print(
            "  {label}: {control} -> generic={generic} xbox={xbox} confidence={confidence}".format(
                label=summary["label"],
                control=summary.get("primary_control_id") or "none",
                generic=summary.get("generic_target") or "none",
                xbox=summary.get("xbox_target") or "none",
                confidence=summary.get("confidence") or "none",
            )
        )
    print()
    print(f"Saved transcript: {transcript_file}")
    print(f"Saved parsed deltas: {parsed_file}")
    print(f"Saved summary: {summary_file}")
    print(f"Saved markdown draft: {markdown_file}")
    return 0 if summaries else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        raise SystemExit(130)
