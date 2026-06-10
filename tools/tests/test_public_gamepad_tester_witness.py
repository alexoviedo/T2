from __future__ import annotations

import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

import public_gamepad_tester_witness as witness  # noqa: E402


class PublicGamepadTesterWitnessTests(unittest.TestCase):
    def test_build_tester_url_merges_capture_params(self) -> None:
        url = witness.build_tester_url(
            "https://example.test/T2/gamepad-test.html?foo=bar",
            expected_profile="xbox-standard",
            capture_seconds=12.5,
            auto_download=True,
            auto_arm=True,
            sample_ms=75,
        )

        self.assertIn("foo=bar", url)
        self.assertIn("autoArm=1", url)
        self.assertIn("expectedProfile=xbox-standard", url)
        self.assertIn("captureMs=12500", url)
        self.assertIn("sampleMs=75", url)
        self.assertIn("autoDownload=1", url)

    def test_browser_evidence_passes_for_changed_standard_xbox_controls(self) -> None:
        evidence = {
            "schema": "usb2ble_public_gamepad_tester_v1",
            "expected_profile": "xbox-standard",
            "gamepad_count": 1,
            "sample_count": 20,
            "primary_gamepad": {
                "id": "Xbox Wireless Controller",
                "mapping": "standard",
            },
            "summary": {
                "changed_axes": [0, 1, 2],
                "changed_buttons": [0, 1, 6, 7],
            },
        }

        passed, reasons = witness.browser_evidence_passes(evidence, "xbox-standard")

        self.assertTrue(passed)
        self.assertEqual(reasons, [])

    def test_browser_evidence_rejects_missing_changes(self) -> None:
        evidence = {
            "gamepad_count": 1,
            "primary_gamepad": {"id": "Xbox Wireless Controller", "mapping": "standard"},
            "summary": {"changed_axes": [], "changed_buttons": []},
        }

        passed, reasons = witness.browser_evidence_passes(evidence, "xbox-standard")

        self.assertFalse(passed)
        self.assertIn("tester did not report changed axes", reasons)
        self.assertIn("tester did not report changed buttons", reasons)

    def test_xinput_scenario_moved_matches_probe_shape(self) -> None:
        slot = {
            "connected": True,
            "buttons": 0x1000 | 0x0001,
            "left_trigger": 255,
            "right_trigger": 0,
            "left_thumb": [32767, 0],
            "right_thumb": [-32768, 0],
        }

        self.assertTrue(witness.xinput_scenario_moved("button_a", slot))
        self.assertTrue(witness.xinput_scenario_moved("dpad_up", slot))
        self.assertTrue(witness.xinput_scenario_moved("left_trigger_max", slot))
        self.assertTrue(witness.xinput_scenario_moved("left_stick_right", slot))
        self.assertTrue(witness.xinput_scenario_moved("right_stick_left", slot))
        self.assertFalse(witness.xinput_scenario_moved("button_b", slot))


if __name__ == "__main__":
    unittest.main()
