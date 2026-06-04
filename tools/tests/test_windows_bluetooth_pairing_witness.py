import pathlib
import sys
import unittest

TOOLS = pathlib.Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import windows_bluetooth_pairing_witness as pairing_witness  # noqa: E402


class WindowsBluetoothPairingWitnessTests(unittest.TestCase):
    def test_summarize_name_records_matches_exact_and_contains(self) -> None:
        records = [
            {
                "bluetooth_address": "90:70:69:07:0D:7E",
                "local_name": "USB2BLE Gamepad",
                "rssi_dbm": -31,
                "service_uuids": ["00001812-0000-1000-8000-00805f9b34fb"],
            },
            {
                "bluetooth_address": "90:70:69:07:0D:7E",
                "local_name": "USB2BLE Gamepad U6",
                "rssi_dbm": -33,
                "service_uuids": [],
            },
            {
                "bluetooth_address": "AA:BB:CC:DD:EE:FF",
                "local_name": "Other",
                "rssi_dbm": -70,
                "service_uuids": [],
            },
        ]

        summary = pairing_witness.summarize_name_records(records, "USB2BLE Gamepad")

        self.assertTrue(summary["seen"])
        self.assertEqual(summary["match_count"], 2)
        self.assertEqual(summary["addresses"], ["90:70:69:07:0D:7E"])
        self.assertEqual(summary["rssi_min"], -33)
        self.assertEqual(summary["rssi_max"], -31)
        self.assertEqual(summary["service_uuids"], ["00001812-0000-1000-8000-00805f9b34fb"])

    def test_parse_ble_address_accepts_colons_and_hyphens(self) -> None:
        self.assertEqual(
            pairing_witness.parse_ble_address("90:70:69:07:0D:7E"),
            pairing_witness.parse_ble_address("90-70-69-07-0D-7E"),
        )


if __name__ == "__main__":
    unittest.main()
