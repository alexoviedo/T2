#!/usr/bin/env python3
"""Run BLE compatibility variant advertising diagnostics."""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import time
from typing import Any

from asap_demo_rehearsal import (
    CommandRecord,
    SerialPort,
    parse_semicolon_fields,
    response_with_prefix,
    run_commands,
    utc_stamp,
)
from generic_axis_exposure_witness import select_port


DEFAULT_OUT_DIR = "target/ble-compat"
DEFAULT_RESET_COMMAND = "espflash reset --chip esp32s3 --port {port} --non-interactive"
VARIANT_START_COMMANDS = {
    "generic_default": "START_BLE_GENERIC_GAMEPAD",
    "generic_hogp_strict": "START_BLE_GENERIC_GAMEPAD_VARIANT generic_hogp_strict",
    "xbox_compatibility": "START_BLE_XBOX_CONTROLLER",
}


def write_transcript(path: pathlib.Path, records: list[CommandRecord]) -> None:
    lines: list[str] = []
    for record in records:
        lines.append(f">> {record.command}")
        lines.extend(record.responses or ["<no matching response>"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def system_output(command: list[str]) -> str:
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    return result.stdout.strip()


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
    return {
        "command": command,
        "returncode": result.returncode,
        "output": result.stdout,
    }


def run_ble_probe(out_dir: pathlib.Path, seconds: float, device_name: str) -> dict[str, Any]:
    cmd = [
        sys.executable,
        "tools/ble_advertising_probe.py",
        "--out-dir",
        str(out_dir),
        "--duration-seconds",
        str(seconds),
        "--name",
        device_name,
    ]
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    summary_path = out_dir / "summary.json"
    summary: dict[str, Any] = {}
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    return {
        "command": cmd,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "summary": summary,
    }


def prompt_iphone(device_name: str, variant: str) -> tuple[str, str]:
    print()
    print("=" * 78)
    print(f"Variant `{variant}` is advertising as `{device_name}`.")
    print("On iPhone, open Settings > Bluetooth and wait 20 seconds.")
    print(f"Do you see `{device_name}` or a USB2BLE-like controller?")
    print("Type yes/no, then press Enter.")
    print("=" * 78)
    answer = input("> ").strip().lower()
    displayed = ""
    if answer.startswith("y"):
        print("Type the exact displayed Bluetooth name, then press Enter.")
        displayed = input("> ").strip()
    return ("yes" if answer.startswith("y") else "no", displayed)


def run_variant(
    *,
    port: str,
    variant: str,
    run_dir: pathlib.Path,
    timeout: float,
    probe_seconds: float,
    iphone_result: str,
    iphone_displayed_name: str,
) -> tuple[dict[str, Any], list[CommandRecord]]:
    records: list[CommandRecord] = []
    start_command = VARIANT_START_COMMANDS.get(variant)
    if start_command is None:
        return (
            {
                "variant": variant,
                "implemented": False,
                "error": "variant has no firmware start command",
            },
            records,
        )

    serial = SerialPort(port)
    try:
        records.extend(
            run_commands(
                serial,
                [
                    "GET_INFO",
                    "GET_STATUS",
                    "GET_USB_STATUS",
                    "LIST_USB_DEVICES",
                    "GET_CONFIG_STATUS",
                    "LIST_BLE_COMPAT_VARIANTS",
                    "FORGET_BLE_BONDS",
                    start_command,
                    "GET_STATUS",
                    "GET_BLE_ADVERTISING_INFO",
                    "GET_BLE_COMPAT_PROFILE",
                ],
                timeout,
            )
        )
    finally:
        serial.close()

    advertising = parse_semicolon_fields(response_with_prefix(records, "BLE_ADVERTISING_INFO:"))
    device_name = advertising.get("device_name") or "USB2BLE Gamepad"
    probe_dir = run_dir / f"mac_ble_probe_{variant}"
    probe_dir.mkdir(parents=True, exist_ok=True)
    mac_probe = run_ble_probe(probe_dir, probe_seconds, device_name)

    manual_result = iphone_result
    displayed_name = iphone_displayed_name
    if manual_result == "prompt":
        manual_result, displayed_name = prompt_iphone(device_name, variant)

    result = {
        "variant": variant,
        "implemented": True,
        "start_command": start_command,
        "target_advertising_info": advertising,
        "compat_profile_json": response_with_prefix(records, "BLE_COMPAT_PROFILE_JSON:"),
        "target_reported_advertising_active": advertising.get("state") == "Advertising",
        "target_reported_variant": advertising.get("variant"),
        "mac_probe_run_dir": str(probe_dir),
        "mac_saw_device_name": bool((mac_probe.get("summary") or {}).get("usb2ble_name_observed")),
        "mac_probe_returncode": mac_probe["returncode"],
        "iphone_manual_result": manual_result,
        "iphone_displayed_name": displayed_name,
    }
    return result, records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="auto", help="Serial port or 'auto'.")
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--variants", default="generic_default,generic_hogp_strict")
    parser.add_argument("--probe-seconds", type=float, default=20.0)
    parser.add_argument("--reset-command", default=DEFAULT_RESET_COMMAND)
    parser.add_argument("--post-reset-wait-seconds", type=float, default=8.0)
    parser.add_argument(
        "--iphone-result",
        choices=("prompt", "yes", "no", "unknown"),
        default="unknown",
        help="Use prompt to ask Alex per variant; yes/no/unknown keeps the run non-interactive.",
    )
    parser.add_argument("--iphone-displayed-name", default="")
    args = parser.parse_args()

    stamp = utc_stamp()
    run_dir = pathlib.Path(args.out_dir) / f"variant_witness_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    port = select_port(args.port, args.timeout)
    variants = [variant.strip() for variant in args.variants.split(",") if variant.strip()]
    all_records: list[CommandRecord] = []
    variant_results: list[dict[str, Any]] = []
    reset_results: list[dict[str, Any]] = []

    for index, variant in enumerate(variants):
        if index > 0:
            reset_results.append(reset_board(port, args.reset_command, args.post_reset_wait_seconds))
        result, records = run_variant(
            port=port,
            variant=variant,
            run_dir=run_dir,
            timeout=args.timeout,
            probe_seconds=args.probe_seconds,
            iphone_result=args.iphone_result,
            iphone_displayed_name=args.iphone_displayed_name,
        )
        variant_results.append(result)
        all_records.extend(records)

    errors = [
        f"{result['variant']}: target did not report requested variant"
        for result in variant_results
        if result.get("implemented")
        and result.get("target_reported_variant")
        and result.get("target_reported_variant") != result.get("variant")
    ]
    summary = {
        "captured_at": stamp,
        "run_dir": str(run_dir),
        "commit_sha": system_output(["git", "rev-parse", "HEAD"]),
        "git_dirty": bool(system_output(["git", "status", "--short"])),
        "selected_port": port,
        "variants_requested": variants,
        "variant_results": variant_results,
        "reset_results": reset_results,
        "iphone_discovered_any_variant": any(
            result.get("iphone_manual_result") == "yes" for result in variant_results
        ),
        "errors": errors,
        "claim_boundary": [
            "variant advertising diagnostics only",
            "not iPhone compatibility unless a real pair/Gamepad API run follows",
            "not broad host support",
            "not BLE bond persistence",
        ],
    }

    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (run_dir / "variant_results.json").write_text(json.dumps(variant_results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_transcript(run_dir / "serial_transcript.txt", all_records)
    (run_dir / "operator_notes.md").write_text(
        "# BLE Compatibility Variant Witness Notes\n\n"
        f"- Selected serial port: {port}\n"
        f"- Variants requested: {', '.join(variants)}\n"
        f"- iPhone prompt mode: {args.iphone_result}\n"
        "- This workflow records discoverability diagnostics only unless a host subsequently pairs and exposes input.\n",
        encoding="utf-8",
    )
    print(json.dumps({"run_dir": str(run_dir), "errors": errors, "variant_results": variant_results}, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        raise SystemExit(130)
