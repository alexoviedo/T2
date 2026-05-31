#!/usr/bin/env python3
"""Run a raw Chrome Gamepad API probe without witness persona filtering."""

from __future__ import annotations

import argparse
import datetime as dt
import http.server
import json
import pathlib
import socketserver
import subprocess
import tempfile
import threading
import time
import urllib.parse
from typing import Any


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8850


PROBE_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>USB2BLE Chrome Gamepad Probe</title>
    <style>
      body {
        margin: 0;
        font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        background: #f7f8f5;
        color: #17201d;
      }
      main {
        width: min(960px, calc(100vw - 32px));
        margin: 24px auto;
        display: grid;
        gap: 16px;
      }
      button {
        min-height: 40px;
        border: 1px solid #cfd8d0;
        border-radius: 6px;
        padding: 0 14px;
        background: #17201d;
        color: white;
        font: inherit;
      }
      button:disabled {
        opacity: 0.55;
      }
      pre {
        min-height: 360px;
        overflow: auto;
        border: 1px solid #cfd8d0;
        border-radius: 8px;
        background: white;
        padding: 12px;
        white-space: pre-wrap;
        overflow-wrap: anywhere;
      }
    </style>
  </head>
  <body>
    <main>
      <h1>USB2BLE Chrome Gamepad Probe</h1>
      <p id="state">Idle</p>
      <button id="arm" type="button">Arm Probe</button>
      <pre id="log"></pre>
    </main>
    <script>
      const params = new URLSearchParams(location.search);
      const sampleMs = Number(params.get("sampleMs") || "100");
      const sessionLabel = params.get("sessionLabel") || `${Date.now().toString(36)}`;
      const state = {
        armed: false,
        seq: 0,
        startedAt: new Date().toISOString(),
      };
      const els = {
        state: document.querySelector("#state"),
        arm: document.querySelector("#arm"),
        log: document.querySelector("#log"),
      };

      function round(value) {
        return Math.round(value * 1000) / 1000;
      }

      function gamepadSnapshot(gamepad) {
        if (!gamepad) return null;
        return {
          index: gamepad.index,
          id: gamepad.id,
          mapping: gamepad.mapping || "",
          connected: gamepad.connected,
          timestamp: gamepad.timestamp,
          axes_count: gamepad.axes.length,
          buttons_count: gamepad.buttons.length,
          axes: gamepad.axes.map(round),
          buttons: gamepad.buttons.map((button) => ({
            pressed: button.pressed,
            touched: button.touched,
            value: round(button.value),
          })),
        };
      }

      async function postSample(type, extra = {}) {
        state.seq += 1;
        const gamepads = Array.from(navigator.getGamepads ? navigator.getGamepads() : []);
        const sample = {
          type,
          at: new Date().toISOString(),
          page_loaded_at: state.startedAt,
          session_label: sessionLabel,
          seq: state.seq,
          armed: state.armed,
          has_get_gamepads: Boolean(navigator.getGamepads),
          gamepad_count: gamepads.filter(Boolean).length,
          gamepads: gamepads.map(gamepadSnapshot),
          document_has_focus: document.hasFocus(),
          visibility_state: document.visibilityState,
          user_activation_active: navigator.userActivation ? navigator.userActivation.isActive : null,
          user_activation_has_been_active: navigator.userActivation ? navigator.userActivation.hasBeenActive : null,
          ...extra,
        };
        els.log.textContent = JSON.stringify(sample, null, 2);
        try {
          await fetch("/sample", {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify(sample),
          });
        } catch {
          // Leave the page useful even if opened without the local server.
        }
      }

      function tick() {
        if (!state.armed) return;
        postSample("poll");
        setTimeout(tick, sampleMs);
      }

      function arm(source) {
        if (state.armed) return;
        state.armed = true;
        els.arm.disabled = true;
        els.state.textContent = `Armed (${source})`;
        postSample("arm", { arm_source: source });
        tick();
      }

      els.arm.addEventListener("click", () => arm("button"));
      window.addEventListener("gamepadconnected", (event) => {
        postSample("gamepadconnected", { event_gamepad: gamepadSnapshot(event.gamepad) });
        arm("gamepadconnected");
      });
      window.addEventListener("gamepaddisconnected", (event) => {
        postSample("gamepaddisconnected", { event_gamepad: gamepadSnapshot(event.gamepad) });
      });

      if (params.get("autoArm") === "1") {
        setTimeout(() => arm("autoArm"), 200);
      }
      if (params.get("autoGesture") === "1") {
        setTimeout(() => {
          els.arm.focus();
          els.arm.click();
        }, 350);
      }
      window.focus();
    </script>
  </body>
