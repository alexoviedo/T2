#!/usr/bin/env python3
"""Run the ASAP Generic Gamepad demo rehearsal and save a transcript."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import re
import select
import socket
import subprocess
import sys
import termios
import time
import tty
from dataclasses import dataclass
from typing import Any


BAUD = termios.B115200
DEFAULT_PORT = "/dev/cu.usbmodem5B5E0200881"
DEFAULT_SOURCE = "auto"
DEFAULT_STICK_VID = "044f"
DEFAULT_STICK_PID = "b10a"
DEFAULT_STICK_INTERFACE = "0"
DEFAULT_WITNESS_PORT = 8765
RESPONSE_PREFIXES = (
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
    "BRIDGE_STATUS:",
    "ERROR:",
)


@dataclass
class CommandRecord:
    command: str
    responses: list[str]

    def to_json(self) -> dict[str, object]:
        return {"command": self.command, "responses": self.responses}


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
                if line.startswith(RESPONSE_PREFIXES):
                    matches.append(line)
                    if not line.startswith("USB_DEVICE:"):
                        return matches
        return matches


def utc_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def print_record(record: CommandRecord) -> None:
    print(f">> {record.command}")
    if record.responses:
        for response in record.responses:
            print(response)
    else:
        print("<no matching response>")


def run_commands(serial: SerialPort, commands: list[str], timeout: float) -> list[CommandRecord]:
    records = []
    for command in commands:
        record = CommandRecord(command, serial.command_response(command, timeout))
        print_record(record)
        records.append(record)
    return records


def response_with_prefix(records: list[CommandRecord], prefix: str) -> str | None:
    for record in records:
        for response in record.responses:
            if response.startswith(prefix):
                return response
    return None


def responses_with_prefix(records: list[CommandRecord], prefix: str) -> list[str]:
    return [
        response
        for record in records
        for response in record.responses
        if response.startswith(prefix)
    ]


def parse_semicolon_fields(line: str | None) -> dict[str, str]:
    if line is None or ":" not in line:
        return {}
    fields: dict[str, str] = {}
    body = line.split(":", 1)[1]
    for item in body.split(";"):
        if not item or "=" not in item:
            continue
        key, value = item.split("=", 1)
        fields[key] = value
    return fields


def parse_int_field(fields: dict[str, str], key: str) -> int | None:
    try:
        return int(fields[key])
    except (KeyError, ValueError):
        return None


def normalize_hex_id(value: str) -> str:
    normalized = value.strip().lower()
    if normalized.startswith("0x"):
        normalized = normalized[2:]
    return normalized.zfill(4)


def parse_usb_devices(line: str | None) -> list[dict[str, str]]:
    if line is None or not line.startswith("USB_DEVICES:"):
        return []
    body = line.split(":", 1)[1]
    devices = []
    for device_text in body.split("|"):
        fields: dict[str, str] = {}
        for field_text in device_text.split(","):
            if "=" not in field_text:
                continue
            key, value = field_text.split("=", 1)
            fields[key] = value
        if fields:
            devices.append(fields)
    return devices


def has_usb_device(devices: list[dict[str, str]], vid: str, pid: str) -> bool:
    target_vid = normalize_hex_id(vid)
    target_pid = normalize_hex_id(pid)
    return any(
        normalize_hex_id(device.get("vid", "")) == target_vid
        and normalize_hex_id(device.get("pid", "")) == target_pid
        for device in devices
    )


def resolve_source(
    records: list[CommandRecord],
    requested_source: str,
    stick_vid: str,
    stick_pid: str,
    stick_interface: str,
) -> str | None:
    if requested_source.lower() != "auto":
        return requested_source

    target_vid = normalize_hex_id(stick_vid)
    target_pid = normalize_hex_id(stick_pid)
    for device in parse_usb_devices(response_with_prefix(records, "USB_DEVICES:")):
        if (
            normalize_hex_id(device.get("vid", "")) == target_vid
            and normalize_hex_id(device.get("pid", "")) == target_pid
            and "id" in device
        ):
            return f"{device['id']}:{stick_interface}"
    return None


def has_ble_connected(records: list[CommandRecord]) -> bool:
    return any(
        "ble=Connected" in response
        for record in records
        for response in record.responses
        if response.startswith("STATUS:")
    )


def wait_for_ble_connected(
    serial: SerialPort,
    records: list[CommandRecord],
    timeout: float,
    attempts: int,
    assume_ready: bool,
) -> bool:
    if has_ble_connected(records):
        return True

    print()
    print("BLE is advertising but not connected yet.")
    print("On the Mac, connect Bluetooth device: USB2BLE Gamepad.")
    for attempt in range(1, attempts + 1):
        if assume_ready:
            time.sleep(2.0)
        else:
            try:
                input(f"Press Enter to recheck BLE connection ({attempt}/{attempts})...")
            except EOFError:
                print("No interactive stdin available; rechecking after a short pause.")
                time.sleep(2.0)
        record = CommandRecord("GET_STATUS", serial.command_response("GET_STATUS", timeout))
        print_record(record)
        records.append(record)
        if has_ble_connected([record]):
            return True
    return False


def is_port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def read_process_lines(
    process: subprocess.Popen[str],
    expected_lines: int,
    timeout: float,
) -> list[str]:
    if process.stdout is None:
        return []
    deadline = time.monotonic() + timeout
    lines: list[str] = []
    while len(lines) < expected_lines and time.monotonic() < deadline:
        readable, _, _ = select.select([process.stdout], [], [], 0.1)
        if not readable:
            continue
        line = process.stdout.readline()
        if not line:
            break
        lines.append(line.rstrip("\n"))
    return lines


def start_witness_server(
    port: int,
    out_dir: pathlib.Path,
) -> tuple[subprocess.Popen[str] | None, list[str], pathlib.Path | None]:
    if not is_port_free(port):
        print(f"Browser witness port {port} is already in use; using the existing server.")
        return None, [], None

    out_dir.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(
        [
            sys.executable,
            "tools/gamepad_witness/server.py",
            "--port",
            str(port),
            "--out-dir",
            str(out_dir),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    lines = read_process_lines(process, expected_lines=3, timeout=5.0)
    capture_file = None
    for line in lines:
        print(line)
        marker = "Capture file: "
        if line.startswith(marker):
            capture_file = pathlib.Path(line[len(marker) :])
    return process, lines, capture_file


def open_browser(port: int) -> None:
    url = f"http://127.0.0.1:{port}/"
    if sys.platform == "darwin":
        subprocess.run(["open", url], check=False)
    else:
        print(f"Open browser witness: {url}")


def read_capture_tail(capture_file: pathlib.Path | None, max_lines: int = 8) -> list[str]:
    if capture_file is None or not capture_file.exists():
        return []
    lines = capture_file.read_text(encoding="utf-8").splitlines()
    return lines[-max_lines:]


def find_latest_capture_file(out_dir: pathlib.Path) -> pathlib.Path | None:
    captures = sorted(out_dir.glob("gamepad_witness_*.jsonl"), key=lambda path: path.stat().st_mtime)
    return captures[-1] if captures else None


def parse_capture(line: str) -> dict[str, Any] | None:
    try:
        value = json.loads(line)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def capture_shows_gamepad(capture_tail: list[str]) -> bool:
    for line in capture_tail:
        capture = parse_capture(line)
        if capture is None:
            continue
        if capture.get("connected") is True and "USB2BLE Gamepad" in str(capture.get("id", "")):
            return True
    return False


def capture_shows_stick_right(capture_tail: list[str]) -> bool:
    for line in capture_tail:
        capture = parse_capture(line)
        if capture is None:
            continue
        axes = capture.get("axes")
        if isinstance(axes, list) and axes and isinstance(axes[0], (int, float)) and axes[0] >= 0.9:
            return True
    return False


def capture_shows_input_change(capture_tail: list[str]) -> bool:
    return any(
        (capture := parse_capture(line)) is not None
        and capture.get("connected") is True
        and capture.get("type") == "change"
        for line in capture_tail
    )


def wait_for_capture_tail(
    capture_dir: pathlib.Path,
    capture_file: pathlib.Path | None,
    timeout: float,
) -> tuple[pathlib.Path | None, list[str]]:
    deadline = time.monotonic() + timeout
    current_file = capture_file
    tail: list[str] = []
    while time.monotonic() < deadline:
        if current_file is None:
            current_file = find_latest_capture_file(capture_dir)
        tail = read_capture_tail(current_file)
        if capture_shows_stick_right(tail):
            return current_file, tail
        time.sleep(0.2)
    return current_file, tail


def extract_axis(line: str | None, control: str) -> int | None:
    if line is None:
        return None
    match = re.search(rf"(?:^|;){re.escape(control)}=axis:([-0-9]+)(?:;|$)", line)
    if match is None:
        return None
    return int(match.group(1))


def analyze(
    preflight: list[CommandRecord],
    wake: list[CommandRecord],
    movement: list[CommandRecord],
    bridge: list[CommandRecord],
    source: str,
    stick_vid: str,
    stick_pid: str,
    capture_tail: list[str],
    require_browser_witness: bool,
    live_bridge: bool,
) -> dict[str, object]:
    usb_status = response_with_prefix(preflight, "USB_STATUS:")
    usb_devices = response_with_prefix(preflight, "USB_DEVICES:")
    devices = parse_usb_devices(usb_devices)
    status_lines = [
        response
        for records in (preflight, wake)
        for record in records
        for response in record.responses
        if response.startswith("STATUS:")
    ]
    normalized = response_with_prefix(movement, "NORMALIZED_INPUT:")
    mapping = response_with_prefix(movement, "GENERIC_GAMEPAD_MAPPING:")
    publish = next(
        (
            response
            for record in movement
            for response in record.responses
            if response.startswith("BLE_ACTION:action=publish_generic_gamepad;")
        ),
        None,
    )
    bridge_statuses = responses_with_prefix(bridge, "BRIDGE_STATUS:")
    bridge_start_status = next(
        (line for line in bridge_statuses if "enabled=true" in line),
        None,
    )
    bridge_stop_status = next(
        (line for line in reversed(bridge_statuses) if "enabled=false" in line),
        None,
    )
    bridge_enabled_fields = parse_semicolon_fields(bridge_start_status)
    bridge_status_fields = [parse_semicolon_fields(line) for line in bridge_statuses]
    bridge_published_values = [
        value
        for fields in bridge_status_fields
        for value in [parse_int_field(fields, "published")]
        if value is not None
    ]
    bridge_published_delta = (
        bridge_published_values[-1] - bridge_published_values[0]
        if len(bridge_published_values) >= 2
        else 0
    )
    axis_x = extract_axis(normalized, "axis_01_30")
    source_parts = source.split(":", 1)
    source_device = source_parts[0]
    source_interface = source_parts[1] if len(source_parts) > 1 else "0"
    expected_mapping = (
        f"src={source_device}:{source_interface}:"
        f"{normalize_hex_id(stick_vid)}:{normalize_hex_id(stick_pid)}:"
        "axis_01_30,target=x"
    )

    checks = {
        "usb_has_hub": has_usb_device(devices, "2109", "2813"),
        "usb_has_twcs": has_usb_device(devices, "044f", "b687"),
        "usb_has_t16000m": has_usb_device(devices, stick_vid, stick_pid),
        "usb_has_two_hid_interfaces": usb_status is not None and "interfaces=2" in usb_status,
        "ble_connected": any("ble=Connected" in line for line in status_lines),
        "flight_pack_profile": mapping is not None and "profile=flight_pack_demo" in mapping,
        "stick_x_maps_to_gamepad_x": mapping is not None and expected_mapping in mapping,
    }
    if live_bridge:
        checks["bridge_enabled"] = (
            bridge_start_status is not None
            and bridge_enabled_fields.get("persona") == "generic_gamepad"
        )
        checks["bridge_published_increased"] = bridge_published_delta > 0
        checks["bridge_stopped"] = bridge_stop_status is not None
    else:
        checks["stick_x_fully_right"] = axis_x is not None and axis_x >= 30000
        checks["publish_connected"] = publish is not None and "state=Connected" in publish
    if require_browser_witness:
        if live_bridge:
            checks["browser_saw_input_change"] = capture_shows_input_change(capture_tail)
        else:
            checks["browser_saw_usb2ble_gamepad"] = capture_shows_gamepad(capture_tail)
            checks["browser_saw_stick_right"] = capture_shows_stick_right(capture_tail)
    return {
        "checks": checks,
        "axis_01_30": axis_x,
        "usb_status": usb_status,
        "usb_devices": usb_devices,
        "publish": publish,
        "bridge_statuses": bridge_statuses,
        "bridge_published_delta": bridge_published_delta,
    }


def prompt(message: str, assume_yes: bool) -> None:
    print()
    print(message)
    if not assume_yes:
        try:
            input("Press Enter when ready...")
        except EOFError:
            print("No interactive stdin available; continuing.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument(
        "--source",
        default=DEFAULT_SOURCE,
        help="USB source as device:interface, or 'auto' to find the T.16000M by VID/PID.",
    )
    parser.add_argument("--stick-vid", default=DEFAULT_STICK_VID)
    parser.add_argument("--stick-pid", default=DEFAULT_STICK_PID)
    parser.add_argument("--stick-interface", default=DEFAULT_STICK_INTERFACE)
    parser.add_argument("--timeout", type=float, default=4.0)
    parser.add_argument("--out-dir", default="target/asap-demo-rehearsal")
    parser.add_argument("--witness-port", type=int, default=DEFAULT_WITNESS_PORT)
    parser.add_argument("--no-browser-witness", action="store_true")
    parser.add_argument("--no-open", action="store_true")
    parser.add_argument("--assume-ready", action="store_true")
    parser.add_argument("--connect-attempts", type=int, default=6)
    parser.add_argument(
        "--live-bridge",
        action="store_true",
        help="Use START_BRIDGE/STOP_BRIDGE and verify automatic publish counters.",
    )
    parser.add_argument("--bridge-duration", type=float, default=6.0)
    args = parser.parse_args()

    stamp = utc_stamp()
    out_dir = pathlib.Path(args.out_dir)
    run_dir = out_dir / f"demo_rehearsal_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    transcript_file = run_dir / "serial_transcript.txt"
    summary_file = run_dir / "summary.json"
    capture_file: pathlib.Path | None = None
    capture_dir = run_dir / "gamepad-witness"
    server: subprocess.Popen[str] | None = None
    server_lines: list[str] = []
    preflight: list[CommandRecord] = []
    wake: list[CommandRecord] = []
    movement: list[CommandRecord] = []
    bridge: list[CommandRecord] = []

    print("USB2BLE ASAP demo rehearsal")
    print(f"Transcript directory: {run_dir}")
    print()

    try:
        if not args.no_browser_witness:
            server, server_lines, capture_file = start_witness_server(
                args.witness_port,
                capture_dir,
            )
            if not args.no_open:
                open_browser(args.witness_port)
            prompt(
                (
                    "In the browser witness page, click Arm and keep the tab focused. "
                    "If it already shows USB2BLE Gamepad connected and no Arm button, continue."
                ),
                args.assume_ready,
            )

        serial = SerialPort(args.port)
        try:
            preflight = run_commands(
                serial,
                [
                    "GET_STATUS",
                    "GET_USB_STATUS",
                    "LIST_USB_DEVICES",
                    "START_BLE_GENERIC_GAMEPAD",
                    "GET_STATUS",
                ],
                args.timeout,
            )
            source = resolve_source(
                preflight,
                args.source,
                args.stick_vid,
                args.stick_pid,
                args.stick_interface,
            )
            if source is None:
                print(
                    "ERROR: could not auto-detect the T.16000M source from LIST_USB_DEVICES. "
                    "Use --source <device>:<interface> to override."
                )
                return 2
            print(f"Using movement source: {source}")

            if not wait_for_ble_connected(
                serial,
                preflight,
                args.timeout,
                args.connect_attempts,
                args.assume_ready,
            ):
                print("ERROR: BLE did not reach Connected; aborting before wake/publish.")
                return 2
            print()
            print("Waking the browser Gamepad API with explicit BLE reports.")
            wake = run_commands(
                serial,
                [
                    "SEND_BLE_SELF_TEST_REPORT",
                    "PUBLISH_GENERIC_GAMEPAD_REPORT",
                    "SEND_BLE_SELF_TEST_REPORT",
                    "PUBLISH_GENERIC_GAMEPAD_REPORT",
                    "GET_STATUS",
                ],
                args.timeout,
            )
            prompt(
                (
                    "Move only the T.16000M stick fully right and hold it there. "
                    "Do not touch the TWCS or press buttons."
                ),
                args.assume_ready,
            )
            if args.live_bridge:
                bridge = run_commands(
                    serial,
                    ["GET_BRIDGE_STATUS", "START_BRIDGE", "GET_BRIDGE_STATUS"],
                    args.timeout,
                )
                print()
                print(
                    f"Keep moving or holding the control for {args.bridge_duration:.1f} seconds "
                    "while live bridge mode publishes automatically."
                )
                time.sleep(args.bridge_duration)
                bridge.extend(
                    run_commands(
                        serial,
                        ["GET_BRIDGE_STATUS", "STOP_BRIDGE", "GET_BRIDGE_STATUS"],
                        args.timeout,
                    )
                )
                movement = run_commands(
                    serial,
                    [
                        f"GET_LAST_USB_REPORT {source}",
                        f"GET_NORMALIZED_INPUT {source}",
                        "GET_GENERIC_GAMEPAD_MAPPING",
                        "GET_GENERIC_GAMEPAD_REPORT",
                    ],
                    args.timeout,
                )
            else:
                movement = run_commands(
                    serial,
                    [
                        f"GET_LAST_USB_REPORT {source}",
                        f"GET_NORMALIZED_INPUT {source}",
                        "GET_GENERIC_GAMEPAD_MAPPING",
                        "GET_GENERIC_GAMEPAD_REPORT",
                        "PUBLISH_GENERIC_GAMEPAD_REPORT",
                    ],
                    args.timeout,
                )
        finally:
            serial.close()

        print()
        print("Release the stick back to center.")
        capture_file, capture_tail = wait_for_capture_tail(
            capture_dir,
            capture_file,
            timeout=5.0 if not args.no_browser_witness else 0.1,
        )
        analysis = analyze(
            preflight,
            wake,
            movement,
            bridge,
            source,
            args.stick_vid,
            args.stick_pid,
            capture_tail,
            require_browser_witness=not args.no_browser_witness,
            live_bridge=args.live_bridge,
        )

        transcript_lines: list[str] = []
        for section, records in (
            ("preflight", preflight),
            ("wake", wake),
            ("bridge", bridge),
            ("movement", movement),
        ):
            transcript_lines.append(f"# {section}")
            for record in records:
                transcript_lines.append(f">> {record.command}")
                transcript_lines.extend(record.responses or ["<no matching response>"])
            transcript_lines.append("")
        transcript_file.write_text("\n".join(transcript_lines), encoding="utf-8")

        payload: dict[str, Any] = {
            "captured_at": stamp,
            "port": args.port,
            "requested_source": args.source,
            "source": source,
            "stick_vid": normalize_hex_id(args.stick_vid),
            "stick_pid": normalize_hex_id(args.stick_pid),
            "stick_interface": args.stick_interface,
            "transcript": str(transcript_file),
            "browser_witness_capture": None if capture_file is None else str(capture_file),
            "browser_witness_tail": capture_tail,
            "server_output": server_lines,
            "live_bridge": args.live_bridge,
            "analysis": analysis,
            "preflight": [record.to_json() for record in preflight],
            "wake": [record.to_json() for record in wake],
            "bridge": [record.to_json() for record in bridge],
            "movement": [record.to_json() for record in movement],
        }
        summary_file.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        print()
        print("Checks:")
        checks = analysis["checks"]
        assert isinstance(checks, dict)
        for name, passed in checks.items():
            print(f"  {'PASS' if passed else 'FAIL'} {name}")
        if capture_tail:
            print()
            print("Browser witness tail:")
            for line in capture_tail[-3:]:
                print(f"  {line}")
        print()
        print(f"Saved transcript: {transcript_file}")
        print(f"Saved summary: {summary_file}")
        return 0 if all(bool(value) for value in checks.values()) else 2
    finally:
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=3.0)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        raise SystemExit(130)
