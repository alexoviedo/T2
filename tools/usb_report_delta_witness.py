#!/usr/bin/env python3
"""Capture before/after deltas from GET_LAST_USB_REPORT over serial."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import select
import termios
import time
import tty


BAUD = termios.B115200
PREFIX = "USB_REPORT:"


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

    def command_response(self, command: str, prefix: str, timeout: float) -> str:
        self.read_text(0.2)
        self.write_line(command)

        deadline = time.monotonic() + timeout
        buffer = ""
        while time.monotonic() < deadline:
            buffer += self.read_text(0.2)
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.rstrip("\r")
                if line.startswith(prefix):
                    return line
        raise TimeoutError(f"no {prefix} response for {command!r}")


def parse_usb_report(line: str) -> bytes:
    if not line.startswith(PREFIX):
        raise ValueError(f"unexpected response: {line!r}")
    return bytes.fromhex(line[len(PREFIX) :].strip())


def byte_deltas(before: bytes, after: bytes) -> list[dict[str, int | None]]:
    changes: list[dict[str, int | None]] = []
    max_len = max(len(before), len(after))
    for index in range(max_len):
        old = before[index] if index < len(before) else None
        new = after[index] if index < len(after) else None
        if old != new:
            changes.append({"offset": index, "before": old, "after": new})
    return changes


def first_change_per_offset(changes_by_sample: list[dict[str, object]]) -> list[dict[str, object]]:
    by_offset: dict[int, dict[str, object]] = {}
    for change in changes_by_sample:
        offset = int(change["offset"])
        by_offset.setdefault(offset, change)
    return [by_offset[offset] for offset in sorted(by_offset)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--source", required=True, help="device:interface, for example 2:0")
    parser.add_argument("--label", default="movement")
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--watch-seconds", type=float, default=0.0)
    parser.add_argument("--sample-interval", type=float, default=0.25)
    parser.add_argument("--out-dir", default="target/usb-report-delta-witness")
    args = parser.parse_args()

    command = f"GET_LAST_USB_REPORT {args.source}"
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"usb_report_delta_{stamp}_{args.label}.json"

    serial = SerialPort(args.port)
    try:
        print(f"Capturing baseline {command}...")
        before_line = serial.command_response(command, PREFIX, args.timeout)
        before = parse_usb_report(before_line)
        print(f"Baseline bytes: {len(before)}")
        print()
        sample_lines: list[str] = []
        samples: list[bytes] = []
        if args.watch_seconds > 0:
            print("Move exactly one control during the watch window.")
            input("Press Enter to start the watch window...")
            print(f"Watching for {args.watch_seconds:.1f}s...")
            deadline = time.monotonic() + args.watch_seconds
            while time.monotonic() < deadline:
                line = serial.command_response(command, PREFIX, args.timeout)
                sample_lines.append(line)
                samples.append(parse_usb_report(line))
                time.sleep(args.sample_interval)
            after = samples[-1] if samples else before
            after_line = sample_lines[-1] if sample_lines else before_line
            changes_by_sample = []
            for sample_index, sample in enumerate(samples, start=1):
                for change in byte_deltas(before, sample):
                    changes_by_sample.append({"sample": sample_index, **change})
            changes = first_change_per_offset(changes_by_sample)
        else:
            print("Move and hold exactly one control now.")
            input("Press Enter while holding that control...")
            after_line = serial.command_response(command, PREFIX, args.timeout)
            after = parse_usb_report(after_line)
            changes_by_sample = []
            changes = byte_deltas(before, after)
    finally:
        serial.close()

    payload = {
        "label": args.label,
        "captured_at": stamp,
        "port": args.port,
        "source": args.source,
        "command": command,
        "before_line": before_line,
        "after_line": after_line,
        "watch_seconds": args.watch_seconds,
        "sample_lines": sample_lines,
        "changed_by_sample": changes_by_sample,
        "changed": changes,
    }
    out_file.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print()
    print("Raw USB report byte deltas:")
    if not changes:
        print("  none")
    else:
        for change in changes[:32]:
            old = change["before"]
            new = change["after"]
            print(f"  byte[{change['offset']}]: {old!r} -> {new!r}")
        if len(changes) > 32:
            print(f"  ... {len(changes) - 32} more")
    print()
    print(f"Saved raw witness: {out_file}")
    return 0 if changes else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nCancelled.")
        raise SystemExit(130)
