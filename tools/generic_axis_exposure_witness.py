#!/usr/bin/env python3
"""Continuously sample browser Gamepad axes while probing Generic BLE reports."""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import http.server
import json
import pathlib
import re
import socketserver
import struct
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any

from asap_demo_rehearsal import (
    CommandRecord,
    SerialPort,
    parse_usb_devices,
    response_with_prefix,
    run_commands,
    utc_stamp,
)


DEFAULT_PORT = "/dev/cu.usbmodem5B5E0200881"
DEFAULT_OUT_DIR = "target/generic-axis-exposure-witness"
DEFAULT_BROWSER_PORT = 8766
REQUIRED_DEVICES = {
    "HooToo hub": ("2109", "2813"),
    "T.16000M stick": ("044f", "b10a"),
    "TWCS/RJ12": ("044f", "b687"),
}
AXIS_IDS = ("x", "y", "z", "rx", "ry", "rz")


@dataclass(frozen=True)
class WindowStep:
    key: str
    label: str
    instruction: str
    generic_target: str | None = None
    source_control_id: str | None = None
    expected_browser_axis_index: int | None = None


STEPS = [
    WindowStep(
        "throttle_min",
        "TWCS throttle minimum",
        "Move only the TWCS throttle to minimum and hold it.",
        "z",
        "axis_01_32",
        2,
    ),
    WindowStep(
        "throttle_max",
        "TWCS throttle maximum",
        "Move only the TWCS throttle to maximum and hold it.",
        "z",
        "axis_01_32",
        2,
    ),
    WindowStep(
        "rudder_center",
        "TFRP/RJ12 rudder centered",
        "Center the rudder pedals and hold them still.",
        "rx",
        "axis_01_36",
        3,
    ),
    WindowStep(
        "rudder_left",
        "TFRP/RJ12 rudder left",
        "Press only physical rudder LEFT / nose-left and hold it.",
        "rx",
        "axis_01_36",
        3,
    ),
    WindowStep(
        "rudder_right",
        "TFRP/RJ12 rudder right",
        "Press only physical rudder RIGHT / nose-right and hold it.",
        "rx",
        "axis_01_36",
        3,
    ),
    WindowStep(
        "left_toe_released",
        "Left toe brake released",
        "Release the left toe brake and keep the other controls still.",
        "ry",
        "axis_01_34",
        4,
    ),
    WindowStep(
        "left_toe_pressed",
        "Left toe brake pressed",
        "Press only the left toe brake fully and hold it.",
        "ry",
        "axis_01_34",
        4,
    ),
    WindowStep(
        "right_toe_released",
        "Right toe brake released",
        "Release the right toe brake and keep the other controls still.",
        "rz",
        "axis_01_33",
        5,
    ),
    WindowStep(
        "right_toe_pressed",
        "Right toe brake pressed",
        "Press only the right toe brake fully and hold it.",
        "rz",
        "axis_01_33",
        5,
    ),
]


