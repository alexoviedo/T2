from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

import ble_advertising_probe  # noqa: E402
import check_ble_hid_profile  # noqa: E402
import check_xbox_ble_profile  # noqa: E402


class BleAdvertisingProbeTests(unittest.TestCase):
    def test_normalizes_nrf_connect_json_export(self) -> None:
        fixture = ROOT / "tools/tests/fixtures/ble_scanner/nrf_connect_usb2ble.json"
        records = ble_advertising_probe.normalize_manual_scan_text(fixture.read_text(encoding="utf-8"))

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["device_name"], "USB2BLE Gamepad")
        self.assertIn("1812", records[0]["service_uuids"])
        self.assertEqual(records[0]["appearance"], "0x03c4")
        self.assertTrue(records[0]["raw_bytes"])

    def test_normalizes_btmon_text_export(self) -> None:
        fixture = ROOT / "tools/tests/fixtures/ble_scanner/btmon_usb2ble.txt"
        records = ble_advertising_probe.normalize_manual_scan_text(fixture.read_text(encoding="utf-8"))

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["device_name"], "USB2BLE Gamepad")
        self.assertEqual(records[0]["rssi"], -51)
        self.assertIn("1812", records[0]["service_uuids"])


class BleHidProfileCheckerTests(unittest.TestCase):
    def test_builtin_generic_default_has_no_structural_failures(self) -> None:
        summary = check_ble_hid_profile.check_profile(
            check_ble_hid_profile.builtin_profile("generic_default")
        )

        self.assertEqual(summary["fail_count"], 0)
        self.assertGreater(summary["unknown_count"], 0)

    def test_detects_missing_hid_uuid(self) -> None:
        profile = check_ble_hid_profile.builtin_profile("generic_default")
        profile["primary_advertisement"]["uuids"] = []

        summary = check_ble_hid_profile.check_profile(profile)

        self.assertGreater(summary["fail_count"], 0)

    def test_loads_prefixed_profile_json(self) -> None:
        profile = check_ble_hid_profile.builtin_profile("generic_hogp_strict")
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8") as handle:
            handle.write("BLE_COMPAT_PROFILE_JSON:" + json.dumps(profile))
            handle.flush()
            loaded = check_ble_hid_profile.load_profile_file(pathlib.Path(handle.name))

        self.assertEqual(loaded["active_variant"], "generic_hogp_strict")


class XboxBleProfileCheckerTests(unittest.TestCase):
    def test_builtin_xbox_profile_matches_reference_shape(self) -> None:
        report_map = check_xbox_ble_profile.extract_xbox_report_map()
        summary = check_xbox_ble_profile.check_profile(
            check_ble_hid_profile.builtin_profile("xbox_compatibility"),
            report_map,
        )

        self.assertEqual(summary["fail_count"], 0)
        self.assertEqual(summary["warn_count"], 0)

    def test_xbox_checker_detects_missing_output_report_id(self) -> None:
        profile = check_ble_hid_profile.builtin_profile("xbox_compatibility")
        profile["report_ids"] = [1]

        summary = check_xbox_ble_profile.check_profile(profile, [])

        self.assertGreater(summary["fail_count"], 0)


if __name__ == "__main__":
    unittest.main()
