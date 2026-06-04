import json
import pathlib
import sys
import tempfile
import unittest


TOOLS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

import firmware_ble_provenance_witness as witness  # noqa: E402


class FirmwareBleProvenanceWitnessTests(unittest.TestCase):
    def test_parse_pages_manifest_offset(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            manifest = root / "manifest.json"
            artifact = root / "usb2ble-fw-esp32s3-merged.bin"
            artifact.write_bytes(b"bin")
            manifest.write_text(
                json.dumps(
                    {
                        "builds": [
                            {
                                "parts": [
                                    {
                                        "path": "usb2ble-fw-esp32s3-merged.bin",
                                        "offset": 0,
                                    }
                                ]
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(witness.parse_offset_from_manifest(manifest, artifact), 0)

    def test_parse_release_manifest_flash_command_offset(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            manifest = root / "manifest.txt"
            artifact = root / "firmware.bin"
            artifact.write_bytes(b"bin")
            manifest.write_text(
                "flash_command=espflash write-bin --chip esp32s3 --port <PORT> 0x0 target/firmware/firmware.bin\n",
                encoding="utf-8",
            )
            self.assertEqual(witness.parse_offset_from_manifest(manifest, artifact), 0)

    def test_scan_name_summary_matches_local_name_and_raw_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            out_dir = pathlib.Path(temp)
            scan_dir = out_dir / "windows_ble_scan"
            scan_dir.mkdir()
            records = [
                {
                    "bluetooth_address": "AA:BB:CC:00:00:01",
                    "local_name": "USB2BLE Gamepad",
                    "rssi_dbm": -42,
                    "data_sections": [],
                },
                {
                    "bluetooth_address": "AA:BB:CC:00:00:02",
                    "local_name": "",
                    "rssi_dbm": -55,
                    "data_sections": [{"data_hex": "424c455f534d4f4b45"}],
                },
            ]
            (scan_dir / "scan_all.jsonl").write_text(
                "\n".join(json.dumps(record) for record in records) + "\n",
                encoding="utf-8",
            )
            summary = witness.scan_name_summary(out_dir, ["USB2BLE Gamepad", "BLE_SMOKE"])
            self.assertTrue(summary["names"]["USB2BLE Gamepad"]["seen"])
            self.assertTrue(summary["names"]["BLE_SMOKE"]["seen"])
            self.assertEqual(summary["unique_addresses"], 2)


if __name__ == "__main__":
    unittest.main()
