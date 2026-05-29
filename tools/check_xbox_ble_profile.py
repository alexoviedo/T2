#!/usr/bin/env python3
"""Check USB2BLE's Xbox Series X|S BLE compatibility profile shape."""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from typing import Any

from check_ble_hid_profile import (
    builtin_profile,
    load_profile_file,
    load_profile_text,
    profiles_from_variant_witness,
)


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "crates/usb2ble-personas/src/lib.rs"

XBOX_REFERENCE = {
    "vid": 0x045E,
    "pid": 0x0B13,
    "device_name": "Xbox Wireless Controller",
    "appearance": "0x03c4",
    "report_map_len": 283,
    "input_report_id": 1,
    "input_payload_len": 16,
    "output_report_id": 3,
    "output_payload_len": 8,
    "stick_logical_min": 0,
    "stick_logical_max": 65_535,
    "trigger_logical_min": 0,
    "trigger_logical_max": 1_023,
    "hat_logical_min": 1,
    "hat_logical_max": 8,
    "hat_null": 0,
    "button_count": 15,
}

SOURCE_PATTERNS = {
    "gamepad_application_collection": [0x05, 0x01, 0x09, 0x05, 0xA1, 0x01],
    "report_id_1": [0x85, 0x01],
    "left_stick_xy_usages": [0x09, 0x30, 0x09, 0x31],
    "right_stick_z_rz_usages": [0x09, 0x32, 0x09, 0x35],
    "unsigned_16bit_axis_range": [0x15, 0x00, 0x27, 0xFF, 0xFF, 0x00, 0x00],
    "brake_usage": [0x05, 0x02, 0x09, 0xC5],
    "accelerator_usage": [0x05, 0x02, 0x09, 0xC4],
    "ten_bit_trigger_range": [0x15, 0x00, 0x26, 0xFF, 0x03, 0x95, 0x01, 0x75, 0x0A],
    "hat_1_to_8_null": [0x09, 0x39, 0x15, 0x01, 0x25, 0x08],
    "fifteen_buttons": [0x05, 0x09, 0x19, 0x01, 0x29, 0x0F],
    "consumer_record_share": [0x05, 0x0C, 0x0A, 0xB2, 0x00],
    "report_id_3_output": [0x05, 0x0F, 0x09, 0x21, 0x85, 0x03],
}


def extract_xbox_report_map(source_path: pathlib.Path = DEFAULT_SOURCE) -> list[int]:
    text = source_path.read_text(encoding="utf-8")
    match = re.search(
        r"const XBOX_WIRELESS_CONTROLLER_REPORT_MAP: &\[u8\] = &\[(.*?)\n\];",
        text,
        re.S,
    )
    if not match:
        raise ValueError(f"could not find Xbox report map in {source_path}")
    values = [int(token, 0) for token in re.findall(r"0x[0-9a-fA-F]+|\b\d+\b", match.group(1))]
    if any(value < 0 or value > 255 for value in values):
        raise ValueError("Xbox report map contains non-byte values")
    return values


def contains_sequence(haystack: list[int], needle: list[int]) -> bool:
    return any(haystack[index : index + len(needle)] == needle for index in range(len(haystack) - len(needle) + 1))


def add_check(
    checks: list[dict[str, Any]],
    layer: str,
    item: str,
    status: str,
    observed: Any,
    expected: Any = None,
    note: str = "",
) -> None:
    checks.append(
        {
            "layer": layer,
            "item": item,
            "status": status,
            "observed": observed,
            "expected": expected,
            "note": note,
        }
    )


def normalize_hex(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, int):
        return f"0x{value:04x}"
    text = str(value).lower()
    if text.startswith("0x"):
        return f"0x{int(text, 16):04x}"
    return text


def ref_value(profile: dict[str, Any], key: str) -> Any:
    xbox_ref = profile.get("xbox_reference")
    if isinstance(xbox_ref, dict) and key in xbox_ref:
        return xbox_ref[key]
    return profile.get(key)


