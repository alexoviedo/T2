#!/usr/bin/env python3
"""Send one or more serial control-plane commands and print matching responses."""

from __future__ import annotations

import argparse
import os
import select
import sys
import termios
import time
import tty


BAUD = termios.B115200
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
    "ERROR:",
)


class SerialPort:
    def __init__(self, path: str, baud: int = BAUD) -> None:
        self.fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        self._previous_attrs = termios.tcgetattr(self.fd)

        attrs = termios.tcgetattr(self.fd)
        tty.setraw(self.fd)
        attrs = termios.tcgetattr(self.fd)
        attrs[4] = baud
        attrs[5] = baud
        attrs[2] |= termios.CLOCAL | termios.CREAD
        termios.tcsetattr(self.fd, termios.TCSANOW, attrs)

    def close(self) -> None:
        termios.tcsetattr(self.fd, termios.TCSANOW, self._previous_attrs)
        os.close(self.fd)

    def write_line(self, line: str) -> None:
        os.write(self.fd, (line.rstrip("\r\n") + "\n").encode("utf-8"))

    def read_text(self, timeout: float) -> str:
        deadline = time.monotonic() + timeout
        chunks: list[bytes] = []
        while time.monotonic() < deadline:
            remaining = max(0.0, deadline - time.monotonic())
            readable, _, _ = select.select([self.fd], [], [], min(0.1, remaining))
            if not readable:
                continue
            try:
                chunk = os.read(self.fd, 8192)
            except BlockingIOError:
                continue
            if chunk:
                chunks.append(chunk)
        return b"".join(chunks).decode("utf-8", errors="replace")

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
