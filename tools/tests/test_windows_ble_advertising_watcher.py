#!/usr/bin/env python3

from __future__ import annotations

import unittest
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

import windows_ble_advertising_watcher as watcher


class WindowsBleAdvertisingWatcherTests(unittest.TestCase):
    def test_format_ble_address(self) -> None:
        self.assertEqual(watcher.format_ble_address(0xAABBCCDDEEFF), "AA:BB:CC:DD:EE:FF")

    def test_usb2ble_name_match(self) -> None:
        record = {"local_name": "USB2BLE Gamepad", "service_uuids": [], "data_sections": []}
        flags = watcher.match_record(record)
        self.assertTrue(flags["matches_usb2ble"])
        self.assertTrue(flags["matches_gamepad_name"])
        self.assertTrue(flags["matches_any_usb2ble_predicate"])

    def test_xbox_name_match(self) -> None:
        record = {"local_name": "Xbox Wireless Controller", "service_uuids": [], "data_sections": []}
        flags = watcher.match_record(record)
        self.assertTrue(flags["matches_xbox"])
        self.assertTrue(flags["matches_any_usb2ble_predicate"])

    def test_hid_service_uuid_match(self) -> None:
        record = {
            "local_name": "",
            "service_uuids": ["00001812-0000-1000-8000-00805f9b34fb"],
            "data_sections": [],
        }
        self.assertTrue(watcher.match_record(record)["matches_hid_service"])

    def test_summary_counts_unique_and_matches(self) -> None:
        records = [
            {
                "bluetooth_address": "AA:BB:CC:DD:EE:01",
                "local_name": "USB2BLE_ADV_TEST",
                "service_uuids": [],
                "matches_usb2ble": True,
                "matches_xbox": False,
                "matches_gamepad_name": False,
                "matches_hid_service": False,
                "matches_any_usb2ble_predicate": True,
                "rssi_dbm": -55,
            },
            {
                "bluetooth_address": "AA:BB:CC:DD:EE:02",
                "local_name": "Other",
                "service_uuids": [],
                "matches_usb2ble": False,
                "matches_xbox": False,
                "matches_gamepad_name": False,
                "matches_hid_service": False,
                "matches_any_usb2ble_predicate": False,
            },
        ]
        summary = watcher.summarize(records, 1.0, "active")
        self.assertEqual(summary["total_advertisements"], 2)
        self.assertEqual(summary["unique_addresses"], 2)
        self.assertTrue(summary["usb2ble_seen"])
        self.assertEqual(summary["matched_advertisements"], 1)
        self.assertEqual(summary["matched_rssi_max"], -55)


if __name__ == "__main__":
    unittest.main()
