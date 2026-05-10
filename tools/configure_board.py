#!/usr/bin/env python3
"""Exercise the USB2BLE webapp-ready configuration protocol over serial."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import pathlib
import sys
from typing import Any

from asap_demo_rehearsal import CommandRecord, SerialPort, print_record, utc_stamp


DEFAULT_PORT = "/dev/cu.usbmodem5B5E0200881"
DEFAULT_OUT_DIR = pathlib.Path("target/configure-board")
CHUNK_BYTES = 72


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


def preset_config(name: str) -> dict[str, Any]:
    if name == "flight-pack-generic":
        return {
            "schema_version": 1,
            "metadata_version": 1,
            "display_name": "Flight Pack Generic",
            "selected_persona": "generic_gamepad",
            "selected_profile": "custom_runtime",
            "bridge": {
                "auto_start_persona": True,
                "auto_start_bridge": False,
                "rate_hz": 50,
            },
            "mappings": [
                thrustmaster_rule(0xB10A, "axis_01_30", "x"),
                thrustmaster_rule(0xB10A, "axis_01_31", "y"),
                thrustmaster_rule(0xB687, "axis_01_32", "z"),
                thrustmaster_rule(0xB687, "axis_01_36", "rx"),
            ],
        }
    if name == "flight-pack-xbox":
        axis_to_trigger = {
            "type": "axis_to_trigger",
            "source_min": -32768,
            "source_max": 32767,
            "invert": False,
        }
        return {
            "schema_version": 1,
            "metadata_version": 1,
            "display_name": "Flight Pack Xbox",
            "selected_persona": "xbox_wireless_controller",
            "selected_profile": "custom_runtime",
            "bridge": {
                "auto_start_persona": True,
                "auto_start_bridge": False,
                "rate_hz": 50,
            },
            "mappings": [
                thrustmaster_rule(0xB10A, "axis_01_30", "left_x"),
                thrustmaster_rule(0xB10A, "axis_01_31", "left_y"),
                thrustmaster_rule(0xB687, "axis_01_36", "right_x"),
                thrustmaster_rule(
                    0xB687,
                    "axis_01_32",
                    "right_trigger",
                    transform=axis_to_trigger,
                ),
                thrustmaster_rule(0xB10A, "hat_01_39", "hat"),
                thrustmaster_rule(0xB10A, "button_1", "a"),
                thrustmaster_rule(0xB10A, "button_2", "b"),
                thrustmaster_rule(0xB10A, "button_3", "x"),
                thrustmaster_rule(0xB10A, "button_4", "y"),
            ],
        }
    raise ValueError(f"unknown preset: {name}")


def send(serial: SerialPort, records: list[CommandRecord], command: str, timeout: float) -> CommandRecord:
    record = CommandRecord(command, serial.command_response(command, timeout))
    print_record(record)
    records.append(record)
    return record


def import_json(
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
    send(serial, records, f"BEGIN_CONFIG_JSON {len(chunks)} {checksum}", timeout)
    for index, chunk in enumerate(chunks):
        send(serial, records, f"CONFIG_JSON_CHUNK {index} {chunk}", timeout)
    send(serial, records, "COMMIT_CONFIG_JSON", timeout)


def response_with_prefix(records: list[CommandRecord], prefix: str) -> str | None:
    for record in records:
        for response in record.responses:
            if response.startswith(prefix):
                return response
    return None


def write_outputs(out_dir: pathlib.Path, records: list[CommandRecord], summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "transcript.json").write_text(
        json.dumps([record.to_json() for record in records], indent=2) + "\n",
        encoding="utf-8",
    )
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    exported = response_with_prefix(records, "CONFIG_JSON:")
    if exported is not None:
        (out_dir / "config_export.json").write_text(exported.split(":", 1)[1] + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--out-dir", type=pathlib.Path, default=DEFAULT_OUT_DIR)
    subparsers = parser.add_subparsers(dest="mode", required=True)

    for mode in ("show", "schema", "catalog", "export", "save", "load", "reset", "start-configured"):
        subparsers.add_parser(mode)
    import_parser = subparsers.add_parser("import")
    import_parser.add_argument("file", type=pathlib.Path)
    preset_parser = subparsers.add_parser("preset")
    preset_parser.add_argument("name", choices=("flight-pack-generic", "flight-pack-xbox"))

    args = parser.parse_args()
    run_dir = args.out_dir / f"configure_board_{utc_stamp()}"
    records: list[CommandRecord] = []

    serial = SerialPort(args.port)
    try:
        if args.mode == "show":
            send(serial, records, "GET_CONFIG_STATUS", args.timeout)
            send(serial, records, "GET_CONFIG_JSON", args.timeout)
        elif args.mode == "schema":
            send(serial, records, "GET_CONFIG_SCHEMA", args.timeout)
            send(serial, records, "GET_PERSONA_SCHEMA generic", args.timeout)
            send(serial, records, "GET_PERSONA_SCHEMA xbox", args.timeout)
        elif args.mode == "catalog":
            send(serial, records, "GET_INPUT_CATALOG", args.timeout)
        elif args.mode == "export":
            send(serial, records, "GET_CONFIG_JSON", args.timeout)
        elif args.mode == "import":
            import_json(serial, records, args.file.read_bytes(), args.timeout)
        elif args.mode == "preset":
            payload = json.dumps(preset_config(args.name), separators=(",", ":")).encode("utf-8")
            import_json(serial, records, payload, args.timeout)
        elif args.mode == "save":
            send(serial, records, "SAVE_CONFIG", args.timeout)
        elif args.mode == "load":
            send(serial, records, "LOAD_CONFIG", args.timeout)
        elif args.mode == "reset":
            send(serial, records, "RESET_CONFIG", args.timeout)
        elif args.mode == "start-configured":
            send(serial, records, "START_CONFIGURED", args.timeout)
        else:
            raise AssertionError(args.mode)
    finally:
        serial.close()

    summary = {
        "mode": args.mode,
        "port": args.port,
        "run_dir": str(run_dir),
        "records": len(records),
        "config_status": response_with_prefix(records, "CONFIG_STATUS:"),
        "config_action": response_with_prefix(records, "CONFIG_ACTION:"),
        "config_import": [
            response
            for record in records
            for response in record.responses
            if response.startswith("CONFIG_IMPORT:")
        ],
        "error": response_with_prefix(records, "ERROR:"),
    }
    write_outputs(run_dir, records, summary)
    print(f"Saved transcript: {run_dir}")
    return 1 if summary["error"] else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        raise SystemExit(130)
