#!/usr/bin/env python3
"""Capture runtime-config import/save/load/start evidence over USB serial."""

from __future__ import annotations

import argparse
import base64
import dataclasses
import datetime as dt
import glob
import hashlib
import json
import os
import pathlib
import select
import sys
import termios
import time
import tty
from typing import Any


CHUNK_BYTES = 72
DEFAULT_OUT_DIR = pathlib.Path("target/config-persistence-witness")
DEFAULT_TIMEOUT = 8.0
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
    "CONFIG_STATUS:",
    "CONFIG_SCHEMA_JSON:",
    "PERSONA_SCHEMA_JSON:",
    "INPUT_CATALOG_JSON:",
    "CONFIG_JSON:",
    "CONFIG_IMPORT:",
    "CONFIG_ACTION:",
    "ERROR:",
)
BAUD_RATES = {
    rate: getattr(termios, name)
    for rate, name in (
        (9600, "B9600"),
        (19200, "B19200"),
        (38400, "B38400"),
        (57600, "B57600"),
        (115200, "B115200"),
        (230400, "B230400"),
        (460800, "B460800"),
        (921600, "B921600"),
    )
    if hasattr(termios, name)
}


@dataclasses.dataclass
class CommandRecord:
    section: str
    command: str
    responses: list[str]

    def to_json(self) -> dict[str, object]:
        return {
            "section": self.section,
            "command": self.command,
            "responses": self.responses,
        }


class SerialPort:
    def __init__(self, path: str, baud: int) -> None:
        if baud not in BAUD_RATES:
            supported = ", ".join(str(rate) for rate in sorted(BAUD_RATES))
            raise ValueError(f"unsupported baud {baud}; supported: {supported}")
        self.fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        self._previous_attrs = termios.tcgetattr(self.fd)

        tty.setraw(self.fd)
        attrs = termios.tcgetattr(self.fd)
        attrs[4] = BAUD_RATES[baud]
        attrs[5] = BAUD_RATES[baud]
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


def likely_serial_ports() -> list[str]:
    patterns = (
        "/dev/cu.usb*",
        "/dev/cu.wch*",
        "/dev/cu.SLAB*",
        "/dev/cu.*modem*",
        "/dev/tty.usb*",
        "/dev/ttyACM*",
        "/dev/ttyUSB*",
    )
    ports: set[str] = set()
    for pattern in patterns:
        ports.update(glob.glob(pattern))
    return sorted(ports)


def print_record(record: CommandRecord) -> None:
    print(f">> {record.command}")
    if record.responses:
        for response in record.responses:
            print(response)
    else:
        print("<no matching response>")


def send(
    serial: SerialPort,
    records: list[CommandRecord],
    section: str,
    command: str,
    timeout: float,
) -> CommandRecord:
    record = CommandRecord(section, command, serial.command_response(command, timeout))
    print_record(record)
    records.append(record)
    return record


def thrustmaster_rule(
    product_id: int,
    source_control_id: str,
    target_control_id: str,
    *,
    transform: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "source_vendor_id": 0x044F,
        "source_product_id": product_id,
        "source_interface_id": 0,
        "source_control_id": source_control_id,
        "target_control_id": target_control_id,
        "invert": False,
        "deadzone": None,
        "transform": transform,
    }


