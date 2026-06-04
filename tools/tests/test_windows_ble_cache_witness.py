import pathlib
import sys
import unittest

TOOLS = pathlib.Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import windows_ble_cache_witness as cache_witness  # noqa: E402


class WindowsBleCacheWitnessTests(unittest.TestCase):
    def test_candidate_matches_usb2ble_root_device(self) -> None:
        device = {
            "Class": "Bluetooth",
            "FriendlyName": "USB2BLE Gamepad",
            "InstanceId": r"BTHLE\DEV_907069070D7E\8&3B2CE00F&0&907069070D7E",
        }

        self.assertEqual(cache_witness.candidate_reason(device), "safe_name_match")

    def test_candidate_matches_hid_child_by_address_and_vid_pid(self) -> None:
        device = {
            "Class": "HIDClass",
            "FriendlyName": "HID-compliant game controller",
            "InstanceId": (
                r"HID\{00001812-0000-1000-8000-00805F9B34FB}_"
                r"DEV_VID&02303A_PID&4001_REV&0001_907069070D7E\A&2C8E6397&0&0000"
            ),
        }

        self.assertEqual(cache_witness.candidate_reason(device), "usb2ble_address_and_hid_or_service_match")

    def test_candidate_does_not_match_unrelated_controller(self) -> None:
        device = {
            "Class": "System",
            "FriendlyName": "Oculus Virtual Gamepad Emulation Bus",
            "InstanceId": r"ROOT\SYSTEM\0002",
        }

        self.assertIsNone(cache_witness.candidate_reason(device))

    def test_candidate_does_not_match_unrelated_xbox_name_without_usb2ble_address(self) -> None:
        device = {
            "Class": "Bluetooth",
            "FriendlyName": "Xbox Wireless Controller",
            "InstanceId": r"BTHLE\DEV_AABBCCDDEEFF\8&1234567&0&AABBCCDDEEFF",
        }

        self.assertIsNone(cache_witness.candidate_reason(device))

    def test_candidate_matches_xbox_name_with_usb2ble_address(self) -> None:
        device = {
            "Class": "Bluetooth",
            "FriendlyName": "Xbox Wireless Controller",
            "InstanceId": r"BTHLE\DEV_907069070D7E\8&3B2CE00F&0&907069070D7E",
        }

        self.assertEqual(cache_witness.candidate_reason(device), "xbox_name_with_usb2ble_address")

    def test_removal_order_puts_child_nodes_before_root(self) -> None:
        inventory = {
            "devices": {
                "devices": [
                    {
                        "Class": "Bluetooth",
                        "FriendlyName": "USB2BLE Gamepad",
                        "InstanceId": r"BTHLE\DEV_907069070D7E\8&3B2CE00F&0&907069070D7E",
                    },
                    {
                        "Class": "HIDClass",
                        "FriendlyName": "HID-compliant game controller",
                        "InstanceId": (
                            r"HID\{00001812-0000-1000-8000-00805F9B34FB}_"
                            r"DEV_VID&02303A_PID&4001_REV&0001_907069070D7E\A&2C8E6397&0&0000"
                        ),
                    },
                ]
            }
        }

        candidates = cache_witness.find_candidates(inventory)

        self.assertTrue(candidates[0]["InstanceId"].startswith("HID\\"))
        self.assertTrue(candidates[1]["InstanceId"].startswith("BTHLE\\DEV_"))


if __name__ == "__main__":
    unittest.main()
