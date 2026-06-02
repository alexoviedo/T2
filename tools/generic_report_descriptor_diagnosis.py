#!/usr/bin/env python3
"""Decode Generic Gamepad HID report layout and correlate delivery artifacts."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
PERSONAS_SOURCE = ROOT / "crates/usb2ble-personas/src/lib.rs"
DEFAULT_DELIVERY_ROOT = ROOT / "target/generic-hid-delivery-diagnosis"
DEFAULT_OUT_ROOT = ROOT / "target/generic-report-descriptor-diagnosis"

USAGE_NAMES = {
    (0x01, 0x30): "x",
    (0x01, 0x31): "y",
    (0x01, 0x32): "z",
    (0x01, 0x33): "rx",
    (0x01, 0x34): "ry",
    (0x01, 0x35): "rz",
    (0x01, 0x39): "hat",
}

SCENARIO_AXIS = {
    "stick_left": "x",
    "stick_right": "x",
    "stick_forward": "y",
    "stick_back": "y",
    "throttle_max": "z",
    "throttle_min": "z",
    "rudder_left": "rx",
    "rudder_right": "rx",
    "left_toe_pressed": "ry",
    "left_toe_released": "ry",
    "right_toe_pressed": "rz",
    "right_toe_released": "rz",
}


def utc_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def latest_delivery_run() -> pathlib.Path:
    runs = sorted(DEFAULT_DELIVERY_ROOT.glob("generic_hid_delivery_*"))
    if not runs:
        raise FileNotFoundError("no generic HID delivery diagnosis artifacts found")
    return runs[-1]


REPORT_MAP_CONSTS = {
    "generic_default": "GENERIC_GAMEPAD_REPORT_MAP",
    "generic_hogp_strict": "GENERIC_GAMEPAD_REPORT_MAP",
    "generic_unsigned_6axis": "GENERIC_UNSIGNED_6AXIS_REPORT_MAP",
}


def extract_generic_report_map(
    source: pathlib.Path = PERSONAS_SOURCE,
    variant: str = "generic_default",
) -> list[int]:
    const_name = REPORT_MAP_CONSTS.get(variant)
    if const_name is None:
        raise ValueError(f"unsupported Generic report-map variant: {variant}")
    text = source.read_text(encoding="utf-8")
    match = re.search(
        rf"const\s+{re.escape(const_name)}:\s*&\[u8\]\s*=\s*&\[(?P<body>.*?)\];",
        text,
        re.S,
    )
    if not match:
        raise ValueError(f"could not locate {const_name} in {source}")
    body = re.sub(r"//.*", "", match.group("body"))
    values: list[int] = []
    for token in re.findall(r"0x[0-9a-fA-F]+|\b\d+\b", body):
        values.append(int(token, 0))
    return values


def signed_value(payload: bytes) -> int:
    if not payload:
        return 0
    return int.from_bytes(payload, "little", signed=True)


def unsigned_value(payload: bytes) -> int:
    if not payload:
        return 0
    return int.from_bytes(payload, "little", signed=False)


def usage_sequence(local: dict[str, Any], count: int) -> list[int | None]:
    usages = list(local.get("usages", []))
    if len(usages) >= count:
        return usages[:count]
    if local.get("usage_minimum") is not None and local.get("usage_maximum") is not None:
        start = int(local["usage_minimum"])
        end = int(local["usage_maximum"])
        return list(range(start, min(end, start + count - 1) + 1)) + [None] * max(0, count - (end - start + 1))
    return usages + [None] * max(0, count - len(usages))


def parse_report_map(report_map: list[int]) -> dict[str, Any]:
    global_state: dict[str, Any] = {
        "usage_page": None,
        "logical_min": None,
        "logical_max": None,
        "report_size": 0,
        "report_count": 0,
        "report_id": 0,
    }
    local: dict[str, Any] = {"usages": []}
    fields: list[dict[str, Any]] = []
    collections: list[dict[str, Any]] = []
    bit_offsets: dict[int, int] = {0: 0}
    report_ids: set[int] = set()
    i = 0
    while i < len(report_map):
        prefix = report_map[i]
        i += 1
        if prefix == 0xFE:
            if i + 2 > len(report_map):
                break
            length = report_map[i]
            i += 2 + length
            continue
        size_code = prefix & 0x03
        size = 4 if size_code == 3 else size_code
        item_type = (prefix >> 2) & 0x03
        tag = (prefix >> 4) & 0x0F
        payload = bytes(report_map[i : i + size])
        i += size

        if item_type == 1:  # Global
            if tag == 0x0:
                global_state["usage_page"] = unsigned_value(payload)
            elif tag == 0x1:
                global_state["logical_min"] = signed_value(payload)
            elif tag == 0x2:
                global_state["logical_max"] = signed_value(payload)
            elif tag == 0x7:
                global_state["report_size"] = unsigned_value(payload)
            elif tag == 0x8:
                report_id = unsigned_value(payload)
                global_state["report_id"] = report_id
                report_ids.add(report_id)
                bit_offsets.setdefault(report_id, 0)
            elif tag == 0x9:
                global_state["report_count"] = unsigned_value(payload)
        elif item_type == 2:  # Local
            if tag == 0x0:
                local.setdefault("usages", []).append(unsigned_value(payload))
            elif tag == 0x1:
                local["usage_minimum"] = unsigned_value(payload)
            elif tag == 0x2:
                local["usage_maximum"] = unsigned_value(payload)
        elif item_type == 0:  # Main
            if tag == 0x8:  # Input
                flags = unsigned_value(payload)
                report_id = int(global_state.get("report_id") or 0)
                report_size = int(global_state.get("report_size") or 0)
                report_count = int(global_state.get("report_count") or 0)
                usage_page = global_state.get("usage_page")
                logical_min = global_state.get("logical_min")
                logical_max = global_state.get("logical_max")
                const = bool(flags & 0x01)
                variable = bool(flags & 0x02)
                usages = usage_sequence(local, report_count) if variable else [local.get("usages", [None])[0]] * report_count
                for index in range(report_count):
                    usage = usages[index] if index < len(usages) else None
                    bit_offset = bit_offsets.setdefault(report_id, 0)
                    fields.append(
                        {
                            "kind": "input",
                            "report_id": report_id,
                            "bit_offset": bit_offset,
                            "bit_size": report_size,
                            "byte_offset": bit_offset // 8,
                            "bit_in_byte": bit_offset % 8,
                            "usage_page": usage_page,
                            "usage": usage,
                            "usage_name": USAGE_NAMES.get((usage_page, usage), f"usage_{usage}" if usage is not None else "padding"),
                            "logical_min": logical_min,
                            "logical_max": logical_max,
                            "constant": const,
                            "variable": variable,
                            "flags": flags,
                        }
                    )
                    bit_offsets[report_id] = bit_offset + report_size
                local = {"usages": []}
            elif tag == 0xA:  # Collection
                collections.append(
                    {
                        "usage_page": global_state.get("usage_page"),
                        "usage": local.get("usages", [None])[-1] if local.get("usages") else None,
                        "collection_type": unsigned_value(payload),
                    }
                )
                local = {"usages": []}
            elif tag == 0xC:  # End Collection
                local = {"usages": []}
    return {
        "report_ids": sorted(report_ids),
        "collections": collections,
        "fields": fields,
        "input_report_bits": {str(report_id): bits for report_id, bits in sorted(bit_offsets.items())},
        "input_report_bytes": {str(report_id): (bits + 7) // 8 for report_id, bits in sorted(bit_offsets.items())},
    }


def extract_bits(data: bytes, bit_offset: int, bit_size: int) -> int:
    value = int.from_bytes(data, "little", signed=False)
    mask = (1 << bit_size) - 1
    return (value >> bit_offset) & mask


def sign_extend(value: int, bit_size: int) -> int:
    sign_bit = 1 << (bit_size - 1)
    return (value ^ sign_bit) - sign_bit


def decode_report(report_hex: str | None, fields: list[dict[str, Any]]) -> dict[str, Any]:
    if not report_hex:
        return {}
    data = bytes.fromhex(report_hex)
    decoded: dict[str, Any] = {}
    for field in fields:
        if field.get("kind") != "input" or field.get("constant"):
            continue
        name = str(field.get("usage_name"))
        raw = extract_bits(data, int(field["bit_offset"]), int(field["bit_size"]))
        logical_min = field.get("logical_min")
        value = sign_extend(raw, int(field["bit_size"])) if isinstance(logical_min, int) and logical_min < 0 else raw
        decoded[name] = {
            "raw": raw,
            "value": value,
            "usage_page": field.get("usage_page"),
            "usage": field.get("usage"),
            "byte_offset": field.get("byte_offset"),
            "bit_offset": field.get("bit_offset"),
            "bit_size": field.get("bit_size"),
        }
    return decoded


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


def parse_iso(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def rows_in_window(rows: list[dict[str, Any]], start: str | None, end: str | None) -> list[dict[str, Any]]:
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


def load_delivery_run(run_dir: pathlib.Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    scenarios = json.loads((run_dir / "scenario_results.json").read_text(encoding="utf-8"))
    hid_file = pathlib.Path(summary["hid_event_file"]) if summary.get("hid_event_file") else None
    hid_rows = load_jsonl(hid_file) if hid_file else []
    return summary, scenarios, hid_rows


def correlate_scenarios(
    scenarios: list[dict[str, Any]],
    hid_rows: list[dict[str, Any]],
    fields: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    events = [row for row in hid_rows if row.get("type") == "input_value"]
    elements = [row for row in hid_rows if row.get("type") == "element"]
    element_usages = {
        (element.get("usage_page"), element.get("usage"))
        for element in elements
        if element.get("usage_page") is not None and element.get("usage") is not None
    }
    correlated: list[dict[str, Any]] = []
    for scenario in scenarios:
        axis = SCENARIO_AXIS.get(str(scenario.get("scenario")))
        active_decoded = decode_report(scenario.get("active_report_bytes"), fields)
        baseline_decoded = decode_report(scenario.get("baseline_report_bytes"), fields)
        field = active_decoded.get(axis or "") if axis else None
        usage_key = (field.get("usage_page"), field.get("usage")) if isinstance(field, dict) else (None, None)
        matching_events = [
            event
            for event in rows_in_window(events, scenario.get("active_start"), scenario.get("active_end"))
            if (event.get("usage_page"), event.get("usage")) == usage_key
        ]
        baseline_value = baseline_decoded.get(axis or "", {}).get("value") if axis else None
        active_value = active_decoded.get(axis or "", {}).get("value") if axis else None
        correlated.append(
            {
                "scenario": scenario.get("scenario"),
                "expected_axis": axis,
                "usage_page": usage_key[0],
                "usage": usage_key[1],
                "descriptor_element_present_in_probe": usage_key in element_usages,
                "baseline_value": baseline_value,
                "active_value": active_value,
                "report_value_changed": baseline_value != active_value,
                "hid_event_count_for_usage": len(matching_events),
                "hid_event_values_for_usage": [event.get("integer_value") for event in matching_events],
                "chrome_failure_layer": scenario.get("failure_layer"),
                "chrome_axes_changed": scenario.get("chrome_axes_changed"),
                "chrome_timestamp_changed": scenario.get("chrome_timestamp_changed"),
            }
        )
    return correlated


def classify_root_cause(layout: dict[str, Any], correlations: list[dict[str, Any]]) -> dict[str, Any]:
    axis_fields = {
        field.get("usage_name"): field
        for field in layout["fields"]
        if field.get("usage_name") in {"x", "y", "z", "rx", "ry", "rz"} and not field.get("constant")
    }
    missing_descriptor = sorted(set(["x", "y", "z", "rx", "ry", "rz"]) - set(axis_fields))
    changed_without_hid = [
        row["scenario"]
        for row in correlations
        if row.get("report_value_changed") and row.get("hid_event_count_for_usage") == 0
    ]
    changed_with_hid_no_chrome = [
        row["scenario"]
        for row in correlations
        if row.get("report_value_changed")
        and row.get("hid_event_count_for_usage", 0) > 0
        and row.get("chrome_failure_layer") == "chrome_gamepad"
    ]
    missing_probe_elements = [
        row["scenario"]
        for row in correlations
        if row.get("report_value_changed") and not row.get("descriptor_element_present_in_probe")
    ]
    if missing_descriptor:
        category = "A"
        reason = "descriptor_missing_axis_fields"
    elif missing_probe_elements:
        category = "D"
        reason = "macos_probe_did_not_enumerate_expected_elements"
    elif changed_without_hid:
        category = "C"
        reason = "descriptor_and_report_decode_match_but_macos_hid_did_not_emit_events"
    elif changed_with_hid_no_chrome:
        category = "E"
        reason = "macos_hid_events_seen_but_chrome_did_not_surface_updates"
    else:
        category = "G"
        reason = "no_unambiguous_failure_in_artifact"
    return {
        "category": category,
        "reason": reason,
        "missing_descriptor_axes": missing_descriptor,
        "changed_without_hid": changed_without_hid,
        "changed_with_hid_no_chrome": changed_with_hid_no_chrome,
        "missing_probe_elements": missing_probe_elements,
    }


def write_diagnosis_md(
    path: pathlib.Path,
    delivery_run: pathlib.Path,
    root_cause: dict[str, Any],
    correlations: list[dict[str, Any]],
) -> None:
    lines = [
        "# Generic Report Descriptor Diagnosis",
        "",
        f"- Delivery artifact: `{delivery_run}`",
        f"- Root-cause category: `{root_cause['category']}` (`{root_cause['reason']}`)",
        "",
        "## Scenario Correlation",
        "",
        "| Scenario | Axis | Decoded baseline -> active | HID element | HID events | Chrome layer |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    for row in correlations:
        lines.append(
            "| {scenario} | {axis} | {before} -> {after} | {element} | {events} | {layer} |".format(
                scenario=row.get("scenario"),
                axis=row.get("expected_axis"),
                before=row.get("baseline_value"),
                after=row.get("active_value"),
                element="yes" if row.get("descriptor_element_present_in_probe") else "no/unknown",
                events=row.get("hid_event_count_for_usage"),
                layer=row.get("chrome_failure_layer"),
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "Category A means the descriptor does not declare the intended axis.",
            "Category B would mean the encoder writes the wrong offset/order; this tool reports that as changed decoded values on the wrong field.",
            "Category C means descriptor and decoded report values look correct, but macOS HID did not emit value callbacks for changed fields.",
            "Category D means the macOS probe did not enumerate the expected elements, so probe visibility is suspect.",
            "Category E means macOS HID delivered events but Chrome did not surface them.",
            "Category G means the artifact is inconclusive.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delivery-run", type=pathlib.Path)
    parser.add_argument("--out-dir", type=pathlib.Path, default=DEFAULT_OUT_ROOT)
    parser.add_argument("--variant", default="generic_default")
    args = parser.parse_args()

    delivery_run = args.delivery_run or latest_delivery_run()
    stamp = utc_stamp()
    variant_safe = args.variant.replace("/", "_").replace(" ", "_")
    run_dir = args.out_dir / f"generic_report_descriptor_{variant_safe}_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    report_map = extract_generic_report_map(variant=args.variant)
    layout = parse_report_map(report_map)
    summary, scenarios, hid_rows = load_delivery_run(delivery_run)
    correlations = correlate_scenarios(scenarios, hid_rows, layout["fields"])
    root_cause = classify_root_cause(layout, correlations)

    report_layout = {
        "source": str(PERSONAS_SOURCE),
        "variant": args.variant,
        "report_map_len": len(report_map),
        "report_map_hex": "".join(f"{byte:02x}" for byte in report_map),
        **layout,
    }
    hid_event_correlation = {
        "delivery_run": str(delivery_run),
        "delivery_summary": {
            "failure_layers": summary.get("failure_layers"),
            "scenario_count": summary.get("scenario_count"),
            "pass_count": summary.get("pass_count"),
        },
        "root_cause": root_cause,
        "scenario_correlations": correlations,
    }
    (run_dir / "report_layout.json").write_text(json.dumps(report_layout, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (run_dir / "scenario_report_decode.json").write_text(json.dumps(correlations, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (run_dir / "hid_event_correlation.json").write_text(json.dumps(hid_event_correlation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary_out = {
        "captured_at": stamp,
        "run_dir": str(run_dir),
        "variant": args.variant,
        "delivery_run": str(delivery_run),
        "root_cause": root_cause,
        "axis_fields": [
            field
            for field in layout["fields"]
            if field.get("usage_name") in {"x", "y", "z", "rx", "ry", "rz"}
        ],
    }
    (run_dir / "summary.json").write_text(json.dumps(summary_out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_diagnosis_md(run_dir / "diagnosis.md", delivery_run, root_cause, correlations)
    print(json.dumps(summary_out, indent=2, sort_keys=True))
    return 0 if root_cause["category"] in {"C", "E", "G"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
