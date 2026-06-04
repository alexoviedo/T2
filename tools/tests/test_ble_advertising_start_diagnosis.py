import pathlib
import sys
import unittest


TOOLS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

import ble_advertising_start_diagnosis as diag  # noqa: E402


class BleAdvertisingStartDiagnosisTests(unittest.TestCase):
    def test_parse_prefixed_json(self):
        parsed = diag.parse_json_payload(
            'BLE_ADVERTISING_EVENTS_JSON:{"last_adv_raw_config_status":0,"owner":"raw_smoke"}'
        )
        self.assertEqual(
            parsed,
            (
                "BLE_ADVERTISING_EVENTS_JSON",
                {"last_adv_raw_config_status": 0, "owner": "raw_smoke"},
            ),
        )

    def test_transport_status_extracts_nested_status(self):
        value = diag.transport_status(
            {
                "transport_status": {
                    "smoke_state": "advertising",
                    "last_adv_start_status": 0,
                }
            }
        )
        self.assertEqual(value["smoke_state"], "advertising")

    def test_classify_target_stack_start_failure(self):
        self.assertEqual(
            diag.classify_failure(
                {
                    "windows_watcher_seen": False,
                    "adv_config_complete_success": True,
                    "adv_start_success": False,
                }
            ),
            "target_ble_stack_start",
        )

    def test_classify_windows_scanner_when_target_started(self):
        self.assertEqual(
            diag.classify_failure(
                {
                    "windows_watcher_seen": False,
                    "adv_config_complete_success": True,
                    "adv_start_success": True,
                }
            ),
            "windows_adapter_or_scanner",
        )

    def test_classify_none_when_seen(self):
        self.assertIsNone(diag.classify_failure({"windows_watcher_seen": True}))


if __name__ == "__main__":
    unittest.main()
