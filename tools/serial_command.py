#!/usr/bin/env python3
"""Send one or more serial control-plane commands and print matching responses."""

from __future__ import annotations

import argparse
import sys
import time

from serial_backend import BAUD, NativeSerialPort

PREFIXES = (
    "INFO:",
    "STATUS:",
    "PROFILE:",
    "USB_STATUS:",
    "USB_DEVICES:",
    "USB_DEVICE:",
    "USB_DESCRIPTOR:",
    "USB_REPORT:",
    "HID_SUMMARY:",
    "NORMALIZED_INPUT:",
    "ENCODED_REPORT:",
    "GENERIC_GAMEPAD_MAPPING:",
    "XBOX_GAMEPAD_MAPPING:",
    "BLE_ACTION:",
    "BLE_ADVERTISING_INFO:",
    "BLE_ADVERTISING_EVENTS_JSON:",
    "BLE_ADV_SMOKE_TEST_STATUS_JSON:",
    "BLE_COMPAT_VARIANTS_JSON:",
    "BLE_COMPAT_PROFILE_JSON:",
    "BRIDGE_STATUS:",
    "CONFIG_STATUS:",
    "CONFIG_SCHEMA_JSON:",
    "PERSONA_SCHEMA_JSON:",
    "INPUT_CATALOG_JSON:",
    "CONFIG_JSON:",
    "CONFIG_IMPORT:",
    "CONFIG_ACTION:",
    "VIRTUAL_INPUT_STATUS_JSON:",
    "ERROR:",
)


class SerialPort:
    def __init__(self, path: str, baud: int = BAUD) -> None:
        self._port = NativeSerialPort(path, baud)

    def close(self) -> None:
        self._port.close()

    def write_line(self, line: str) -> None:
        self._port.write_line(line)

    def read_text(self, timeout: float) -> str:
        return self._port.read_text(timeout)

    def command_response(self, command: str, timeout: float) -> list[str]:
        self.read_text(0.2)
        self.write_line(command)

        deadline = time.monotonic() + timeout
        buffer = ""
        matches: list[str] = []
        while time.monotonic() < deadline:
            buffer += self.read_text(0.2)
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.rstrip("\r")
                if line.startswith(PREFIXES):
                    matches.append(line)
                    if not line.startswith("USB_DEVICE:"):
                        return matches
        return matches


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("commands", nargs="+")
    args = parser.parse_args()

    serial = SerialPort(args.port)
    try:
        for command in args.commands:
            print(f">> {command}")
            responses = serial.command_response(command, args.timeout)
            if responses:
                for response in responses:
                    print(response)
            else:
                print("<no matching response>")
    finally:
        serial.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        raise SystemExit(130)
