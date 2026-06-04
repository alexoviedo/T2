#!/usr/bin/env python3
"""Best-effort Windows BLE pairing witness.

This tool discovers a BLE advertiser with the native Windows watcher, resolves
the advertised address through WinRT Bluetooth APIs, optionally attempts pairing,
and captures Windows PnP/HID/Bluetooth state. It never treats discovery as
pairing success.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import subprocess
import sys
from typing import Any

import windows_ble_advertising_watcher as ble_watcher


DEFAULT_OUT_DIR = pathlib.Path("target/windows-bluetooth-pairing")


def utc_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_command(command: list[str], timeout: float = 25.0) -> dict[str, Any]:
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


def powershell_json(script: str) -> dict[str, Any]:
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        script,
    ]
    result = run_command(command)
    text = str(result.get("output", "")).strip()
    parsed: Any = []
    if text:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            result["json_error"] = "could not parse PowerShell JSON output"
    if isinstance(parsed, dict):
        devices = [parsed]
    elif isinstance(parsed, list):
        devices = [item for item in parsed if isinstance(item, dict)]
    else:
        devices = []
    return {"devices": devices, "command": result}


def collect_windows_inventory() -> dict[str, Any]:
    scripts = {
        "bluetooth": "Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue | Select-Object Status,Class,FriendlyName,InstanceId | ConvertTo-Json -Depth 5",
        "hidclass": "Get-PnpDevice -Class HIDClass -ErrorAction SilentlyContinue | Select-Object Status,Class,FriendlyName,InstanceId | ConvertTo-Json -Depth 5",
        "named": "Get-PnpDevice -PresentOnly | Where-Object { $_.FriendlyName -match 'USB2BLE|Xbox|Game|Controller|Bluetooth|HID' } | Select-Object Status,Class,FriendlyName,InstanceId | ConvertTo-Json -Depth 5",
    }
    return {name: powershell_json(script) for name, script in scripts.items()}


def record_matches_name(record: dict[str, Any], name: str) -> bool:
    expected = name.lower()
    local_name = str(record.get("local_name") or "").lower()
    return local_name == expected or expected in local_name


def summarize_name_records(records: list[dict[str, Any]], name: str) -> dict[str, Any]:
    matches = [record for record in records if record_matches_name(record, name)]
    rssis = [record.get("rssi_dbm") for record in matches if isinstance(record.get("rssi_dbm"), int)]
    addresses = sorted({str(record.get("bluetooth_address")) for record in matches if record.get("bluetooth_address")})
    service_uuids = sorted(
        {
            str(uuid)
            for record in matches
            for uuid in (record.get("service_uuids") or [])
        }
    )
    return {
        "expected_name": name,
        "seen": bool(matches),
        "match_count": len(matches),
        "addresses": addresses,
        "service_uuids": service_uuids,
        "rssi_min": min(rssis) if rssis else None,
        "rssi_max": max(rssis) if rssis else None,
    }


def parse_ble_address(address: str) -> int:
    return int(address.replace(":", "").replace("-", ""), 16)


def enum_text(value: Any) -> str:
    name = getattr(value, "name", None)
    if isinstance(name, str):
        return name
    return str(value)


def resolve_and_pair(address: str, attempt_pair: bool) -> dict[str, Any]:
    try:
        from winrt.windows.devices.bluetooth import BluetoothLEDevice
    except Exception as exc:  # pragma: no cover - depends on Windows package availability.
        return {"available": False, "error": f"WinRT Bluetooth API unavailable: {exc!r}"}

    result: dict[str, Any] = {
        "available": True,
        "address": address,
        "attempt_pair_requested": attempt_pair,
        "resolved": False,
        "pair_attempted": False,
        "manual_required": False,
    }
    device = None
    try:
        device = BluetoothLEDevice.from_bluetooth_address_async(parse_ble_address(address)).get()
        if device is None:
            result["error"] = "BluetoothLEDevice.from_bluetooth_address_async returned no device."
            result["manual_required"] = True
            return result
        result["resolved"] = True
        result["name"] = str(device.name or "")
        info = device.device_information
        result["device_information_id"] = str(info.id)
        pairing = info.pairing
        result["is_paired_before"] = bool(pairing.is_paired)
        result["can_pair_before"] = bool(pairing.can_pair)
        if attempt_pair and not pairing.is_paired and pairing.can_pair:
            pair_result = pairing.pair_async().get()
            result["pair_attempted"] = True
            result["pair_status"] = enum_text(pair_result.status)
            result["pair_protection_level_used"] = enum_text(pair_result.protection_level_used)
        elif attempt_pair and pairing.is_paired:
            result["pair_status"] = "AlreadyPaired"
        elif attempt_pair:
            result["pair_status"] = "CannotPair"
            result["manual_required"] = True
        result["is_paired_after"] = bool(info.pairing.is_paired)
        result["can_pair_after"] = bool(info.pairing.can_pair)
        if attempt_pair and not result["is_paired_after"]:
            result["manual_required"] = True
    except Exception as exc:
        result["error"] = repr(exc)
        if attempt_pair:
            result["manual_required"] = True
    finally:
        close = getattr(device, "close", None)
        if callable(close):
            close()
    return result


def write_outputs(run_dir: pathlib.Path, summary: dict[str, Any], records: list[dict[str, Any]]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (run_dir / "scan_all.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    (run_dir / "operator_notes.md").write_text(
        "\n".join(
            [
                "# Windows Bluetooth Pairing Witness",
                "",
                "This diagnostic records advertisement discovery, WinRT pairing status, and Windows device inventory.",
                "Discovery alone is not pairing or host input delivery evidence.",
                f"Expected device name: {summary['expected_name']}",
                f"Advertisement seen: {summary['advertisement']['seen']}",
                f"Pairing attempted: {summary['pairing'].get('pair_attempted', False)}",
                f"Paired after attempt: {summary['pairing'].get('is_paired_after', False)}",
                f"Manual required: {summary['pairing'].get('manual_required', False)}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def run_witness(args: argparse.Namespace) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    records, watcher_status = ble_watcher.run_watcher(args.duration, args.scan_mode)
    advertisement = summarize_name_records(records, args.name)
    pairing: dict[str, Any] = {
        "available": False,
        "manual_required": False,
        "reason": "advertisement was not seen",
    }
    if advertisement["addresses"]:
        pairing = resolve_and_pair(str(advertisement["addresses"][0]), args.attempt_pair)
    return (
        {
            "captured_at": utc_stamp(),
            "expected_name": args.name,
            "scan_mode": args.scan_mode,
            "duration_seconds": args.duration,
            "watcher_final_status": watcher_status,
            "advertisement": advertisement,
            "pairing": pairing,
            "windows_inventory_before_or_after": collect_windows_inventory(),
        },
        records,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True, help="Expected BLE local name to discover and optionally pair.")
    parser.add_argument("--out-dir", type=pathlib.Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--duration", type=float, default=20.0)
    parser.add_argument("--scan-mode", choices=("active", "passive"), default="active")
    parser.add_argument("--attempt-pair", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = args.out_dir / f"windows_bluetooth_pairing_{utc_stamp()}"
    summary, records = run_witness(args)
    summary["run_dir"] = str(run_dir)
    write_outputs(run_dir, summary, records)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
