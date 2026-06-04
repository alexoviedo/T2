#!/usr/bin/env python3
"""Inventory and safely remove USB2BLE-related Windows BLE cache devices."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import subprocess
from typing import Any


DEFAULT_OUT_DIR = pathlib.Path("target/windows-ble-cache")
USB2BLE_ADDRESS_RE = re.compile(r"907069070d7e", re.IGNORECASE)
USB2BLE_VID_PID_RE = re.compile(r"(?:VID&02)?303A_PID&400[12]|VID_303A|PID&400[12]", re.IGNORECASE)
XBOX_USB2BLE_RE = re.compile(r"045E_PID&0B13|VID_045E.*PID_0B13", re.IGNORECASE)
USB2BLE_NAME_RE = re.compile(r"USB2BLE|USB2BLE Gamepad U6", re.IGNORECASE)
XBOX_NAME_RE = re.compile(r"Xbox Wireless Controller", re.IGNORECASE)
NON_HEX_RE = re.compile(r"[^0-9a-f]", re.IGNORECASE)
SERVICE_NAME_RE = re.compile(
    r"Device Information Service|Bluetooth LE Generic Attribute Service|Generic Access Profile|Generic Attribute Profile|Bluetooth Low Energy GATT compliant HID device|HID-compliant game controller",
    re.IGNORECASE,
)


def utc_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_command(command: list[str], timeout: float = 45.0) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
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


def powershell_json(script: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    result = run_command(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ]
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


def collect_inventory() -> dict[str, Any]:
    scripts = {
        "bluetooth": "Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue | Select-Object Status,Class,FriendlyName,InstanceId,Problem | ConvertTo-Json -Depth 5",
        "hidclass": "Get-PnpDevice -Class HIDClass -ErrorAction SilentlyContinue | Select-Object Status,Class,FriendlyName,InstanceId,Problem | ConvertTo-Json -Depth 5",
        "named": "Get-PnpDevice -PresentOnly | Where-Object { $_.FriendlyName -match 'USB2BLE|Xbox|Gamepad|Controller|Bluetooth|HID' } | Select-Object Status,Class,FriendlyName,InstanceId,Problem | ConvertTo-Json -Depth 5",
        "cim_named": "Get-CimInstance Win32_PnPEntity | Where-Object { $_.Name -match 'USB2BLE|Xbox|Gamepad|Controller' -or $_.DeviceID -match '907069070D7E|303A.*4001|303A.*4002|045E.*0B13' } | Select-Object Name,Status,PNPClass,DeviceID,Manufacturer | ConvertTo-Json -Depth 5",
    }
    inventory: dict[str, Any] = {}
    for name, script in scripts.items():
        devices, command = powershell_json(script)
        inventory[name] = {"devices": devices, "command": command}
    return inventory


def device_text(device: dict[str, Any]) -> str:
    return " ".join(
        str(device.get(key) or "")
        for key in ("FriendlyName", "Name", "InstanceId", "DeviceID", "Class", "PNPClass", "Manufacturer")
    )


def address_fragment(address: str) -> str:
    return NON_HEX_RE.sub("", address).lower()


def normalize_associated_addresses(addresses: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    if not addresses:
        return ()
    fragments = sorted({address_fragment(address) for address in addresses if len(address_fragment(address)) == 12})
    return tuple(fragments)


def instance_id(device: dict[str, Any]) -> str:
    return str(device.get("InstanceId") or device.get("DeviceID") or "")


def candidate_reason(device: dict[str, Any], associated_addresses: tuple[str, ...] = ()) -> str | None:
    text = device_text(device)
    text_hex = NON_HEX_RE.sub("", text).lower()
    has_usb2ble_address = bool(USB2BLE_ADDRESS_RE.search(text))
    has_associated_address = any(fragment in text_hex for fragment in associated_addresses)
    has_usb2ble_vid_pid = bool(USB2BLE_VID_PID_RE.search(text))
    has_usb2ble_name = bool(USB2BLE_NAME_RE.search(text))
    has_xbox_name = bool(XBOX_NAME_RE.search(text))
    has_service_name = bool(SERVICE_NAME_RE.search(text))
    has_xbox_usb2ble = bool(XBOX_USB2BLE_RE.search(text) and has_usb2ble_address)
    if has_usb2ble_name:
        return "safe_name_match"
    if has_xbox_name and has_usb2ble_address:
        return "xbox_name_with_usb2ble_address"
    if has_xbox_name and has_associated_address:
        return "xbox_name_with_associated_address"
    if has_usb2ble_address and (has_usb2ble_vid_pid or has_service_name):
        return "usb2ble_address_and_hid_or_service_match"
    if has_associated_address and (has_usb2ble_vid_pid or has_service_name or bool(XBOX_USB2BLE_RE.search(text))):
        return "associated_address_and_hid_or_service_match"
    if has_xbox_usb2ble:
        return "xbox_vid_pid_with_usb2ble_address"
    return None


def find_candidates(inventory: dict[str, Any], associated_addresses: tuple[str, ...] = ()) -> list[dict[str, Any]]:
    by_instance: dict[str, dict[str, Any]] = {}
    for section_name, section in inventory.items():
        for device in section.get("devices", []):
            if not isinstance(device, dict):
                continue
            reason = candidate_reason(device, associated_addresses)
            inst = instance_id(device)
            if not reason or not inst:
                continue
            entry = dict(device)
            entry["source_section"] = section_name
            entry["match_reason"] = reason
            by_instance.setdefault(inst, entry)
    return sorted(by_instance.values(), key=removal_sort_key)


def removal_sort_key(device: dict[str, Any]) -> tuple[int, str]:
    inst = instance_id(device).upper()
    # Remove child service/HID nodes before the parent BTHLE root device.
    if inst.startswith("HID\\"):
        priority = 0
    elif inst.startswith("BTHLEDEVICE\\"):
        priority = 1
    elif inst.startswith("BTHLE\\DEV_"):
        priority = 2
    else:
        priority = 3
    return priority, inst


def remove_candidates(candidates: list[dict[str, Any]], dry_run: bool) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for device in candidates:
        inst = instance_id(device)
        record = {
            "instance_id": inst,
            "friendly_name": device.get("FriendlyName") or device.get("Name"),
            "match_reason": device.get("match_reason"),
            "dry_run": dry_run,
        }
        if dry_run:
            record["ok"] = True
            record["output"] = "dry run"
        else:
            removal = run_command(["pnputil", "/remove-device", inst], timeout=45.0)
            record["ok"] = bool(removal.get("ok"))
            record["returncode"] = removal.get("returncode")
            record["output"] = removal.get("output")
            record["command"] = removal.get("command")
        results.append(record)
    return results


def write_outputs(run_dir: pathlib.Path, summary: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (run_dir / "candidate_devices.json").write_text(
        json.dumps(summary["candidates"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Windows BLE Cache Witness",
        "",
        f"- Candidate count: {len(summary['candidates'])}",
        f"- Removal attempted: {summary['removal_attempted']}",
        f"- Dry run: {summary['dry_run']}",
        "",
        "## Candidates",
    ]
    for candidate in summary["candidates"]:
        lines.append(
            f"- {candidate.get('Class') or candidate.get('PNPClass')}: "
            f"{candidate.get('FriendlyName') or candidate.get('Name')} "
            f"`{instance_id(candidate)}` ({candidate.get('match_reason')})"
        )
    (run_dir / "operator_notes.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=pathlib.Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--remove", action="store_true", help="Remove matching USB2BLE-related devices with pnputil.")
    parser.add_argument("--dry-run", action="store_true", help="Do not remove devices; show candidates only.")
    parser.add_argument(
        "--associated-address",
        action="append",
        default=[],
        help="Additional BLE address known to belong to USB2BLE for this run, such as a derived static-random address.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = args.out_dir / f"windows_ble_cache_{utc_stamp()}"
    before = collect_inventory()
    associated_addresses = normalize_associated_addresses(args.associated_address)
    candidates = find_candidates(before, associated_addresses)
    removal_results = remove_candidates(candidates, dry_run=args.dry_run or not args.remove) if candidates else []
    after = collect_inventory() if args.remove and not args.dry_run else None
    summary = {
        "captured_at": utc_stamp(),
        "run_dir": str(run_dir),
        "dry_run": bool(args.dry_run or not args.remove),
        "associated_addresses": associated_addresses,
        "removal_attempted": bool(args.remove and not args.dry_run),
        "inventory_before": before,
        "candidates": candidates,
        "removal_results": removal_results,
        "inventory_after": after,
    }
    write_outputs(run_dir, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