PAGE = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>USB2BLE Continuous Axis Witness</title>
    <style>
      :root { color-scheme: light dark; font-family: system-ui, -apple-system, sans-serif; }
      body { margin: 24px; }
      header { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
      button { min-height: 40px; padding: 0 14px; font: inherit; }
      .status { margin: 14px 0; font-weight: 650; }
      .axes { display: grid; gap: 8px; max-width: 760px; }
      .axis { display: grid; grid-template-columns: 48px 1fr 80px; gap: 10px; align-items: center; }
      .track { height: 20px; border: 1px solid #8886; background: #8882; position: relative; }
      .zero { position: absolute; left: 50%; top: 0; bottom: 0; border-left: 1px solid #8888; }
      .fill { position: absolute; top: 3px; bottom: 3px; left: 50%; background: #1e6bb8; }
      pre { max-height: 320px; overflow: auto; border: 1px solid #8886; padding: 10px; }
    </style>
  </head>
  <body>
    <header>
      <div>
        <h1>USB2BLE Continuous Axis Witness</h1>
        <div id="status" class="status">Idle</div>
      </div>
      <button id="arm">Arm</button>
    </header>
    <div id="device"></div>
    <div id="axes" class="axes"></div>
    <pre id="log"></pre>
    <script>
      const state = { armed: false, activeIndex: null, samples: 0, lastPostAt: 0 };
      const els = {
        arm: document.querySelector("#arm"),
        status: document.querySelector("#status"),
        device: document.querySelector("#device"),
        axes: document.querySelector("#axes"),
        log: document.querySelector("#log"),
      };
      function round(value) { return Math.round(value * 1000) / 1000; }
      function selectGamepad() {
        const pads = Array.from(navigator.getGamepads ? navigator.getGamepads() : []);
        if (state.activeIndex !== null && pads[state.activeIndex]) return pads[state.activeIndex];
        return pads.find(Boolean) || null;
      }
      function snapshot(gamepad, type) {
        return {
          type,
          at: new Date().toISOString(),
          index: gamepad.index,
          id: gamepad.id,
          mapping: gamepad.mapping || "",
          connected: gamepad.connected,
          axes: gamepad.axes.map(round),
          buttons: gamepad.buttons.map((b) => ({ pressed: b.pressed, value: round(b.value) })),
          sample: state.samples,
        };
      }
      async function post(entry) {
        els.log.textContent += JSON.stringify(entry) + "\\n";
        els.log.scrollTop = els.log.scrollHeight;
        try {
          await fetch("/capture", {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify(entry),
          });
        } catch {}
      }
      function render(gamepad) {
        els.status.textContent = gamepad ? `Armed, samples ${state.samples}` : "Armed, no gamepad";
        els.device.textContent = gamepad ? gamepad.id : "No gamepad selected";
        els.axes.innerHTML = "";
        if (!gamepad) return;
        gamepad.axes.forEach((axis, index) => {
          const row = document.createElement("div");
          row.className = "axis";
          const name = document.createElement("div");
          name.textContent = `A${index}`;
          const track = document.createElement("div");
          track.className = "track";
          const zero = document.createElement("div");
          zero.className = "zero";
          const fill = document.createElement("div");
          fill.className = "fill";
          const clamped = Math.max(-1, Math.min(1, axis));
          if (clamped >= 0) {
            fill.style.left = "50%";
            fill.style.width = `${clamped * 50}%`;
          } else {
            fill.style.left = `${50 + clamped * 50}%`;
            fill.style.width = `${Math.abs(clamped) * 50}%`;
          }
          track.append(zero, fill);
          const value = document.createElement("div");
          value.textContent = round(axis).toFixed(3);
          row.append(name, track, value);
          els.axes.append(row);
        });
      }
      function tick() {
        if (!state.armed) return;
        const gamepad = selectGamepad();
        if (gamepad) state.activeIndex = gamepad.index;
        state.samples += 1;
        render(gamepad);
        const now = performance.now();
        if (gamepad && now - state.lastPostAt >= 100) {
          state.lastPostAt = now;
          post(snapshot(gamepad, "sample"));
        }
        requestAnimationFrame(tick);
      }
      function arm() {
        if (state.armed) return;
        state.armed = true;
        els.arm.disabled = true;
        const gamepad = selectGamepad();
        if (gamepad) {
          state.activeIndex = gamepad.index;
          post(snapshot(gamepad, "arm"));
        }
        requestAnimationFrame(tick);
      }
      els.arm.addEventListener("click", arm);
      window.addEventListener("gamepadconnected", (event) => {
        state.activeIndex = event.gamepad.index;
        post(snapshot(event.gamepad, "connected"));
        arm();
      });
      window.addEventListener("gamepaddisconnected", (event) => {
        post({ type: "disconnected", at: new Date().toISOString(), id: event.gamepad.id });
      });
    </script>
  </body>
</html>
"""


class CaptureHandler(http.server.BaseHTTPRequestHandler):
    capture_file: pathlib.Path

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802 - stdlib callback name
        if self.path not in ("/", "/index.html"):
            self.send_error(404)
            return
        body = PAGE.encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "text/html; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802 - stdlib callback name
        if self.path != "/capture":
            self.send_error(404)
            return
        length = int(self.headers.get("content-length", "0"))
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_error(400, "invalid json")
            return
        with self.capture_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n")
        self.send_response(204)
        self.end_headers()


class ReusableTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def normalize_hex(value: str) -> str:
    return value.lower().removeprefix("0x").zfill(4)


def likely_ports() -> list[str]:
    ports = sorted(set(glob.glob("/dev/cu.*") + glob.glob("/dev/tty.*")))
    likely = [
        port
        for port in ports
        if re.search(r"(usb|wch|modem|serial)", pathlib.Path(port).name, re.IGNORECASE)
    ]

    def priority(port: str) -> tuple[int, str]:
        if port == DEFAULT_PORT:
            return (0, port)
        if port.startswith("/dev/cu.usbmodem"):
            return (1, port)
        if port.startswith("/dev/cu."):
            return (2, port)
        return (3, port)

    return sorted(likely, key=priority)


def has_valid_control_plane(port: str, timeout: float) -> bool:
    try:
        serial = SerialPort(port)
    except OSError:
        return False
    try:
        records = run_commands(serial, ["GET_INFO", "GET_STATUS"], timeout)
    except OSError:
        return False
    finally:
        serial.close()
    return (
        response_with_prefix(records, "INFO:") is not None
        and response_with_prefix(records, "STATUS:") is not None
    )


def select_port(requested: str, timeout: float) -> str:
    if requested != "auto":
        return requested
    for port in likely_ports():
        print(f"Probing {port}...")
        if has_valid_control_plane(port, timeout):
            print(f"Selected {port}")
            return port
    raise RuntimeError("no likely serial port returned USB2BLE INFO/STATUS")


def notify(message: str, enabled: bool) -> None:
    if not enabled or sys.platform != "darwin":
        return
    safe = message.replace("\\", "\\\\").replace('"', '\\"')
    subprocess.run(
        ["osascript", "-e", f'display notification "{safe}" with title "USB2BLE axis witness"'],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(["say", message], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def prompt_operator(message: str, alerts: bool, assume_ready: bool) -> None:
    print()
    print("=" * 78)
    print(message)
    print("Keep unrelated controls still while the window is sampled.")
    notify(message, alerts)
    if assume_ready:
        time.sleep(0.5)
        return
    input("Press Enter when ready...")


def load_samples(path: pathlib.Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    samples: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            samples.append(value)
    return samples


def wait_for_samples(path: pathlib.Path, minimum: int, timeout: float) -> list[dict[str, Any]]:
    deadline = time.monotonic() + timeout
    samples = load_samples(path)
    while len(samples) < minimum and time.monotonic() < deadline:
        time.sleep(0.2)
        samples = load_samples(path)
    return samples


def observed_devices(records: list[CommandRecord]) -> dict[str, bool]:
    devices = parse_usb_devices(response_with_prefix(records, "USB_DEVICES:"))
    result: dict[str, bool] = {}
    for name, (vid, pid) in REQUIRED_DEVICES.items():
        result[name] = any(
            normalize_hex(device.get("vid", "")) == normalize_hex(vid)
            and normalize_hex(device.get("pid", "")) == normalize_hex(pid)
            for device in devices
        )
    return result


def parse_bridge_published(line: str | None) -> int | None:
    if not line:
        return None
    match = re.search(r"(?:^|;)published=(\d+)(?:;|$)", line)
    return int(match.group(1)) if match else None


def mapping_values(records: list[CommandRecord]) -> list[dict[str, str]]:
    values: list[dict[str, str]] = []
    for record in records:
        for response in record.responses:
            if response.startswith("MAPPED_CONTROL:"):
                body = response.split(":", 1)[1]
                item: dict[str, str] = {}
                for field in body.split(";"):
                    if "=" in field:
                        key, value = field.split("=", 1)
                        item[key] = value
                values.append(item)
                continue
            if response.startswith("GENERIC_GAMEPAD_MAPPING:") and "mappings=" in response:
                mappings = response.split("mappings=", 1)[1]
                for entry in mappings.split("|"):
                    item: dict[str, str] = {}
                    for field in entry.split(","):
                        if "=" in field:
                            key, value = field.split("=", 1)
                            item[key] = value
                    source = item.get("src")
                    if source:
                        parts = source.split(":")
                        if len(parts) >= 5:
                            item["source"] = ":".join(parts[:4])
                            item["control"] = ":".join(parts[4:])
                    if item:
                        values.append(item)
    return values


def decoded_report(response: str | None) -> dict[str, Any] | None:
    if not response:
        return None
    match = re.search(r"bytes=([0-9a-fA-F]+)", response)
    if not match:
        return None
    hex_bytes = match.group(1)
    data = bytes.fromhex(hex_bytes)
    axes: dict[str, int] = {}
    if len(data) >= 15:
        axes = dict(zip(AXIS_IDS, struct.unpack_from("<hhhhhh", data, 3)))
    return {"bytes": hex_bytes, "length": len(data), "axes": axes}


def axis_stats(samples: list[dict[str, Any]]) -> tuple[list[int], list[dict[str, Any]], int | None]:
    axis_rows = [sample.get("axes") for sample in samples if isinstance(sample.get("axes"), list)]
    if not axis_rows:
        return [], [], None
    axis_len = max(len(row) for row in axis_rows)
    stats = []
    changed = []
    for index in range(axis_len):
        values = [float(row[index]) for row in axis_rows if index < len(row)]
        if not values:
            continue
        delta = max(values) - min(values)
        if abs(delta) > 0.001:
            changed.append(index)
        stats.append(
            {
                "axis_index": index,
                "samples": len(values),
                "min": min(values),
                "max": max(values),
                "delta": delta,
                "first": values[0],
                "last": values[-1],
            }
        )
    return changed, stats, axis_len


def start_server(capture_file: pathlib.Path, port: int) -> tuple[ReusableTCPServer, threading.Thread]:
    CaptureHandler.capture_file = capture_file
    server = ReusableTCPServer(("127.0.0.1", port), CaptureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def open_browser(port: int) -> None:
    url = f"http://127.0.0.1:{port}/"
    if sys.platform == "darwin":
        subprocess.run(["open", url], check=False)
    else:
        subprocess.run(["xdg-open", url], check=False)


def write_transcript(path: pathlib.Path, records: list[CommandRecord]) -> None:
    lines: list[str] = []
    for record in records:
        lines.append(f">> {record.command}")
        lines.extend(record.responses or ["<no matching response>"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def capture_window(
    serial: SerialPort,
    step: WindowStep,
    capture_file: pathlib.Path,
    timeout: float,
    window_seconds: float,
    alerts: bool,
    assume_ready: bool,
) -> tuple[dict[str, Any], list[CommandRecord]]:
    before_samples = load_samples(capture_file)
    before_count = len(before_samples)
    prompt_operator(step.instruction, alerts, assume_ready)
    before_records = run_commands(serial, ["GET_BRIDGE_STATUS"], timeout)
    during_records = run_commands(
        serial,
        ["GET_GENERIC_GAMEPAD_MAPPING", "GET_GENERIC_GAMEPAD_REPORT", "GET_BRIDGE_STATUS"],
        timeout,
    )
    time.sleep(window_seconds)
    after_records = run_commands(serial, ["GET_BRIDGE_STATUS"], timeout)
    all_records = before_records + during_records + after_records
    samples = load_samples(capture_file)
    step_samples = samples[before_count:]
    changed, stats, axes_length = axis_stats(step_samples)
    report = decoded_report(response_with_prefix(during_records, "ENCODED_REPORT:"))
    before_published = parse_bridge_published(response_with_prefix(before_records, "BRIDGE_STATUS:"))
    after_published = parse_bridge_published(response_with_prefix(after_records, "BRIDGE_STATUS:"))
    mappings = mapping_values(during_records)
    target_mapping = [
        mapping
        for mapping in mappings
        if step.source_control_id is None
        or mapping.get("control") == step.source_control_id
        or mapping.get("target") == step.generic_target
    ]
    return (
        {
            "key": step.key,
            "label": step.label,
            "generic_target": step.generic_target,
            "source_control_id": step.source_control_id,
            "expected_browser_axis_index": step.expected_browser_axis_index,
            "sample_count": len(step_samples),
            "browser_axes_length": axes_length,
            "browser_axes_changed": bool(changed),
            "changed_browser_axis_indices": changed,
            "expected_browser_axis_changed": (
                step.expected_browser_axis_index in changed
                if step.expected_browser_axis_index is not None
                else None
            ),
            "browser_axis_stats": stats,
            "serial_mapping_changed": bool(target_mapping),
            "target_mappings": target_mapping,
            "encoded_report": report,
            "encoded_report_changed": report is not None,
            "bridge_before_published": before_published,
            "bridge_after_published": after_published,
            "bridge_published_increased": (
                before_published is not None
                and after_published is not None
                and after_published > before_published
            ),
        },
        all_records,
    )


def infer_axis_map(windows: list[dict[str, Any]]) -> dict[str, list[int]]:
    result: dict[str, list[int]] = {}
    for window in windows:
        target = window.get("generic_target")
        if not target:
            continue
        expected = window.get("expected_browser_axis_index")
        if not isinstance(expected, int):
            continue
        changed = window.get("changed_browser_axis_indices")
        if not isinstance(changed, list) or expected not in changed:
            continue
        existing = set(result.get(target, []))
        existing.add(expected)
        result[target] = sorted(existing)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="auto", help="Serial port or 'auto'.")
    parser.add_argument("--timeout", type=float, default=4.0)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--browser-port", type=int, default=DEFAULT_BROWSER_PORT)
    parser.add_argument("--window-seconds", type=float, default=3.0)
    parser.add_argument("--assume-ready", action="store_true")
    parser.add_argument("--quiet-alerts", action="store_true")
    parser.add_argument("--skip-browser-open", action="store_true")
    parser.add_argument("--steps", help="Comma-separated step keys. Default: all focused windows.")
    args = parser.parse_args()

    selected_steps = STEPS
    if args.steps:
        wanted = {key.strip() for key in args.steps.split(",") if key.strip()}
        selected_steps = [step for step in STEPS if step.key in wanted]
        missing = wanted - {step.key for step in selected_steps}
        if missing:
            print(f"Unknown step(s): {', '.join(sorted(missing))}", file=sys.stderr)
            return 2

    run_dir = pathlib.Path(args.out_dir) / f"generic_axis_exposure_{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    capture_file = run_dir / "browser_samples.jsonl"
    capture_file.touch()

    errors: list[str] = []
    port = select_port(args.port, args.timeout)
    server, _thread = start_server(capture_file, args.browser_port)
    if not args.skip_browser_open:
        open_browser(args.browser_port)
    print(f"Browser witness URL: http://127.0.0.1:{args.browser_port}/")
    print(f"Saving artifacts: {run_dir}")

    all_records: list[CommandRecord] = []
    windows: list[dict[str, Any]] = []
    serial = SerialPort(port)
    try:
        preflight = run_commands(
            serial,
            [
                "GET_INFO",
                "GET_STATUS",
                "GET_USB_STATUS",
                "LIST_USB_DEVICES",
                "GET_CONFIG_STATUS",
                "GET_CONFIG_JSON",
            ],
            args.timeout,
        )
        all_records.extend(preflight)
        start_records = run_commands(serial, ["START_CONFIGURED", "GET_STATUS", "GET_BRIDGE_STATUS"], args.timeout)
        all_records.extend(start_records)
        devices = observed_devices(all_records)
        missing_devices = [name for name, present in devices.items() if not present]
        if missing_devices:
            errors.append(f"missing expected USB device(s): {', '.join(missing_devices)}")

        samples = wait_for_samples(capture_file, 3, 8.0)
        if len(samples) < 3:
            prompt_operator(
                "In the opened browser witness page, click Arm. If Bluetooth is disconnected, connect USB2BLE Gamepad first.",
                not args.quiet_alerts,
                args.assume_ready,
            )
            samples = wait_for_samples(capture_file, 3, 15.0)
        if len(samples) < 3:
            errors.append("browser did not produce continuous Gamepad samples")
        else:
            latest = samples[-1]
            print(f"Browser samples active: {len(samples)}; latest gamepad={latest.get('id')}")

        if len(samples) >= 3:
            for step in selected_steps:
                window, records = capture_window(
                    serial,
                    step,
                    capture_file,
                    args.timeout,
                    args.window_seconds,
                    not args.quiet_alerts,
                    args.assume_ready,
                )
                windows.append(window)
                all_records.extend(records)
                print(
                    json.dumps(
                        {
                            "step": step.key,
                            "samples": window["sample_count"],
                            "changed_browser_axis_indices": window["changed_browser_axis_indices"],
                            "decoded_axes": (window.get("encoded_report") or {}).get("axes"),
                        },
                        sort_keys=True,
                    )
                )
                if window["sample_count"] < 3:
                    errors.append(f"{step.key}: fewer than three browser samples")
                if not window["encoded_report_changed"]:
                    errors.append(f"{step.key}: no encoded Generic report captured")

        final_records = run_commands(serial, ["GET_BRIDGE_STATUS", "GET_STATUS"], args.timeout)
        all_records.extend(final_records)
    finally:
        serial.close()
        server.shutdown()
        server.server_close()

    all_samples = load_samples(capture_file)
    changed_over_run, stats_over_run, axes_length = axis_stats(all_samples)
    summary = {
        "run_dir": str(run_dir),
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "port": port,
        "browser_url": f"http://127.0.0.1:{args.browser_port}/",
        "browser_sample_count": len(all_samples),
        "browser_axes_length": axes_length,
        "changed_browser_axis_indices_over_run": changed_over_run,
        "browser_axis_stats_over_run": stats_over_run,
        "observed_devices": observed_devices(all_records),
        "windows": windows,
        "likely_browser_axis_map": infer_axis_map(windows),
        "errors": errors,
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_transcript(run_dir / "serial_transcript.txt", all_records)
    (run_dir / "operator_notes.md").write_text(
        "# Generic Axis Exposure Witness Notes\n\n"
        "- This is a browser Gamepad API / BLE HID exposure diagnostic, not game/app compatibility evidence.\n"
        "- The page posts continuous Gamepad samples while armed, so unchanged axes are represented explicitly.\n"
        "- Success requires comparing serial decoded reports with browser axis deltas in summary.json.\n",
        encoding="utf-8",
    )
    print(f"Saved witness artifacts: {run_dir}")
    if errors:
        print("Witness completed with errors; see summary.json.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        raise SystemExit(130)
