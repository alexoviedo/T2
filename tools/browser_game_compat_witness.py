#!/usr/bin/env python3
"""Run a self-hosted browser mini-game compatibility smoke witness."""

from __future__ import annotations

import argparse
import datetime as dt
import http.server
import json
import pathlib
import socketserver
import subprocess
import sys
import threading
import time
from typing import Any

from asap_demo_rehearsal import (
    CommandRecord,
    SerialPort,
    parse_int_field,
    parse_semicolon_fields,
    response_with_prefix,
    run_commands,
    utc_stamp,
)


ROOT = pathlib.Path(__file__).resolve().parent
GAME_DIR = ROOT / "browser_game_compat"
DEFAULT_OUT_DIR = "target/game-compatibility"
DEFAULT_PORT = 8770


class GameHandler(http.server.SimpleHTTPRequestHandler):
    capture_file: pathlib.Path

    def __init__(self, *args: Any, directory: str | None = None, **kwargs: Any) -> None:
        super().__init__(*args, directory=directory or str(GAME_DIR), **kwargs)

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stdout.write("[browser-game] " + (fmt % args) + "\n")
        sys.stdout.flush()

    def do_GET(self) -> None:  # noqa: N802 - stdlib callback name
        if self.path == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802 - stdlib callback name
        if self.path != "/capture":
            self.send_error(404)
            return
        length = int(self.headers.get("content-length", "0"))
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except json.JSONDecodeError:
            self.send_error(400, "invalid json")
            return
        with self.capture_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
        self.send_response(204)
        self.end_headers()


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def write_transcript(path: pathlib.Path, records: list[CommandRecord]) -> None:
    lines: list[str] = []
    for record in records:
        lines.append(f">> {record.command}")
        lines.extend(record.responses or ["<no matching response>"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_jsonl(path: pathlib.Path, values: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for value in values:
            handle.write(json.dumps(value, sort_keys=True) + "\n")


def load_jsonl(path: pathlib.Path) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            values.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return values


def chrome_version() -> str | None:
    chrome = pathlib.Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    if not chrome.exists():
        return None
    result = subprocess.run(
        [str(chrome), "--version"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def system_output(command: list[str]) -> str:
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
    return result.stdout.strip()


def start_server(capture_file: pathlib.Path, port: int) -> ReusableTCPServer:
    GameHandler.capture_file = capture_file
    server = ReusableTCPServer(("127.0.0.1", port), GameHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def launch_chrome(url: str, profile_dir: pathlib.Path, use_default_profile: bool) -> subprocess.Popen[str] | None:
    if use_default_profile:
        subprocess.run(["open", url], check=False)
        return None
    chrome = pathlib.Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    if not chrome.exists():
        subprocess.run(["open", url], check=False)
        return None
    profile_dir.mkdir(parents=True, exist_ok=True)
    return subprocess.Popen(
        [
            str(chrome),
            f"--user-data-dir={profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--new-window",
            url,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )


def bridge_status(record: CommandRecord) -> dict[str, str]:
    return parse_semicolon_fields(response_with_prefix([record], "BRIDGE_STATUS:"))


def poll_serial(serial: SerialPort, duration: float, interval: float, timeout: float) -> tuple[list[dict[str, Any]], list[CommandRecord]]:
    start = time.monotonic()
    next_sample = start
    samples: list[dict[str, Any]] = []
    records: list[CommandRecord] = []
    index = 0
    while time.monotonic() - start < duration:
        now = time.monotonic()
        if now < next_sample:
            time.sleep(min(0.1, next_sample - now))
            continue
        status_record = CommandRecord("GET_STATUS", serial.command_response("GET_STATUS", timeout))
        bridge_record = CommandRecord("GET_BRIDGE_STATUS", serial.command_response("GET_BRIDGE_STATUS", timeout))
        records.extend([status_record, bridge_record])
        samples.append(
            {
                "sample": index,
                "elapsed_seconds": round(now - start, 3),
                "status": parse_semicolon_fields(response_with_prefix([status_record], "STATUS:")),
                "bridge_status": bridge_status(bridge_record),
            }
        )
        index += 1
        next_sample += interval
    return samples, records


def summarize_game(events: list[dict[str, Any]]) -> dict[str, Any]:
    connected = [event for event in events if event.get("connected") is True]
    states = [event for event in events if event.get("kind") == "game_state"]
    mission_events = [event for event in events if event.get("kind") == "mission_complete"]
    axis_samples = [event.get("axes") for event in events if isinstance(event.get("axes"), list)]
    max_axis_abs = 0.0
    for axes in axis_samples:
        for value in axes[:6]:
            if isinstance(value, (int, float)):
                max_axis_abs = max(max_axis_abs, abs(float(value)))
    first_state = states[0] if states else None
    last_state = states[-1] if states else None
    ship_delta_x = None
    ship_delta_y = None
    if first_state and last_state:
        first_ship = first_state.get("ship") or {}
        last_ship = last_state.get("ship") or {}
        if isinstance(first_ship, dict) and isinstance(last_ship, dict):
            ship_delta_x = (last_ship.get("x") or 0) - (first_ship.get("x") or 0)
            ship_delta_y = (last_ship.get("y") or 0) - (first_ship.get("y") or 0)
    return {
        "event_count": len(events),
        "connected_event_count": len(connected),
        "game_state_count": len(states),
        "controller_ids": sorted({event.get("gamepad_id") for event in connected if event.get("gamepad_id")}),
        "mission_completed": bool(mission_events or any(event.get("mission_completed") for event in events)),
        "max_axis_abs": max_axis_abs,
        "ship_delta_x": ship_delta_x,
        "ship_delta_y": ship_delta_y,
        "score_max": max((int(event.get("score") or 0) for event in events), default=0),
    }


def field_delta(samples: list[dict[str, Any]], field: str) -> tuple[int | None, int | None, int | None]:
    values = [
        value
        for sample in samples
        for value in [parse_int_field(sample.get("bridge_status") or {}, field)]
        if value is not None
    ]
    if not values:
        return None, None, None
    return values[0], values[-1], values[-1] - values[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="/dev/cu.usbmodem5B5E0200881")
    parser.add_argument("--http-port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--duration-seconds", type=float, default=65.0)
    parser.add_argument("--sample-interval-seconds", type=float, default=5.0)
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--skip-browser-open", action="store_true")
    parser.add_argument(
        "--temporary-chrome-profile",
        action="store_true",
        help="Launch Chrome with an isolated profile. Default uses the normal Chrome profile, matching prior browser witnesses.",
    )
    args = parser.parse_args()

    stamp = utc_stamp()
    run_dir = pathlib.Path(args.out_dir) / f"self_hosted_sky_run_generic_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    capture_file = run_dir / "browser_game_events.jsonl"
    capture_file.touch()

    server = start_server(capture_file, args.http_port)
    chrome: subprocess.Popen[str] | None = None
    url = f"http://127.0.0.1:{args.http_port}/"
    records: list[CommandRecord] = []
    samples: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        serial = SerialPort(args.port)
        try:
            preflight = run_commands(
                serial,
                [
                    "GET_INFO",
                    "GET_STATUS",
                    "GET_USB_STATUS",
                    "LIST_USB_DEVICES",
                    "GET_CONFIG_STATUS",
                    "GET_BRIDGE_STATUS",
                    "START_CONFIGURED",
                    "GET_STATUS",
                    "GET_BRIDGE_STATUS",
                ],
                args.timeout,
            )
            records.extend(preflight)
            if not args.skip_browser_open:
                chrome = launch_chrome(
                    url,
                    run_dir / "chrome-profile",
                    use_default_profile=not args.temporary_chrome_profile,
                )
            samples, poll_records = poll_serial(
                serial,
                args.duration_seconds,
                args.sample_interval_seconds,
                args.timeout,
            )
            records.extend(poll_records)
            final_records = run_commands(serial, ["GET_BRIDGE_STATUS", "GET_STATUS"], args.timeout)
            records.extend(final_records)
        finally:
            serial.close()
    finally:
        if chrome is not None:
            chrome.terminate()
            try:
                chrome.wait(timeout=5)
            except subprocess.TimeoutExpired:
                chrome.kill()
        server.shutdown()
        server.server_close()

    events = load_jsonl(capture_file)
    game_summary = summarize_game(events)
    published_start, published_end, published_delta = field_delta(samples, "published")
    not_connected_start, not_connected_end, not_connected_delta = field_delta(samples, "skipped_not_connected")
    not_ready_start, not_ready_end, not_ready_delta = field_delta(samples, "skipped_not_ready")
    last_errors = sorted(
        {
            (sample.get("bridge_status") or {}).get("last_error", "none")
            for sample in samples
        }
    )
    usb_devices = response_with_prefix(records, "USB_DEVICES:") or ""
    config_status = parse_semicolon_fields(response_with_prefix(records, "CONFIG_STATUS:"))
    bridge_start = bridge_status(next((record for record in records if record.command == "GET_BRIDGE_STATUS"), CommandRecord("", [])))
    bridge_end_records = [record for record in records if record.command == "GET_BRIDGE_STATUS"]
    bridge_end = bridge_status(bridge_end_records[-1]) if bridge_end_records else {}

    if config_status.get("persona") != "generic_gamepad":
        errors.append("loaded config was not generic_gamepad")
    if config_status.get("profile") != "custom_runtime":
        errors.append("loaded config was not custom_runtime")
    if config_status.get("mappings") != "6":
        errors.append("loaded config did not report six mappings")
    if "vid=2109,pid=2813" not in usb_devices:
        errors.append("HooToo hub not observed")
    if "vid=044f,pid=b10a" not in usb_devices:
        errors.append("T.16000M stick not observed")
    if "vid=044f,pid=b687" not in usb_devices:
        errors.append("TWCS/RJ12 not observed")
    if published_delta is None or published_delta <= 0:
        errors.append("bridge published counter did not increase")
    if not_connected_delta not in (0, None):
        errors.append("skipped_not_connected increased")
    if not_ready_delta not in (0, None):
        errors.append("skipped_not_ready increased")
    if any(value != "none" for value in last_errors):
        errors.append("bridge last_error was not none")
    if not game_summary["connected_event_count"]:
        errors.append("browser game did not report a connected controller")
    if game_summary["max_axis_abs"] <= 0.2:
        errors.append("browser game did not observe a meaningful refined Generic axis")
    if not game_summary["mission_completed"]:
        errors.append("browser game mission did not complete")

    passed = not errors
    summary = {
        "run_dir": str(run_dir),
        "captured_at": stamp,
        "app_game_name": "USB2BLE Sky Run",
        "app_game_kind": "self-hosted browser game/app compatibility smoke",
        "app_game_url": url,
        "selected_port": args.port,
        "host_os": system_output(["sw_vers"]),
        "browser": chrome_version(),
        "commit_sha": system_output(["git", "rev-parse", "HEAD"]),
        "git_dirty": bool(system_output(["git", "status", "--short"])),
        "bluetooth_identity": system_output(
            ["bash", "-lc", "system_profiler SPBluetoothDataType 2>/dev/null | grep -A8 -B2 -E 'USB2BLE|Gamepad|Controller|Xbox' || true"]
        ),
        "firmware_info": parse_semicolon_fields(response_with_prefix(records, "INFO:")),
        "config_status": config_status,
        "usb_devices": usb_devices,
        "bridge_start": bridge_start,
        "bridge_end": bridge_end,
        "bridge_sample_count": len(samples),
        "published_start": published_start,
        "published_end": published_end,
        "published_delta": published_delta,
        "skipped_not_connected_start": not_connected_start,
        "skipped_not_connected_end": not_connected_end,
        "skipped_not_connected_delta": not_connected_delta,
        "skipped_not_ready_start": not_ready_start,
        "skipped_not_ready_end": not_ready_end,
        "skipped_not_ready_delta": not_ready_delta,
        "last_error_values": last_errors,
        "game_summary": game_summary,
        "controls_recognized": {
            "refined_generic_axes": "Browser game consumed Gamepad axes including A2/A3/A4/A5 when present.",
            "buttons": "not required for this self-hosted smoke",
            "orientation": "visible game-state movement observed; exact product-quality orientation remains future calibration work",
        },
        "errors": errors,
        "self_hosted_browser_game_smoke_passed": passed,
        "claim_boundary": [
            "self-hosted browser game/app compatibility smoke only",
            "not broad game compatibility",
            "not native app/game compatibility",
            "not Xbox compatibility",
            "not BLE bond persistence",
            "not final calibration quality",
        ],
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_transcript(run_dir / "serial_transcript.txt", records)
    write_jsonl(run_dir / "bridge_status_samples.jsonl", samples)
    (run_dir / "operator_notes.md").write_text(
        "# USB2BLE Sky Run Operator Notes\n\n"
        "- Self-hosted browser game/app compatibility smoke.\n"
        "- No human actions were required in this run.\n"
        "- This is not broad game compatibility or native app/game compatibility.\n"
        f"- Result: {'pass' if passed else 'fail'}.\n",
        encoding="utf-8",
    )
    print(json.dumps({"run_dir": str(run_dir), "passed": passed, "errors": errors}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        raise SystemExit(130)