</html>
"""


class ProbeHandler(http.server.BaseHTTPRequestHandler):
    sample_file: pathlib.Path

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802 - stdlib callback name
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path not in {"/", "/index.html"}:
            self.send_error(404)
            return
        body = PROBE_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "text/html; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802 - stdlib callback name
        if urllib.parse.urlparse(self.path).path != "/sample":
            self.send_error(404)
            return
        length = int(self.headers.get("content-length", "0"))
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_error(400)
            return
        with self.sample_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n")
        self.send_response(204)
        self.end_headers()


class ReusableThreadingTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def utc_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load_samples(path: pathlib.Path) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    if not path.exists():
        return samples
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            samples.append(value)
    return samples


def connected_gamepads(sample: dict[str, Any]) -> list[dict[str, Any]]:
    gamepads = sample.get("gamepads")
    if not isinstance(gamepads, list):
        return []
    return [gamepad for gamepad in gamepads if isinstance(gamepad, dict) and gamepad.get("connected") is True]


def summarize_samples(samples: list[dict[str, Any]]) -> dict[str, Any]:
    connected = [(sample, gamepad) for sample in samples for gamepad in connected_gamepads(sample)]
    ids = sorted({str(gamepad.get("id", "")) for _, gamepad in connected if gamepad.get("id")})
    mappings = sorted({str(gamepad.get("mapping", "")) for _, gamepad in connected})
    axes_lengths = sorted({int(gamepad.get("axes_count", 0)) for _, gamepad in connected})
    buttons_lengths = sorted({int(gamepad.get("buttons_count", 0)) for _, gamepad in connected})
    generic = [
        gamepad
        for _, gamepad in connected
        if "USB2BLE Gamepad" in str(gamepad.get("id", ""))
        and "STANDARD GAMEPAD" not in str(gamepad.get("id", ""))
        and str(gamepad.get("mapping", "")) == ""
    ]
    stale_xbox = [
        gamepad
        for _, gamepad in connected
        if str(gamepad.get("mapping", "")) == "standard"
        or "STANDARD GAMEPAD" in str(gamepad.get("id", ""))
    ]
    return {
        "sample_count": len(samples),
        "samples_with_gamepads": sum(1 for sample in samples if connected_gamepads(sample)),
        "connected_gamepad_observations": len(connected),
        "ids": ids,
        "mappings": mappings,
        "axes_lengths": axes_lengths,
        "buttons_lengths": buttons_lengths,
        "generic_gamepad_seen": bool(generic),
        "stale_or_standard_gamepad_seen": bool(stale_xbox),
        "document_focus_observed": any(sample.get("document_has_focus") is True for sample in samples),
        "user_activation_observed": any(sample.get("user_activation_has_been_active") is True for sample in samples),
        "first_connected_sample": connected[0][0] if connected else None,
        "last_sample": samples[-1] if samples else None,
    }


def open_chrome(url: str, mode: str, chrome_app: str, out_dir: pathlib.Path) -> dict[str, Any]:
    if mode == "none":
        return {"mode": mode, "command": None, "ok": True}
    command = ["open", "-a", chrome_app, url]
    temp_profile = None
    if mode == "temp-profile":
        temp_profile = tempfile.mkdtemp(prefix="usb2ble-chrome-gamepad-")
        command = [
            "open",
            "-na",
            chrome_app,
            "--args",
            f"--user-data-dir={temp_profile}",
            "--no-first-run",
            "--no-default-browser-check",
            url,
        ]
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    launch = {
        "mode": mode,
        "command": command,
        "ok": result.returncode == 0,
        "output": result.stdout,
        "temp_profile": temp_profile,
    }
    (out_dir / "chrome_launch.json").write_text(json.dumps(launch, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return launch


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--out-dir", type=pathlib.Path, default=pathlib.Path("target/generic-chrome-exposure-diagnosis"))
    parser.add_argument("--duration", type=float, default=10.0)
    parser.add_argument("--sample-ms", type=int, default=100)
    parser.add_argument("--session-label", default="")
    parser.add_argument("--chrome-mode", choices=["existing-profile", "temp-profile", "none"], default="existing-profile")
    parser.add_argument("--chrome-app", default="Google Chrome")
    parser.add_argument("--auto-gesture", action="store_true")
    args = parser.parse_args()

    stamp = utc_stamp()
    session_label = args.session_label or f"chrome-probe-{stamp}"
    run_dir = args.out_dir / f"chrome_gamepad_probe_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    sample_file = run_dir / "chrome_gamepad_probe.jsonl"
    sample_file.touch()
    ProbeHandler.sample_file = sample_file

    with ReusableThreadingTCPServer((args.host, args.port), ProbeHandler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        query = urllib.parse.urlencode(
            {
                "autoArm": "1",
                "autoGesture": "1" if args.auto_gesture else "0",
                "sampleMs": str(args.sample_ms),
                "sessionLabel": session_label,
            }
        )
        url = f"http://{args.host}:{args.port}/?{query}"
        launch = open_chrome(url, args.chrome_mode, args.chrome_app, run_dir)
        if not launch.get("ok"):
            raise SystemExit(f"Chrome launch failed: {launch.get('output')}")
        deadline = time.monotonic() + args.duration
        while time.monotonic() < deadline:
            time.sleep(0.2)
        server.shutdown()
        thread.join(timeout=2.0)

    samples = load_samples(sample_file)
    summary = {
        "captured_at": stamp,
        "run_dir": str(run_dir),
        "url": url,
        "chrome_mode": args.chrome_mode,
        "sample_file": str(sample_file),
        **summarize_samples(samples),
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    notes = [
        "# Chrome Gamepad Probe",
        "",
        f"- URL: `{url}`",
        f"- Chrome mode: `{args.chrome_mode}`",
        f"- Samples: {summary['sample_count']}",
        f"- Samples with gamepads: {summary['samples_with_gamepads']}",
        f"- IDs: {', '.join(summary['ids']) if summary['ids'] else 'none'}",
        f"- Generic gamepad seen: {summary['generic_gamepad_seen']}",
        f"- Standard/stale gamepad seen: {summary['stale_or_standard_gamepad_seen']}",
    ]
    (run_dir / "operator_notes.md").write_text("\n".join(notes) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
