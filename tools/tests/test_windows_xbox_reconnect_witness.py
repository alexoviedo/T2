from __future__ import annotations

import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

import windows_xbox_reconnect_witness as reconnect_witness  # noqa: E402


class WindowsXboxReconnectWitnessTests(unittest.TestCase):
    def test_parse_kv_payload_parses_semicolon_response(self) -> None:
        fields = reconnect_witness.parse_kv_payload(
            "STATUS:ble=Connected;profile=none;persona=xbox_wireless_controller;bonds=false;"
        )

        self.assertEqual(fields["ble"], "Connected")
        self.assertEqual(fields["persona"], "xbox_wireless_controller")
        self.assertEqual(fields["bonds"], "false")

    def test_scenario_passed_detects_xinput_shapes(self) -> None:
        left = [{"slot0": {"connected": True, "left_thumb": [32767, 0], "buttons": 0}}]
        trigger = [{"slot0": {"connected": True, "left_trigger": 255, "buttons": 0}}]
        button = [{"slot0": {"connected": True, "buttons": 4096}}]

        self.assertTrue(reconnect_witness.scenario_passed("left_stick_right", left))
        self.assertTrue(reconnect_witness.scenario_passed("left_trigger_max", trigger))
        self.assertTrue(reconnect_witness.scenario_passed("button_a", button))

    def test_scenario_passed_rejects_disconnected_samples(self) -> None:
        samples = [{"slot0": {"connected": False, "left_thumb": [32767, 0]}}]

        self.assertFalse(reconnect_witness.scenario_passed("left_stick_right", samples))

    def test_classify_reconnect_auto_pass(self) -> None:
        classification = reconnect_witness.classify_reconnect(
            {"slot0_connected": True},
            {"passed": True},
            manual_windows_action=False,
        )

        self.assertEqual(classification, "reconnect_pass_auto")

    def test_classify_reconnect_failed_without_xinput(self) -> None:
        classification = reconnect_witness.classify_reconnect(
            {"slot0_connected": False},
            None,
            manual_windows_action=False,
        )

        self.assertEqual(classification, "reconnect_fail")

    def test_classify_reconnect_failed_when_connected_slot_does_not_move(self) -> None:
        classification = reconnect_witness.classify_reconnect(
            {"slot0_connected": True},
            {"passed": False},
            manual_windows_action=False,
            target_restart_required=True,
        )

        self.assertEqual(classification, "reconnect_fail")

    def test_classify_reconnect_after_target_restart_requires_sanity_pass(self) -> None:
        classification = reconnect_witness.classify_reconnect(
            {"slot0_connected": True},
            {"passed": True},
            manual_windows_action=False,
            target_restart_required=True,
        )

        self.assertEqual(classification, "reconnect_pass_after_target_restart")


if __name__ == "__main__":
    unittest.main()
