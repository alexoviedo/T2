import pathlib
import sys
import unittest

TOOLS = pathlib.Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import windows_ble_identity_witness as witness  # noqa: E402


class WindowsBleIdentityWitnessTests(unittest.TestCase):
    def test_topology_ok_requires_expected_flight_pack_devices(self) -> None:
        text = (
            "USB_DEVICES:id=1,vid=2109,pid=2813|"
            "id=2,vid=044f,pid=b10a|id=3,vid=044f,pid=b687"
        )

        self.assertTrue(witness.topology_ok(text))
        self.assertFalse(witness.topology_ok("USB_DEVICES:id=1,vid=2109,pid=2813"))

    def test_response_lines_filters_serial_noise(self) -> None:
        output = "\n".join(
            [
                "boot noise",
                "BLE_IDENTITY_INFO_JSON:{\"supported\":true}",
                "ERROR:Generic",
                "more noise",
            ]
        )

        self.assertEqual(
            witness.response_lines(output),
            ["BLE_IDENTITY_INFO_JSON:{\"supported\":true}", "ERROR:Generic"],
        )


if __name__ == "__main__":
    unittest.main()