def runtime_config(persona: str, profile: str, auto_start_bridge: bool) -> dict[str, Any]:
    persona_id = {
        "generic": "generic_gamepad",
        "xbox": "xbox_wireless_controller",
    }[persona]
    if profile == "minimal":
        selected_profile = "generic_auto" if persona == "generic" else "xbox_auto"
        mappings: list[dict[str, Any]] = []
    elif profile in ("flight-pack", "custom_runtime"):
        selected_profile = "custom_runtime"
        if persona == "generic":
            mappings = [
                thrustmaster_rule(0xB10A, "axis_01_30", "x"),
                thrustmaster_rule(0xB10A, "axis_01_31", "y"),
                thrustmaster_rule(0xB687, "axis_01_32", "z"),
                thrustmaster_rule(0xB687, "axis_01_36", "rx"),
            ]
        else:
            mappings = [
                thrustmaster_rule(0xB10A, "axis_01_30", "left_x"),
                thrustmaster_rule(0xB10A, "axis_01_31", "left_y"),
                thrustmaster_rule(0xB687, "axis_01_36", "right_x"),
                thrustmaster_rule(
                    0xB687,
                    "axis_01_32",
                    "right_trigger",
                    transform={
                        "type": "axis_to_trigger",
                        "source_min": -32768,
                        "source_max": 32767,
                        "invert": False,
                    },
                ),
                thrustmaster_rule(0xB10A, "hat_01_39", "hat"),
                thrustmaster_rule(0xB10A, "button_1", "a"),
                thrustmaster_rule(0xB10A, "button_2", "b"),
                thrustmaster_rule(0xB10A, "button_3", "x"),
                thrustmaster_rule(0xB10A, "button_4", "y"),
            ]
    elif profile in ("generic_auto", "flight_pack_demo"):
        if persona != "generic":
            raise ValueError(f"profile {profile} is only valid with --persona generic")
        selected_profile = profile
        mappings = []
    elif profile in ("xbox_auto", "xbox_flight_pack_demo"):
        if persona != "xbox":
            raise ValueError(f"profile {profile} is only valid with --persona xbox")
        selected_profile = profile
        mappings = []
    else:
        raise ValueError(f"unsupported profile {profile}")

    return {
        "schema_version": 1,
        "metadata_version": 1,
        "display_name": f"Config Witness {persona.title()} {profile}",
        "selected_persona": persona_id,
        "selected_profile": selected_profile,
        "bridge": {
            "auto_start_persona": True,
            "auto_start_bridge": auto_start_bridge,
            "rate_hz": 50,
        },
        "mappings": mappings,
    }


def minified_json_bytes(config: dict[str, Any]) -> bytes:
    return json.dumps(config, sort_keys=True, separators=(",", ":")).encode("utf-8")


def import_config(
    serial: SerialPort,
    records: list[CommandRecord],
    payload: bytes,
    timeout: float,
) -> None:
    chunks = [
        base64.urlsafe_b64encode(payload[i : i + CHUNK_BYTES]).decode("ascii").rstrip("=")
        for i in range(0, len(payload), CHUNK_BYTES)
    ]
    checksum = hashlib.sha256(payload).hexdigest()
    send(serial, records, "import", f"BEGIN_CONFIG_JSON {len(chunks)} {checksum}", timeout)
    for index, chunk in enumerate(chunks):
        send(serial, records, "import", f"CONFIG_JSON_CHUNK {index} {chunk}", timeout)
    send(serial, records, "import", "COMMIT_CONFIG_JSON", timeout)


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


def first_response(
    records: list[CommandRecord],
    *,
    section: str,
    command: str,
    prefix: str,
) -> str | None:
    for record in records:
        if record.section != section or record.command != command:
            continue
        for response in record.responses:
            if response.startswith(prefix):
                return response
    return None


def last_response(
    records: list[CommandRecord],
    *,
    section: str,
    command: str,
    prefix: str,
) -> str | None:
    found = None
    for record in records:
        if record.section != section or record.command != command:
            continue
        for response in record.responses:
            if response.startswith(prefix):
                found = response
    return found


def parse_fields(line: str | None) -> dict[str, str]:
    if line is None or ":" not in line:
        return {}
    fields: dict[str, str] = {}
    for part in line.split(":", 1)[1].split(";"):
        if not part or "=" not in part:
            continue
        key, value = part.split("=", 1)
        fields[key] = value
    return fields


def config_jsons(records: list[CommandRecord]) -> list[dict[str, Any]]:
    parsed = []
    for line in responses_with_prefix(records, "CONFIG_JSON:"):
        try:
            parsed.append(json.loads(line.split(":", 1)[1]))
        except json.JSONDecodeError:
            pass
    return parsed


