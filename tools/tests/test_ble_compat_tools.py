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
import check_persona_acceptance  # noqa: E402
import check_xbox_ble_profile  # noqa: E402
import xbox_host_visible_witness  # noqa: E402


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


class XboxHostVisibleWitnessTests(unittest.TestCase):
    def test_standard_layout_classifier_accepts_identity_string_mismatch_only(self) -> None:
        browser = {
            "id": "USB2BLE Gamepad (STANDARD GAMEPAD)",
            "mapping": "standard",
            "axes_count": 4,
            "buttons_count": 18,
            "is_standard_mapping": True,
        }
        scenario_results = [
            {
                "scenario": scenario,
                "standard_control": {
                    "expected": xbox_host_visible_witness.STANDARD_EXPECTED_CONTROLS[scenario],
                    "matched": True,
                },
            }
            for scenario in xbox_host_visible_witness.STANDARD_EXPECTED_CONTROLS
        ]

        result = xbox_host_visible_witness.classify_standard_layout(
            browser,
            scenario_results,
            xbox_like_identity_observed=False,
        )

        self.assertEqual(result["classification"], "identity_string_mismatch_only")
        self.assertTrue(result["required_pass"])
        self.assertFalse(result["xbox_like_identity_observed"])

    def test_standard_layout_classifier_marks_partial_when_buttons_do_not_match(self) -> None:
        browser = {
            "id": "USB2BLE Gamepad (STANDARD GAMEPAD)",
            "mapping": "standard",
            "axes_count": 4,
            "buttons_count": 18,
            "is_standard_mapping": True,
        }
        scenario_results = []
        for scenario, expected in xbox_host_visible_witness.STANDARD_EXPECTED_CONTROLS.items():
            scenario_results.append(
                {
                    "scenario": scenario,
                    "standard_control": {
                        "expected": expected,
                        "matched": scenario not in {"button_x", "button_rb", "button_view"},
                    },
                }
            )

        result = xbox_host_visible_witness.classify_standard_layout(
            browser,
            scenario_results,
            xbox_like_identity_observed=False,
        )

        self.assertEqual(result["classification"], "standard_layout_partial")
        self.assertTrue(result["core_pass"])
        self.assertFalse(result["required_pass"])
        self.assertIn("button_x", result["failed_standard_scenarios"])

    def test_layout_diagnosis_records_unexpected_and_missing_controls(self) -> None:
        scenario_results = [
            {
                "scenario": "button_x",
                "encoded_report_bytes": "00",
                "changed_axis_indices": [],
                "changed_button_indices": [{"index": 5, "before": 0.0, "after": 1.0, "delta": 1.0}],
                "standard_control": {
                    "expected": xbox_host_visible_witness.STANDARD_EXPECTED_CONTROLS["button_x"],
                    "matched": False,
                },
            },
            {
                "scenario": "button_y",
                "encoded_report_bytes": "00",
                "changed_axis_indices": [],
                "changed_button_indices": [],
                "standard_control": {
                    "expected": xbox_host_visible_witness.STANDARD_EXPECTED_CONTROLS["button_y"],
                    "matched": False,
                },
            },
        ]

        diagnosis = xbox_host_visible_witness.layout_diagnosis(scenario_results)

        self.assertEqual(diagnosis["unexpected_button_indices"][0]["scenario"], "button_x")
        self.assertEqual(diagnosis["missing_expected_indices"][0]["scenario"], "button_y")


class PersonaAcceptanceGateTests(unittest.TestCase):
    def test_unknown_persona_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            check_persona_acceptance.evaluate_persona("not_a_persona")

    def test_planned_keyboard_persona_has_no_failures(self) -> None:
        summary = check_persona_acceptance.evaluate_persona("ble_keyboard")
        self.assertEqual(summary["fail_count"], 0)
        self.assertGreaterEqual(summary["warn_count"], 1)

    def test_xbox_persona_acceptance_references_standard_layout_evidence(self) -> None:
        summary = check_persona_acceptance.evaluate_persona("xbox_wireless_controller")
        self.assertEqual(summary["fail_count"], 0)
        host_checks = [
            check
            for check in summary["checks"]
            if check["layer"] == "evidence" and check["item"] == "host_visible_witness"
        ]
        self.assertEqual(len(host_checks), 1)
        self.assertIn("XBOX_STANDARD_LAYOUT_DIAGNOSTIC_2026-05-29.md", host_checks[0]["note"])


if __name__ == "__main__":
    unittest.main()
