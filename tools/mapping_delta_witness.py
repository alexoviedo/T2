#!/usr/bin/env python3
"""Capture before/after deltas from GET_GENERIC_GAMEPAD_MAPPING over serial."""

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
from dataclasses import dataclass
from typing import Iterable


BAUD = termios.B115200
PREFIX = "GENERIC_GAMEPAD_MAPPING:"


@dataclass(frozen=True)
class MappingEntry:
    src: str
    target: str
    value: str
    reason: str


class SerialPort:
    def __init__(self, path: str, baud: int = BAUD) -> None:
        self.path = path
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


def parse_mapping(line: str) -> dict[str, MappingEntry]:
    _, _, tail = line.partition("mappings=")
    if not tail:
        raise ValueError("mapping response did not include mappings=")

    entries: dict[str, MappingEntry] = {}
    for raw_entry in tail.rstrip(";").split("|"):
        fields = {}
        for raw_field in raw_entry.split(","):
            key, sep, value = raw_field.partition("=")
            if sep:
                fields[key] = value
        src = fields.get("src")
        if not src:
            continue
        entries[src] = MappingEntry(
            src=src,
            target=fields.get("target", "none"),
            value=fields.get("value", ""),
            reason=fields.get("reason", ""),
        )
    return entries


def changed_entries(
    before: dict[str, MappingEntry], after: dict[str, MappingEntry]
) -> list[tuple[MappingEntry | None, MappingEntry | None]]:
    changes = []
    for src in sorted(set(before) | set(after)):
        old = before.get(src)
        new = after.get(src)
        if old != new:
            changes.append((old, new))
    return changes


def changed_entries_by_sample(
    baseline: dict[str, MappingEntry],
    samples: list[dict[str, MappingEntry]],
) -> list[dict[str, object]]:
    changed: list[dict[str, object]] = []
    for sample_index, sample in enumerate(samples, start=1):
        for old, new in changed_entries(baseline, sample):
            current = new or old
            if current is None:
                continue
            changed.append(
                {
                    "sample": sample_index,
                    "src": current.src,
                    "before": None if old is None else old.__dict__,
                    "after": None if new is None else new.__dict__,
                }
            )
    return changed


def collapse_changed_samples(changed: list[dict[str, object]]) -> list[dict[str, object]]:
    by_src: dict[str, dict[str, object]] = {}
    for change in changed:
        src = str(change["src"])
        by_src.setdefault(src, change)
    return [by_src[src] for src in sorted(by_src)]


def print_changes(changes: Iterable[tuple[MappingEntry | None, MappingEntry | None]]) -> None:
    mapped = []
    unmapped = []
    for old, new in changes:
        current = new or old
        if current is None:
            continue
        if current.target == "none":
            unmapped.append((old, new))
        else:
            mapped.append((old, new))

    def emit(title: str, rows: list[tuple[MappingEntry | None, MappingEntry | None]]) -> None:
        print(title)
        if not rows:
            print("  none")
            return
        for old, new in rows:
            src = (new or old).src  # type: ignore[union-attr]
            old_value = old.value if old else "<missing>"
            new_value = new.value if new else "<missing>"
            target = new.target if new else old.target  # type: ignore[union-attr]
            reason = new.reason if new else old.reason  # type: ignore[union-attr]
            print(f"  {src} -> {target}: {old_value} -> {new_value} ({reason})")

    emit("Mapped target deltas:", mapped)
    emit("Unmapped/source-only deltas:", unmapped)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--label", default="movement")
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--watch-seconds", type=float, default=0.0)
    parser.add_argument("--sample-interval", type=float, default=0.25)
    parser.add_argument("--out-dir", default="target/mapping-delta-witness")
    args = parser.parse_args()

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"mapping_delta_{stamp}_{args.label}.json"

    serial = SerialPort(args.port)
    try:
        print("Capturing baseline GET_GENERIC_GAMEPAD_MAPPING...")
        before_line = serial.command_response("GET_GENERIC_GAMEPAD_MAPPING", PREFIX, args.timeout)
        before = parse_mapping(before_line)
        print(f"Baseline entries: {len(before)}")
        print()
        if args.watch_seconds > 0:
            print("Move exactly one control during the watch window.")
            input("Press Enter to start the watch window...")
            print(f"Watching for {args.watch_seconds:.1f}s...")
            sample_lines = []
            samples = []
            deadline = time.monotonic() + args.watch_seconds
            while time.monotonic() < deadline:
                line = serial.command_response(
                    "GET_GENERIC_GAMEPAD_MAPPING", PREFIX, args.timeout
                )
                sample_lines.append(line)
                samples.append(parse_mapping(line))
                time.sleep(args.sample_interval)
            after_line = sample_lines[-1] if sample_lines else before_line
            changes_by_sample = changed_entries_by_sample(before, samples)
            collapsed_changes = collapse_changed_samples(changes_by_sample)
            changes = [
                (
                    None
                    if change["before"] is None
                    else MappingEntry(**change["before"]),  # type: ignore[arg-type]
                    None
                    if change["after"] is None
                    else MappingEntry(**change["after"]),  # type: ignore[arg-type]
                )
                for change in collapsed_changes
            ]
        else:
            print("Move and hold exactly one control now.")
            input("Press Enter while holding that control...")
            after_line = serial.command_response(
                "GET_GENERIC_GAMEPAD_MAPPING", PREFIX, args.timeout
            )
            after = parse_mapping(after_line)
            changes_by_sample = []
            sample_lines = []
            changes = changed_entries(before, after)
    finally:
        serial.close()

    payload = {
        "label": args.label,
        "captured_at": stamp,
        "port": args.port,
        "before_line": before_line,
        "after_line": after_line,
        "watch_seconds": args.watch_seconds,
        "sample_lines": sample_lines,
        "changed_by_sample": changes_by_sample,
        "changed": [
            {
                "src": (new or old).src,
                "before": None if old is None else old.__dict__,
                "after": None if new is None else new.__dict__,
            }
            for old, new in changes
        ],
    }
    out_file.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print()
    print_changes(changes)
    print()
    print(f"Saved raw witness: {out_file}")
    return 0 if changes else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nCancelled.")
        raise SystemExit(130)
