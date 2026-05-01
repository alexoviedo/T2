#!/usr/bin/env python3
"""Capture detach cleanup evidence from the serial control plane."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import select
import sys
import termios
import time
import tty


BAUD = termios.B115200
RESPONSE_PREFIXES = (
    "USB_STATUS:",
    "USB_DEVICES:",
    "USB_DESCRIPTOR:",
    "USB_REPORT:",
    "HID_SUMMARY:",
    "NORMALIZED_INPUT:",
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

    def read_lines(self, timeout: float) -> list[str]:
        text = self.read_text(timeout)
        return [line.rstrip("\r") for line in text.split("\n") if line.rstrip("\r")]

    def command_response(self, command: str, timeout: float) -> list[str]:
        self.read_text(0.2)
        self.write_line(command)

        deadline = time.monotonic() + timeout
        buffer = ""
        responses: list[str] = []
        while time.monotonic() < deadline:
            buffer += self.read_text(0.2)
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.rstrip("\r")
                if line.startswith(RESPONSE_PREFIXES):
                    responses.append(line)
                    if not line.startswith("USB_DEVICES:"):
                        return responses
        return responses


def run_commands(serial: SerialPort, commands: list[str], timeout: float) -> list[dict[str, object]]:
    results = []
    for command in commands:
        responses = serial.command_response(command, timeout)
        results.append({"command": command, "responses": responses})
        print(f">> {command}")
        if responses:
            for response in responses:
                print(response)
        else:
            print("<no matching response>")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--label", default="detach_cleanup")
    parser.add_argument("--timeout", type=float, default=4.0)
    parser.add_argument("--watch-seconds", type=float, default=12.0)
    parser.add_argument("--source", required=True, help="device:interface to verify after detach")
    parser.add_argument("--out-dir", default="target/detach-cleanup-witness")
    args = parser.parse_args()

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"detach_cleanup_{stamp}_{args.label}.json"

    serial = SerialPort(args.port)
    try:
        before_commands = [
            "GET_USB_STATUS",
            "LIST_USB_DEVICES",
            f"GET_HID_SUMMARY {args.source}",
            f"GET_LAST_USB_REPORT {args.source}",
        ]
        after_commands = [
            "GET_USB_STATUS",
            "LIST_USB_DEVICES",
            f"GET_HID_SUMMARY {args.source}",
            f"GET_LAST_USB_REPORT {args.source}",
        ]

        print("Before detach:")
        before = run_commands(serial, before_commands, args.timeout)
        print()
        print("Detach exactly the requested downstream USB device during the watch window.")
        input("Press Enter to start the detach watch window...")
        print(f"Watching for {args.watch_seconds:.1f}s...")
        lines = serial.read_lines(args.watch_seconds)
        detach_lines = [line for line in lines if line.startswith("[DETACH]")]
        for line in detach_lines:
            print(line)
        if not detach_lines:
            print("<no detach line captured>")
        print()
        print("After detach:")
        after = run_commands(serial, after_commands, args.timeout)
    finally:
        serial.close()

    payload = {
        "label": args.label,
        "captured_at": stamp,
        "port": args.port,
        "source": args.source,
        "before": before,
        "watch_seconds": args.watch_seconds,
        "watch_lines": lines,
        "detach_lines": detach_lines,
        "after": after,
    }
    out_file.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print()
    print(f"Saved raw witness: {out_file}")
    return 0 if detach_lines else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        raise SystemExit(130)
