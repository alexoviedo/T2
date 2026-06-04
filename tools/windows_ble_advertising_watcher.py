#!/usr/bin/env python3
"""Capture Windows BLE advertisements with the native WinRT watcher."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import threading
import time
from typing import Any


DEFAULT_OUT_DIR = pathlib.Path("target/windows-ble-advertising")
MATCH_NAME_TOKENS = ("usb2ble", "xbox wireless controller", "gamepad")
HID_SERVICE_UUIDS = {
    "00001812-0000-1000-8000-00805f9b34fb",
    "1812",
}


def utc_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def format_ble_address(value: int | None) -> str | None:
    if value is None:
        return None
    return ":".join(f"{(int(value) >> shift) & 0xff:02X}" for shift in range(40, -1, -8))


def enum_name(value: Any) -> str:
    name = getattr(value, "name", None)
    if isinstance(name, str):
        return name
    return str(value)


def buffer_hex(buffer: Any) -> str:
    try:
        return bytes(buffer).hex()
    except Exception:
        return ""


def normalize_event(args: Any) -> dict[str, Any]:
    advertisement = args.advertisement
    service_uuids = [str(uuid).lower() for uuid in list(advertisement.service_uuids)]
    data_sections = [
        {
            "data_type": int(section.data_type),
            "data_hex": buffer_hex(section.data),
        }
        for section in list(advertisement.data_sections)
    ]
    manufacturer_data = [
        {
            "company_id": int(item.company_id),
            "data_hex": buffer_hex(item.data),
        }
        for item in list(advertisement.manufacturer_data)
    ]
    timestamp = getattr(args, "timestamp", None)
    if hasattr(timestamp, "isoformat"):
        timestamp_text = timestamp.isoformat()
    else:
        timestamp_text = dt.datetime.now(dt.timezone.utc).isoformat()

    record = {
        "captured_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "event_timestamp": timestamp_text,
        "bluetooth_address": format_ble_address(getattr(args, "bluetooth_address", None)),
        "bluetooth_address_int": getattr(args, "bluetooth_address", None),
        "bluetooth_address_type": enum_name(getattr(args, "bluetooth_address_type", None)),
        "rssi_dbm": getattr(args, "raw_signal_strength_in_dbm", None),
        "transmit_power_dbm": getattr(args, "transmit_power_level_in_dbm", None),
        "advertisement_type": enum_name(getattr(args, "advertisement_type", None)),
        "is_connectable": getattr(args, "is_connectable", None),
        "is_scannable": getattr(args, "is_scannable", None),
        "is_scan_response": getattr(args, "is_scan_response", None),
        "is_directed": getattr(args, "is_directed", None),
        "is_anonymous": getattr(args, "is_anonymous", None),
        "primary_phy": enum_name(getattr(args, "primary_phy", None)),
        "secondary_phy": enum_name(getattr(args, "secondary_phy", None)),
        "local_name": advertisement.local_name or "",
        "service_uuids": service_uuids,
        "flags": getattr(advertisement, "flags", None),
        "data_sections": data_sections,
        "manufacturer_data": manufacturer_data,
    }
    record.update(match_record(record))
    return record


def match_record(record: dict[str, Any]) -> dict[str, bool]:
    local_name = str(record.get("local_name") or "").lower()
    uuids = {str(uuid).lower() for uuid in record.get("service_uuids") or []}
    data_text = " ".join(str(section.get("data_hex", "")) for section in record.get("data_sections") or [])
    usb2ble_seen = "usb2ble" in local_name
    xbox_seen = "xbox wireless controller" in local_name or local_name == "xbox"
    gamepad_seen = "gamepad" in local_name
    hid_service_seen = bool(uuids & HID_SERVICE_UUIDS) or "1218" in data_text
    return {
        "matches_usb2ble": usb2ble_seen,
        "matches_xbox": xbox_seen,
        "matches_gamepad_name": gamepad_seen,
        "matches_hid_service": hid_service_seen,
        "matches_any_usb2ble_predicate": usb2ble_seen or xbox_seen or gamepad_seen or hid_service_seen,
    }


def summarize(records: list[dict[str, Any]], duration_seconds: float, mode: str) -> dict[str, Any]:
    unique_addresses = sorted({str(record.get("bluetooth_address")) for record in records if record.get("bluetooth_address")})
    matched = [record for record in records if record.get("matches_any_usb2ble_predicate")]
    rssis = [record.get("rssi_dbm") for record in matched if isinstance(record.get("rssi_dbm"), int)]
    return {
        "scanner": "windows_winrt_bluetooth_le_advertisement_watcher",
        "scan_mode": mode,
        "duration_seconds": duration_seconds,
        "total_advertisements": len(records),
        "unique_addresses": len(unique_addresses),
        "usb2ble_seen": any(record.get("matches_usb2ble") for record in records),
        "xbox_seen": any(record.get("matches_xbox") for record in records),
        "gamepad_name_seen": any(record.get("matches_gamepad_name") for record in records),
        "hid_service_seen": any(record.get("matches_hid_service") for record in records),
        "matched_advertisements": len(matched),
        "matched_addresses": sorted({str(record.get("bluetooth_address")) for record in matched if record.get("bluetooth_address")}),
        "matched_local_names": sorted({str(record.get("local_name")) for record in matched if record.get("local_name")}),
        "matched_service_uuids": sorted(
            {
                str(uuid)
                for record in matched
                for uuid in (record.get("service_uuids") or [])
            }
        ),
        "matched_rssi_min": min(rssis) if rssis else None,
        "matched_rssi_max": max(rssis) if rssis else None,
    }


def write_outputs(run_dir: pathlib.Path, records: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    with (run_dir / "scan_all.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    (run_dir / "scan_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        f"scanner: {summary['scanner']}",
        f"scan_mode: {summary['scan_mode']}",
        f"total_advertisements: {summary['total_advertisements']}",
        f"unique_addresses: {summary['unique_addresses']}",
        f"usb2ble_seen: {summary['usb2ble_seen']}",
        f"xbox_seen: {summary['xbox_seen']}",
        f"hid_service_seen: {summary['hid_service_seen']}",
        "",
        "Matched advertisements:",
    ]
    for record in records:
        if record.get("matches_any_usb2ble_predicate"):
            lines.append(
                f"- {record.get('bluetooth_address')} rssi={record.get('rssi_dbm')} "
                f"name={record.get('local_name')!r} uuids={record.get('service_uuids')}"
            )
    (run_dir / "scan_all.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_watcher(duration_seconds: float, mode: str) -> tuple[list[dict[str, Any]], str]:
    from winrt.windows.devices.bluetooth.advertisement import (
        BluetoothLEAdvertisementWatcher,
        BluetoothLEAdvertisementWatcherStatus,
        BluetoothLEScanningMode,
    )

    watcher = BluetoothLEAdvertisementWatcher()
    watcher.scanning_mode = BluetoothLEScanningMode.ACTIVE if mode == "active" else BluetoothLEScanningMode.PASSIVE
    records: list[dict[str, Any]] = []
    lock = threading.Lock()

    def received(_sender: Any, args: Any) -> None:
        record = normalize_event(args)
        with lock:
            records.append(record)

    token = watcher.add_received(received)
    watcher.start()
    start = time.monotonic()
    try:
        while time.monotonic() - start < duration_seconds:
            time.sleep(0.1)
    finally:
        watcher.remove_received(token)
        if watcher.status != BluetoothLEAdvertisementWatcherStatus.STOPPED:
            watcher.stop()
        time.sleep(0.25)
    return records, enum_name(watcher.status)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=pathlib.Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--duration", type=float, default=30.0)
    parser.add_argument("--mode", choices=("active", "passive"), default="active")
    parser.add_argument("--run-name", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = args.out_dir
    if args.run_name:
        run_dir = run_dir / args.run_name
    else:
        run_dir = run_dir / f"windows_ble_scan_{utc_stamp()}"
    try:
        records, final_status = run_watcher(args.duration, args.mode)
        error = None
    except Exception as exc:
        records = []
        final_status = "error"
        error = repr(exc)
    summary = summarize(records, args.duration, args.mode)
    summary["watcher_final_status"] = final_status
    if error:
        summary["error"] = error
    write_outputs(run_dir, records, summary)
    print(json.dumps({"run_dir": str(run_dir), **summary}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