def write_text_transcript(path: pathlib.Path, records: list[CommandRecord]) -> None:
    lines: list[str] = []
    last_section = None
    for record in records:
        if record.section != last_section:
            lines.append(f"## {record.section}")
            last_section = record.section
        lines.append(f">> {record.command}")
        if record.responses:
            lines.extend(record.responses)
        else:
            lines.append("<no matching response>")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_json(path: pathlib.Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_outputs(
    out_dir: pathlib.Path,
    records: list[CommandRecord],
    imported_config: dict[str, Any],
    loaded_config: dict[str, Any] | None,
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    write_text_transcript(out_dir / "serial_transcript.txt", records)
    write_json(out_dir / "transcript.json", [record.to_json() for record in records])
    write_json(out_dir / "summary.json", summary)
    write_json(out_dir / "imported_config.json", imported_config)
    if loaded_config is not None:
        write_json(out_dir / "loaded_config.json", loaded_config)
    notes = [
        "# Config Persistence Witness Notes",
        "",
        "This run exercises the USB2BLE runtime configuration serial protocol used by",
        "the Web Serial configurator path.",
        "",
        "## Proven By This Run",
        "",
        "- Baseline config/status/schema/catalog commands returned serial responses.",
        "- Runtime config JSON was imported through BEGIN_CONFIG_JSON,",
        "  CONFIG_JSON_CHUNK, and COMMIT_CONFIG_JSON.",
        "- Imported config was exported with GET_CONFIG_JSON.",
        "- SAVE_CONFIG and LOAD_CONFIG command-path behavior was exercised.",
        "- START_CONFIGURED was exercised and followed by GET_STATUS and",
        "  GET_BRIDGE_STATUS.",
        "",
        "## Not Proven By This Run",
        "",
        "- Browser Web Serial UI behavior; this is CLI protocol evidence only.",
        "- BLE host/gamepad success unless separate host-visible evidence is captured.",
        "- Game/app compatibility.",
        "- Reboot persistence unless this run was paired with an actual board reset and",
        "  a second LOAD_CONFIG/GET_CONFIG_JSON capture.",
    ]
    (out_dir / "operator_notes.md").write_text("\n".join(notes) + "\n", encoding="utf-8")


def build_summary(
    args: argparse.Namespace,
    run_dir: pathlib.Path,
    records: list[CommandRecord],
    imported_config: dict[str, Any],
    loaded_config: dict[str, Any] | None,
) -> dict[str, Any]:
    config_statuses = responses_with_prefix(records, "CONFIG_STATUS:")
    config_json_list = config_jsons(records)
    final_status = parse_fields(config_statuses[-1] if config_statuses else None)
    errors = responses_with_prefix(records, "ERROR:")
    imported_export = config_json_list[1] if len(config_json_list) > 1 else None
    loaded_matches_imported = loaded_config == imported_config if loaded_config is not None else None
    imported_matches_export = imported_export == imported_config if imported_export is not None else None
    post_import_status = parse_fields(
        first_response(
            records,
            section="post-import",
            command="GET_CONFIG_STATUS",
            prefix="CONFIG_STATUS:",
        )
    )
    loaded_status = parse_fields(
        last_response(
            records,
            section="persistence",
            command="GET_CONFIG_STATUS",
            prefix="CONFIG_STATUS:",
        )
    )
    start_action = response_with_prefix(
        [record for record in records if record.command == "START_CONFIGURED"],
        "CONFIG_ACTION:",
    )
    return {
        "started_at_utc": args.started_at,
        "port": args.port,
        "baud": args.baud,
        "run_dir": str(run_dir),
        "persona": args.persona,
        "profile": args.profile,
        "config_file": str(args.config_json) if args.config_json else None,
        "skip_reset": args.skip_reset,
        "auto_start_bridge": args.auto_start_bridge,
        "commands": len(records),
        "errors": errors,
        "config_statuses": config_statuses,
        "final_config_status": final_status,
        "post_import_config_status": post_import_status,
        "loaded_config_status": loaded_status,
        "import_committed": any(
            "state=committed" in response
            for response in responses_with_prefix(records, "CONFIG_IMPORT:")
        ),
        "imported_status_valid": post_import_status.get("valid") == "true",
        "loaded_status_valid": loaded_status.get("valid") == "true",
        "imported_matches_export": imported_matches_export,
        "loaded_matches_imported": loaded_matches_imported,
        "start_configured_response": start_action,
        "bridge_status": response_with_prefix(records, "BRIDGE_STATUS:"),
        "config_sha256": hashlib.sha256(minified_json_bytes(imported_config)).hexdigest(),
        "web_serial_protocol_smoke": not errors,
        "reboot_persistence_proven": False,
        "browser_web_serial_ui_proven": False,
        "game_app_compatibility_proven": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", help="Serial port, for example /dev/cu.usbmodem...")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--out-dir", type=pathlib.Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--persona", choices=("generic", "xbox"), default="generic")
    parser.add_argument(
        "--profile",
        choices=(
            "minimal",
            "flight-pack",
            "generic_auto",
            "flight_pack_demo",
            "xbox_auto",
            "xbox_flight_pack_demo",
            "custom_runtime",
        ),
        default="flight-pack",
        help="Witness config profile. 'flight-pack' builds a custom_runtime preset.",
    )
    parser.add_argument("--config-json", type=pathlib.Path, help="Import this config JSON instead")
    parser.add_argument(
        "--skip-reset",
        action="store_true",
        help="Skip RESET_CONFIG before LOAD_CONFIG; this weakens persistence evidence.",
    )
    parser.add_argument(
        "--auto-start-bridge",
        action="store_true",
        help="Set bridge.auto_start_bridge=true in the imported config.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.started_at = utc_stamp()

    if args.port is None:
        print("No --port supplied; refusing to auto-select a serial device.", file=sys.stderr)
        ports = likely_serial_ports()
        if ports:
            print("Likely serial ports:", file=sys.stderr)
            for port in ports:
                print(f"  {port}", file=sys.stderr)
        else:
            print("No likely serial ports found.", file=sys.stderr)
        print(
            "Run: python3 tools/config_persistence_witness.py --port <PORT>",
            file=sys.stderr,
        )
        return 2

    if args.config_json:
        imported_config = json.loads(args.config_json.read_text(encoding="utf-8"))
    else:
        imported_config = runtime_config(args.persona, args.profile, args.auto_start_bridge)

    run_dir = args.out_dir / f"config_persistence_{args.started_at}"
    records: list[CommandRecord] = []
    payload = minified_json_bytes(imported_config)

    serial = SerialPort(args.port, args.baud)
    try:
        print("Capturing baseline...")
        for command in (
            "GET_INFO",
            "GET_STATUS",
            "GET_USB_STATUS",
            "LIST_USB_DEVICES",
            "GET_CONFIG_STATUS",
            "GET_CONFIG_SCHEMA",
            "GET_PERSONA_SCHEMA generic",
            "GET_PERSONA_SCHEMA xbox",
            "GET_INPUT_CATALOG",
            "GET_CONFIG_JSON",
        ):
            send(serial, records, "baseline", command, args.timeout)

        print("Importing runtime config...")
        import_config(serial, records, payload, args.timeout)
        send(serial, records, "post-import", "GET_CONFIG_STATUS", args.timeout)
        send(serial, records, "post-import", "GET_CONFIG_JSON", args.timeout)

        print("Exercising save/load command path...")
        send(serial, records, "persistence", "SAVE_CONFIG", args.timeout)
        if not args.skip_reset:
            send(serial, records, "persistence", "RESET_CONFIG", args.timeout)
            send(serial, records, "persistence", "GET_CONFIG_STATUS", args.timeout)
            send(serial, records, "persistence", "GET_CONFIG_JSON", args.timeout)
        send(serial, records, "persistence", "LOAD_CONFIG", args.timeout)
        send(serial, records, "persistence", "GET_CONFIG_STATUS", args.timeout)
        send(serial, records, "persistence", "GET_CONFIG_JSON", args.timeout)

        print("Starting configured persona/bridge behavior...")
        send(serial, records, "start-configured", "START_CONFIGURED", args.timeout)
        send(serial, records, "start-configured", "GET_STATUS", args.timeout)
        send(serial, records, "start-configured", "GET_BRIDGE_STATUS", args.timeout)
    finally:
        serial.close()

    json_exports = config_jsons(records)
    loaded_config = json_exports[-1] if json_exports else None
    summary = build_summary(args, run_dir, records, imported_config, loaded_config)
    write_outputs(run_dir, records, imported_config, loaded_config, summary)
    print(f"Saved witness artifacts: {run_dir}")
    if summary["errors"]:
        print("Witness completed with ERROR responses; see summary.json.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        raise SystemExit(130)