def check_profile(profile: dict[str, Any], report_map: list[int] | None = None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    hids = profile.get("hids") if isinstance(profile.get("hids"), dict) else {}

    add_check(checks, "identity", "persona", "pass" if profile.get("active_persona") == "xbox_wireless_controller" else "fail", profile.get("active_persona"), "xbox_wireless_controller")
    add_check(checks, "identity", "variant", "pass" if profile.get("active_variant") == "xbox_compatibility" else "fail", profile.get("active_variant"), "xbox_compatibility")
    add_check(checks, "identity", "device_name", "pass" if profile.get("device_name") == XBOX_REFERENCE["device_name"] else "fail", profile.get("device_name"), XBOX_REFERENCE["device_name"])
    add_check(checks, "identity", "vid", "pass" if int(profile.get("vendor_id") or 0) == XBOX_REFERENCE["vid"] else "fail", profile.get("vendor_id"), "0x045e")
    add_check(checks, "identity", "pid", "pass" if int(profile.get("product_id") or 0) == XBOX_REFERENCE["pid"] else "fail", profile.get("product_id"), "0x0b13")
    add_check(checks, "gap", "appearance", "pass" if normalize_hex(profile.get("appearance")) == XBOX_REFERENCE["appearance"] else "fail", profile.get("appearance"), XBOX_REFERENCE["appearance"])

    report_ids = profile.get("report_ids") or []
    add_check(checks, "report", "input_report_id_1", "pass" if XBOX_REFERENCE["input_report_id"] in report_ids else "fail", report_ids, 1)
    add_check(checks, "report", "output_report_id_3", "pass" if XBOX_REFERENCE["output_report_id"] in report_ids else "fail", report_ids, 3)
    add_check(checks, "report", "report_map_len", "pass" if int(profile.get("report_map_len") or 0) == XBOX_REFERENCE["report_map_len"] else "fail", profile.get("report_map_len"), XBOX_REFERENCE["report_map_len"])
    add_check(checks, "report", "input_payload_len", "pass" if ref_value(profile, "input_payload_len") == XBOX_REFERENCE["input_payload_len"] else "fail", ref_value(profile, "input_payload_len"), XBOX_REFERENCE["input_payload_len"])
    add_check(checks, "report", "output_payload_len", "pass" if ref_value(profile, "output_payload_len") == XBOX_REFERENCE["output_payload_len"] else "fail", ref_value(profile, "output_payload_len"), XBOX_REFERENCE["output_payload_len"])
    add_check(checks, "report", "stick_logical_range", "pass" if ref_value(profile, "stick_logical_max") == XBOX_REFERENCE["stick_logical_max"] else "fail", [ref_value(profile, "stick_logical_min"), ref_value(profile, "stick_logical_max")], [0, 65535])
    add_check(checks, "report", "trigger_logical_range", "pass" if ref_value(profile, "trigger_logical_max") == XBOX_REFERENCE["trigger_logical_max"] else "fail", [ref_value(profile, "trigger_logical_min"), ref_value(profile, "trigger_logical_max")], [0, 1023])
    add_check(checks, "report", "hat_range", "pass" if [ref_value(profile, "hat_logical_min"), ref_value(profile, "hat_logical_max"), ref_value(profile, "hat_null")] == [1, 8, 0] else "fail", [ref_value(profile, "hat_logical_min"), ref_value(profile, "hat_logical_max"), ref_value(profile, "hat_null")], [1, 8, 0])
    add_check(checks, "report", "button_count", "pass" if ref_value(profile, "button_count") == XBOX_REFERENCE["button_count"] else "fail", ref_value(profile, "button_count"), XBOX_REFERENCE["button_count"])
    add_check(checks, "report", "share_record", "pass" if ref_value(profile, "share_usage") == "consumer_record" else "fail", ref_value(profile, "share_usage"), "consumer_record")
    add_check(checks, "hids", "input_reports", "pass" if hids.get("input_reports") == 1 else "fail", hids.get("input_reports"), 1)
    add_check(checks, "hids", "output_reports", "pass" if hids.get("output_reports") == 1 else "fail", hids.get("output_reports"), 1)

    if report_map is None:
        add_check(checks, "source", "report_map_bytes", "warn", "not provided", "source parse")
    else:
        for item, pattern in SOURCE_PATTERNS.items():
            add_check(
                checks,
                "source",
                item,
                "pass" if contains_sequence(report_map, pattern) else "fail",
                "present" if contains_sequence(report_map, pattern) else "missing",
                [f"0x{byte:02x}" for byte in pattern],
            )

    return {
        "profile": profile.get("active_variant"),
        "checks": checks,
        "pass_count": sum(1 for check in checks if check["status"] == "pass"),
        "warn_count": sum(1 for check in checks if check["status"] == "warn"),
        "fail_count": sum(1 for check in checks if check["status"] == "fail"),
    }


def profiles_from_args(args: argparse.Namespace) -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    if args.builtin:
        profiles.append(builtin_profile("xbox_compatibility"))
    for path in args.profile_json:
        profiles.append(load_profile_file(path))
    if args.variant_witness_dir:
        for profile in profiles_from_variant_witness(args.variant_witness_dir):
            if profile.get("active_persona") == "xbox_wireless_controller":
                profiles.append(profile)
    if args.profile_text:
        profiles.append(load_profile_text(args.profile_text))
    if not profiles:
        profiles.append(builtin_profile("xbox_compatibility"))
    return profiles


def print_table(summaries: list[dict[str, Any]]) -> None:
    for summary in summaries:
        print(f"\nXbox profile: {summary['profile']}")
        print("Layer      Check                         Status    Observed")
        print("---------  ----------------------------  --------  ----------------")
        for check in summary["checks"]:
            observed = json.dumps(check["observed"], sort_keys=True)
            print(
                f"{check['layer'][:9]:9}  {check['item'][:28]:28}  "
                f"{check['status'][:8]:8}  {observed[:80]}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-rust", type=pathlib.Path, default=DEFAULT_SOURCE)
    parser.add_argument("--no-source", action="store_true")
    parser.add_argument("--builtin", action="store_true", help="Check source-defined built-in Xbox profile")
    parser.add_argument("--profile-json", type=pathlib.Path, action="append", default=[])
    parser.add_argument("--variant-witness-dir", type=pathlib.Path)
    parser.add_argument("--profile-text")
    parser.add_argument("--out-json", type=pathlib.Path)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    report_map = None if args.no_source else extract_xbox_report_map(args.source_rust)
    summaries = [check_profile(profile, report_map) for profile in profiles_from_args(args)]
    result = {
        "profiles_checked": len(summaries),
        "summaries": summaries,
        "fail_count": sum(summary["fail_count"] for summary in summaries),
        "warn_count": sum(summary["warn_count"] for summary in summaries),
    }
    if args.out_json:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not args.quiet:
        print_table(summaries)
        print(
            json.dumps(
                {
                    "profiles_checked": result["profiles_checked"],
                    "fail_count": result["fail_count"],
                    "warn_count": result["warn_count"],
                },
                indent=2,
            )
        )
    return 1 if result["fail_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
