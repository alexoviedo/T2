from __future__ import annotations

import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

import windows_xbox_app_witness  # noqa: E402


class WindowsXboxAppWitnessTests(unittest.TestCase):
    def test_default_scenarios_are_xbox_virtual_mapping_only(self) -> None:
        scenarios = windows_xbox_app_witness.DEFAULT_SCENARIOS

        self.assertIn("stick_left", scenarios)
        self.assertIn("rudder_right", scenarios)
        self.assertIn("left_toe_pressed", scenarios)
        self.assertIn("right_toe_released", scenarios)
        self.assertNotIn("throttle_max", scenarios)

    def test_xinput_slot_finds_slot_zero(self) -> None:
        xinput = {
            "slots": [
                {"slot": 1, "connected": False},
                {"slot": 0, "connected": True, "left_trigger": 255},
            ]
        }

        slot = windows_xbox_app_witness.xinput_slot(xinput, 0)

        self.assertIsNotNone(slot)
        self.assertTrue(slot["connected"])
        self.assertEqual(slot["left_trigger"], 255)

    def test_summarize_slot_samples_reports_axis_and_trigger_extremes(self) -> None:
        samples = [
            {
                "slot0": {
                    "connected": True,
                    "left_thumb": [-32768, -1],
                    "right_thumb": [0, -1],
                    "left_trigger": 0,
                    "right_trigger": 0,
                    "buttons": 0,
                }
            },
            {
                "slot0": {
                    "connected": True,
                    "left_thumb": [32767, 32767],
                    "right_thumb": [-32768, -1],
                    "left_trigger": 255,
                    "right_trigger": 255,
                    "buttons": 4096,
                }
            },
        ]

        summary = windows_xbox_app_witness.summarize_slot_samples(samples)

        self.assertTrue(summary["slot0_connected"])
        self.assertEqual(summary["left_thumb_x_min"], -32768)
        self.assertEqual(summary["left_thumb_x_max"], 32767)
        self.assertEqual(summary["right_thumb_x_min"], -32768)
        self.assertEqual(summary["left_trigger_max"], 255)
        self.assertEqual(summary["right_trigger_max"], 255)
        self.assertEqual(summary["buttons_observed"], [0, 4096])


if __name__ == "__main__":
    unittest.main()
