#!/usr/bin/env python3
"""Run a macOS HID event probe for USB2BLE Gamepad devices."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import subprocess
import sys
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
SWIFT_SOURCE = pathlib.Path(__file__).with_suffix(".swift")


def utc_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_command(command: list[str], timeout: float | None = None) -> tuple[int, str]:
    result = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )
    return result.returncode, result.stdout


def load_jsonl(path: pathlib.Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def summarize_events(rows: list[dict[str, Any]]) -> dict[str, Any]:
    devices = [row for row in rows if row.get("type") == "device"]
    elements = [row for row in rows if row.get("type") == "element"]
    events = [row for row in rows if row.get("type") == "input_value"]
    element_usages = sorted(
        {
            f"{element.get('usage_page')}:{element.get('usage')}"
            for element in elements
            if element.get("usage_page") is not None and element.get("usage") is not None
        }
    )
    usages = sorted(
        {
            f"{event.get('usage_page')}:{event.get('usage')}"
            for event in events
            if event.get("usage_page") is not None and event.get("usage") is not None
        }
    )
    return {
        "device_count": len(devices),
        "element_count": len(elements),
        "event_count": len(events),
        "products": sorted({str(device.get("product", "")) for device in devices if device.get("product")}),
        "transports": sorted({str(device.get("transport", "")) for device in devices if device.get("transport")}),
        "vendor_product_ids": sorted(
            {
                f"{int(device.get('vendor_id')):04x}:{int(device.get('product_id')):04x}"
                for device in devices
                if device.get("vendor_id") is not None and device.get("product_id") is not None
            }
        ),
        "element_usages": element_usages,
        "changed_usages": usages,
        "hid_events_seen": len(events) > 0,
    }


def compile_swift(binary: pathlib.Path) -> tuple[bool, str]:
    binary.parent.mkdir(parents=True, exist_ok=True)
    returncode, output = run_command(["swiftc", str(SWIFT_SOURCE), "-o", str(binary)], timeout=30)
    return returncode == 0, output


def fallback_snapshot(out_dir: pathlib.Path) -> dict[str, Any]:
    snapshots: dict[str, Any] = {}
    for name, command in {
        "hidutil_list": ["hidutil", "list"],
        "ioreg_hid": ["ioreg", "-r", "-c", "IOHIDDevice", "-l"],
        "system_profiler_bluetooth": ["system_profiler", "SPBluetoothDataType"],
    }.items():
        try:
            returncode, output = run_command(command, timeout=20)
        except (OSError, subprocess.TimeoutExpired) as exc:
            returncode, output = 1, str(exc)
        (out_dir / f"{name}.txt").write_text(output, encoding="utf-8", errors="replace")
        snapshots[name] = {"returncode": returncode, "path": str(out_dir / f"{name}.txt")}
    return snapshots


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=float, default=10.0)
    parser.add_argument("--product-contains", default="USB2BLE Gamepad")
    parser.add_argument("--out-dir", type=pathlib.Path, default=pathlib.Path("target/generic-hid-delivery-diagnosis"))
    parser.add_argument("--binary")
    args = parser.parse_args()

    stamp = utc_stamp()
    run_dir = args.out_dir / f"macos_hid_event_probe_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    output_jsonl = run_dir / "macos_hid_events.jsonl"
    binary = pathlib.Path(args.binary) if args.binary else run_dir / "macos_hid_event_probe"

    compile_ok, compile_output = compile_swift(binary)
    (run_dir / "swift_compile.txt").write_text(compile_output, encoding="utf-8", errors="replace")

    run_result: dict[str, Any]
    if compile_ok:
        command = [
            str(binary),
            "--duration",
            str(args.duration),
            "--product-contains",
            args.product_contains,
            "--out",
            str(output_jsonl),
        ]
        try:
            returncode, output = run_command(command, timeout=args.duration + 10)
        except subprocess.TimeoutExpired as exc:
            returncode, output = 124, str(exc)
        (run_dir / "macos_hid_event_probe_stdout.txt").write_text(output, encoding="utf-8", errors="replace")
        run_result = {"command": command, "returncode": returncode, "stdout_path": str(run_dir / "macos_hid_event_probe_stdout.txt")}
    else:
        output_jsonl.touch()
        run_result = {"command": None, "returncode": None, "error": "swift_compile_failed"}

    snapshots = fallback_snapshot(run_dir)
    rows = load_jsonl(output_jsonl)
    summary = {
        "captured_at": stamp,
        "run_dir": str(run_dir),
        "product_contains": args.product_contains,
        "duration_seconds": args.duration,
        "swift_compile_ok": compile_ok,
        "run_result": run_result,
        "event_file": str(output_jsonl),
        "fallback_snapshots": snapshots,
        **summarize_events(rows),
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    notes = [
        "# macOS HID Event Probe",
        "",
        f"- Product filter: `{args.product_contains}`",
        f"- Swift compile: `{compile_ok}`",
        f"- Devices matched: `{summary['device_count']}`",
        f"- HID input events: `{summary['event_count']}`",
        f"- Event file: `{output_jsonl}`",
    ]
    (run_dir / "operator_notes.md").write_text("\n".join(notes) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if compile_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
