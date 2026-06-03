from __future__ import annotations

import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

import windows_gamepad_probe  # noqa: E402


class WindowsGamepadProbeTests(unittest.TestCase):
    def test_controller_name_classifier_matches_usb2ble_and_xbox(self) -> None:
        self.assertTrue(windows_gamepad_probe.looks_like_controller_name("USB2BLE Gamepad"))
        self.assertTrue(windows_gamepad_probe.looks_like_controller_name("Xbox Wireless Controller"))
        self.assertTrue(windows_gamepad_probe.looks_like_controller_name(r"HID#VID_303A&PID_4001"))
        self.assertFalse(windows_gamepad_probe.looks_like_controller_name("Bluetooth Radio"))

    def test_pnp_summary_finds_controller_like_devices(self) -> None:
        inventory = {
            "hidclass": {
                "devices": [
                    {
                        "FriendlyName": "USB2BLE Gamepad",
                        "InstanceId": r"HID\VID_303A&PID_4001",
                    },
                    {
                        "FriendlyName": "Keyboard",
                        "InstanceId": r"HID\VID_0000&PID_0000",
                    },
                ]
            },
            "bluetooth": {"devices": []},
        }

        summary = windows_gamepad_probe.summarize_pnp_inventory(inventory)

        self.assertEqual(summary["controller_like_count"], 1)
        self.assertEqual(summary["controller_like_devices"][0]["FriendlyName"], "USB2BLE Gamepad")

    def test_browser_sample_summary_reports_no_controller_cleanly(self) -> None:
        summary = windows_gamepad_probe.summarize_browser_samples(
            [{"gamepads": [None], "document_has_focus": True}]
        )

        self.assertEqual(summary["sample_count"], 1)
        self.assertEqual(summary["connected_gamepad_observations"], 0)
        self.assertFalse(summary["gamepad_visible"])

    def test_browser_sample_summary_reports_visible_xinput_shape(self) -> None:
        summary = windows_gamepad_probe.summarize_browser_samples(
            [
                {
                    "gamepads": [
                        {
                            "connected": True,
                            "id": "Xbox Wireless Controller (STANDARD GAMEPAD Vendor: 045e Product: 0b13)",
                            "mapping": "standard",
                        }
                    ]
                }
            ]
        )

        self.assertTrue(summary["gamepad_visible"])
        self.assertEqual(summary["mappings"], ["standard"])
        self.assertIn("Xbox Wireless Controller", summary["ids"][0])


if __name__ == "__main__":
    unittest.main()
