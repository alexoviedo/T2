#!/usr/bin/env python3
"""Check USB2BLE BLE HID compatibility profile snapshots."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any


PROFILE_PREFIX = "BLE_COMPAT_PROFILE_JSON:"


def builtin_profile(variant: str) -> dict[str, Any]:
    if variant == "generic_default":
        return {
            "active_persona": "generic_gamepad",
            "active_variant": "generic_default",
            "profile_family": "hogp_hids",
            "intended_host_target": "macos_chrome_proven_default",
            "advertising_active": None,
            "device_name": "USB2BLE Gamepad",
            "appearance": "0x03c4",
            "raw_advertisement_bytes_available": False,
            "primary_advertisement": {
                "fields": ["flags", "appearance", "complete_128bit_service_uuid"],
                "flags": "0x06",
                "complete_local_name": False,
                "uuids": ["1812"],
                "appearance": True,
                "estimated_payload_len": 25,
                "raw_bytes": "unavailable",
            },
            "scan_response": {
                "fields": ["complete_local_name"],
                "complete_local_name": True,
                "uuids": [],
                "estimated_payload_len": 17,
                "raw_bytes": "unavailable",
            },
            "hids": {
                "service_uuid": "1812",
                "service_present": "intended_by_esp_hidd_dev_init",
                "hid_information": "unknown",
                "report_map": "intended",
                "hid_control_point": "unknown",
                "protocol_mode": "unknown",
                "input_reports": 1,
                "output_reports": 0,
                "report_reference_descriptors": "unknown",
                "cccd_notify": "unknown",
            },
            "device_information_service": "unknown",
            "battery_service": "unknown",
            "report_map_len": 78,
            "report_ids": [1],
            "security": {
                "mode": "bond",
                "pairing_policy": "just_works",
                "io_capability": "none",
                "bond_storage_enabled": True,
                "bonds_present": False,
                "bond_count": "0",
            },
        }
    if variant == "generic_hogp_strict":
        profile = builtin_profile("generic_default")
        profile.update(
            {
                "active_variant": "generic_hogp_strict",
                "intended_host_target": "apple_ios_discovery_experiment",
                "primary_advertisement": {
                    "fields": ["flags", "appearance", "complete_local_name"],
                    "flags": "0x06",
                    "complete_local_name": True,
                    "uuids": [],
                    "appearance": True,
                    "estimated_payload_len": 24,
                    "raw_bytes": "unavailable",
                },
                "scan_response": {
                    "fields": ["complete_128bit_service_uuid"],
                    "complete_local_name": False,
                    "uuids": ["1812"],
                    "estimated_payload_len": 18,
                    "raw_bytes": "unavailable",
                },
            }
        )
        return profile
    if variant == "generic_unsigned_6axis":
        profile = builtin_profile("generic_default")
        profile.update(
            {
                "active_variant": "generic_unsigned_6axis",
                "intended_host_target": "macos_chrome_six_axis_delivery_experiment",
                "device_name": "USB2BLE Gamepad U6",
                "product_id": 0x4002,
                "report_map_len": 79,
                "scan_response": {
                    **profile["scan_response"],
                    "estimated_payload_len": 20,
                },
                "generic_reference": {
                    "axes_declared": ["x", "y", "z", "rx", "ry", "rz"],
                    "axis_value_type": "unsigned_16_centered",
                    "axis_logical_min": 0,
                    "axis_logical_max": 65535,
                    "axis_offsets": {
                        "x": 3,
                        "y": 5,
                        "z": 7,
                        "rx": 9,
                        "ry": 11,
                        "rz": 13,
                    },
                    "variant_purpose": "experimental host-compatible six-axis delivery check",
                },
            }
        )
        return profile
    if variant == "xbox_compatibility":
        profile = builtin_profile("generic_default")
        profile.update(
            {
                "active_persona": "xbox_wireless_controller",
                "active_variant": "xbox_compatibility",
                "intended_host_target": "xbox_like_hosts_experimental",
                "device_name": "Xbox Wireless Controller",
                "manufacturer": "Microsoft",
                "vendor_id": 0x045E,
                "product_id": 0x0B13,
                "report_map_len": 283,
                "report_ids": [1, 3],
                "hids": {
                    **profile["hids"],
                    "output_reports": 1,
                },
                "xbox_reference": {
                    "reference_model": "Xbox Wireless Controller model 1914 / Series X|S BLE",
                    "vid": "0x045e",
                    "pid": "0x0b13",
                    "input_report_id": 1,
                    "input_payload_len": 16,
                    "output_report_id": 3,
                    "output_payload_len": 8,
                    "report_map_len_expected": 283,
                    "stick_logical_min": 0,
                    "stick_logical_max": 65535,
                    "trigger_logical_min": 0,
                    "trigger_logical_max": 1023,
                    "hat_logical_min": 1,
                    "hat_logical_max": 8,
                    "hat_null": 0,
                    "button_count": 15,
                    "share_usage": "consumer_record",
                    "rumble_output_behavior": "safe_noop",
                },
            }
        )
        return profile
    if variant == "ios_keyboard_icade_fallback":
        return {
            "active_persona": "keyboard_icade",
            "active_variant": "ios_keyboard_icade_fallback",
            "profile_family": "keyboard_fallback",
            "intended_host_target": "ios_keyboard_fallback_planned",
            "implemented": False,
            "device_name": "USB2BLE iCade",
            "hids": {"service_uuid": "1812", "service_present": "not_implemented"},
            "report_map_len": 0,
            "report_ids": [],
            "security": {"mode": "unknown"},
        }
    raise ValueError(f"unknown built-in variant: {variant}")


def load_profile_text(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith(PROFILE_PREFIX):
        stripped = stripped[len(PROFILE_PREFIX) :]
    value = json.loads(stripped)
    if not isinstance(value, dict):
        raise ValueError("profile JSON is not an object")
    return value


def load_profile_file(path: pathlib.Path) -> dict[str, Any]:
    return load_profile_text(path.read_text(encoding="utf-8"))


def profiles_from_variant_witness(path: pathlib.Path) -> list[dict[str, Any]]:
    results_path = path / "variant_results.json"
    if not results_path.exists():
        results_path = path / "summary.json"
    value = json.loads(results_path.read_text(encoding="utf-8"))
    if isinstance(value, dict):
        results = value.get("variant_results", [])
    else:
        results = value
    profiles: list[dict[str, Any]] = []
    for result in results:
        if not isinstance(result, dict):
            continue
        profile_line = result.get("compat_profile_json")
        if isinstance(profile_line, str) and profile_line:
            profiles.append(load_profile_text(profile_line))
    return profiles


def status_for_presence(value: Any, *, intended_ok: bool = True) -> str:
    if value in (None, "", [], {}, "unknown", "unavailable"):
        return "unknown"
    if isinstance(value, str) and value.startswith("intended"):
        return "pass" if intended_ok else "unknown"
    return "pass"


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


def check_profile(profile: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    variant = str(profile.get("active_variant") or profile.get("variant") or "unknown")
    family = profile.get("profile_family")
    primary = profile.get("primary_advertisement") if isinstance(profile.get("primary_advertisement"), dict) else {}
    scan = profile.get("scan_response") if isinstance(profile.get("scan_response"), dict) else {}
    hids = profile.get("hids") if isinstance(profile.get("hids"), dict) else {}
    security = profile.get("security") if isinstance(profile.get("security"), dict) else {}
    implemented = profile.get("implemented", True) is not False
    primary_uuids = primary.get("uuids") or []
    scan_uuids = scan.get("uuids") or []
    all_uuids = {str(value).lower() for value in [*primary_uuids, *scan_uuids]}

    add_check(checks, "identity", "device_name", status_for_presence(profile.get("device_name")), profile.get("device_name"))
    add_check(checks, "gap", "appearance", status_for_presence(profile.get("appearance")), profile.get("appearance"), "0x03c4")
    add_check(checks, "gap", "flags", "pass" if primary.get("flags") == "0x06" else ("unknown" if not implemented else "fail"), primary.get("flags"), "0x06")
    add_check(
        checks,
        "gap",
        "hid_uuid_1812_advertised_or_scan_response",
        "pass" if "1812" in all_uuids else ("unknown" if not implemented else "fail"),
        sorted(all_uuids),
        "1812",
    )
    add_check(
        checks,
        "gap",
        "primary_payload_len",
        "pass" if int(primary.get("estimated_payload_len") or 0) <= 31 else "fail",
        primary.get("estimated_payload_len"),
        "<=31",
    )
    add_check(
        checks,
        "gap",
        "scan_response_payload_len",
        "pass" if int(scan.get("estimated_payload_len") or 0) <= 31 else "fail",
        scan.get("estimated_payload_len"),
        "<=31",
    )
    add_check(
        checks,
        "gap",
        "raw_advertisement_bytes",
        "pass" if profile.get("raw_advertisement_bytes_available") is True else "unknown",
        profile.get("raw_advertisement_bytes_available"),
        True,
        "target command reports intent; scanner import required for raw bytes",
    )
    expected_family = "keyboard_fallback" if variant == "ios_keyboard_icade_fallback" else "hogp_hids"
    add_check(checks, "profile", "family", "pass" if family == expected_family else "fail", family, expected_family)
    add_check(
        checks,
        "hids",
        "service_1812",
        "pass" if hids.get("service_uuid") == "1812" and hids.get("service_present") not in ("not_implemented", None) else ("unknown" if not implemented else "fail"),
        hids.get("service_present"),
        "1812 present/intended",
    )
    for item in ("hid_information", "report_map", "hid_control_point", "protocol_mode", "report_reference_descriptors", "cccd_notify"):
        add_check(checks, "hids", item, status_for_presence(hids.get(item)), hids.get(item))
    input_reports = hids.get("input_reports")
    add_check(checks, "hids", "input_report_characteristics", "pass" if isinstance(input_reports, int) and input_reports > 0 else "unknown", input_reports)
    output_reports = hids.get("output_reports")
    if variant == "xbox_compatibility":
        add_check(checks, "hids", "output_report_characteristics", "pass" if output_reports == 1 else "fail", output_reports, 1)
    else:
        add_check(checks, "hids", "output_report_characteristics", "pass" if output_reports == 0 else "unknown", output_reports, 0)
    add_check(checks, "gatt", "device_information_service", status_for_presence(profile.get("device_information_service")), profile.get("device_information_service"))
    add_check(checks, "gatt", "battery_service", status_for_presence(profile.get("battery_service")), profile.get("battery_service"))
    add_check(checks, "report_map", "length", "pass" if int(profile.get("report_map_len") or 0) > 0 else ("unknown" if not implemented else "fail"), profile.get("report_map_len"))
    add_check(checks, "report_map", "report_ids", "pass" if profile.get("report_ids") else ("unknown" if not implemented else "fail"), profile.get("report_ids"))
    add_check(checks, "security", "mode", status_for_presence(security.get("mode")), security.get("mode"))
    add_check(checks, "security", "pairing_policy", status_for_presence(security.get("pairing_policy")), security.get("pairing_policy"))
    add_check(checks, "security", "bond_storage_enabled", "pass" if security.get("bond_storage_enabled") is True else "unknown", security.get("bond_storage_enabled"))
    add_check(checks, "security", "bond_count", status_for_presence(security.get("bond_count")), security.get("bond_count"))

    summary = {
        "variant": variant,
        "persona": profile.get("active_persona"),
        "checks": checks,
        "fail_count": sum(1 for check in checks if check["status"] == "fail"),
        "unknown_count": sum(1 for check in checks if check["status"] == "unknown"),
        "pass_count": sum(1 for check in checks if check["status"] == "pass"),
    }
    return summary


def print_table(summaries: list[dict[str, Any]]) -> None:
    for summary in summaries:
        print(f"\nVariant: {summary['variant']}  Persona: {summary.get('persona')}")
        print("Layer      Check                                Status    Observed")
        print("---------  -----------------------------------  --------  ----------------")
        for check in summary["checks"]:
            observed = json.dumps(check["observed"], sort_keys=True)
            print(
                f"{check['layer'][:9]:9}  {check['item'][:35]:35}  "
                f"{check['status'][:8]:8}  {observed[:80]}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", action="append", default=[], help="Built-in variant to check")
    parser.add_argument("--profile-json", type=pathlib.Path, action="append", default=[])
    parser.add_argument("--variant-witness-dir", type=pathlib.Path)
    parser.add_argument("--out-json", type=pathlib.Path)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    profiles: list[dict[str, Any]] = []
    for variant in args.variant:
        profiles.append(builtin_profile(variant))
    for path in args.profile_json:
        profiles.append(load_profile_file(path))
    if args.variant_witness_dir:
        profiles.extend(profiles_from_variant_witness(args.variant_witness_dir))
    if not profiles:
        profiles = [
            builtin_profile("generic_default"),
            builtin_profile("generic_hogp_strict"),
            builtin_profile("generic_unsigned_6axis"),
        ]

    summaries = [check_profile(profile) for profile in profiles]
    result = {
        "profiles_checked": len(summaries),
        "summaries": summaries,
        "fail_count": sum(summary["fail_count"] for summary in summaries),
        "unknown_count": sum(summary["unknown_count"] for summary in summaries),
    }
    if args.out_json:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not args.quiet:
        print_table(summaries)
        print(json.dumps({"profiles_checked": result["profiles_checked"], "fail_count": result["fail_count"], "unknown_count": result["unknown_count"]}, indent=2))
    return 1 if result["fail_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
