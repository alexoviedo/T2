#!/usr/bin/env python3
"""Best-effort Windows gamepad visibility probe.

This diagnostic separates Windows controller visibility layers without making
compatibility claims:

* PnP/HID and Bluetooth inventory
* Raw Input device enumeration
* XInput slot state
* optional browser Gamepad API sampling
* GameInput availability notes
"""

from __future__ import annotations

import argparse
import ctypes
import datetime as dt
import http.server
import json
import os
import pathlib
import shutil
import socketserver
import subprocess
import sys
import threading
import time
import urllib.parse
from typing import Any


DEFAULT_OUT_DIR = pathlib.Path("target/windows-gamepad-probe")
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8870
ERROR_DEVICE_NOT_CONNECTED = 1167
RIM_TYPE_NAMES = {0: "mouse", 1: "keyboard", 2: "hid"}
RIDI_DEVICENAME = 0x20000007


BROWSER_PROBE_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>USB2BLE Windows Gamepad Probe</title>
    <style>
      body { margin: 0; font-family: system-ui, Segoe UI, sans-serif; background: #f7f8f5; color: #17201d; }
      main { width: min(960px, calc(100vw - 32px)); margin: 24px auto; display: grid; gap: 16px; }
      button { min-height: 40px; border: 1px solid #cfd8d0; border-radius: 6px; padding: 0 14px; background: #17201d; color: white; font: inherit; }
      button:disabled { opacity: 0.55; }
      pre { min-height: 360px; overflow: auto; border: 1px solid #cfd8d0; border-radius: 8px; background: white; padding: 12px; white-space: pre-wrap; overflow-wrap: anywhere; }
    </style>
  </head>
  <body>
    <main>
      <h1>USB2BLE Windows Gamepad Probe</h1>
      <p id="state">Idle</p>
      <button id="arm" type="button">Arm Probe</button>
      <pre id="log"></pre>
    </main>
    <script>
      const params = new URLSearchParams(location.search);
      const sampleMs = Number(params.get("sampleMs") || "100");
      const state = { armed: false, seq: 0 };
      const els = { state: document.querySelector("#state"), arm: document.querySelector("#arm"), log: document.querySelector("#log") };
      function round(value) { return Math.round(value * 1000) / 1000; }
      function snapshot(gamepad) {
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
          buttons: gamepad.buttons.map((button) => ({ pressed: button.pressed, touched: button.touched, value: round(button.value) })),
        };
      }
      async function postSample(type) {
        state.seq += 1;
        const sample = {
          type,
          at: new Date().toISOString(),
          seq: state.seq,
          has_get_gamepads: Boolean(navigator.getGamepads),
          gamepads: Array.from(navigator.getGamepads ? navigator.getGamepads() : []).map(snapshot),
          document_has_focus: document.hasFocus(),
          visibility_state: document.visibilityState,
        };
        els.log.textContent = JSON.stringify(sample, null, 2);
        try {
          await fetch("/sample", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(sample) });
        } catch {}
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
        postSample("arm");
        tick();
      }
      els.arm.addEventListener("click", () => arm("button"));
      window.addEventListener("gamepadconnected", () => arm("gamepadconnected"));
      if (params.get("autoArm") === "1") setTimeout(() => arm("autoArm"), 250);
    </script>
  </body>
</html>
"""


def utc_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_command(command: list[str], timeout: float = 20.0) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        return {"command": command, "returncode": None, "output": str(exc), "ok": False}
    except subprocess.TimeoutExpired as exc:
        return {"command": command, "returncode": None, "output": exc.stdout or "", "ok": False, "timeout": True}
    return {"command": command, "returncode": result.returncode, "output": result.stdout, "ok": result.returncode == 0}


def powershell_json(script: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        script,
    ]
    result = run_command(command)
    if not result["ok"]:
        return [], result
    text = str(result.get("output", "")).strip()
    if not text:
        return [], result
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        result["json_error"] = "could not parse PowerShell JSON output"
        return [], result
    if isinstance(parsed, dict):
        return [parsed], result
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)], result
    return [], result


def collect_pnp_inventory() -> dict[str, Any]:
    scripts = {
        "hidclass": "Get-PnpDevice -Class HIDClass -ErrorAction SilentlyContinue | Select-Object Status,Class,FriendlyName,InstanceId | ConvertTo-Json -Depth 4",
        "bluetooth": "Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue | Select-Object Status,Class,FriendlyName,InstanceId | ConvertTo-Json -Depth 4",
        "controller_named": "Get-CimInstance Win32_PnPEntity | Where-Object { $_.Name -match 'game|xbox|controller|joystick|hid|bluetooth|usb' } | Select-Object Name,Status,PNPClass,DeviceID,Manufacturer | ConvertTo-Json -Depth 4",
    }
    inventory: dict[str, Any] = {}
    for name, script in scripts.items():
        devices, command = powershell_json(script)
        inventory[name] = {"devices": devices, "command": command}
    return inventory


class RAWINPUTDEVICELIST(ctypes.Structure):
    _fields_ = [("hDevice", ctypes.c_void_p), ("dwType", ctypes.c_ulong)]


def collect_raw_input_devices() -> dict[str, Any]:
    if os.name != "nt":
        return {"available": False, "reason": "Raw Input enumeration is Windows-only.", "devices": []}
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    count = ctypes.c_uint(0)
    size = ctypes.sizeof(RAWINPUTDEVICELIST)
    rc = user32.GetRawInputDeviceList(None, ctypes.byref(count), size)
    if rc == ctypes.c_uint(-1).value:
        return {"available": False, "reason": f"GetRawInputDeviceList failed: {ctypes.get_last_error()}", "devices": []}
    devices_array = (RAWINPUTDEVICELIST * count.value)()
    rc = user32.GetRawInputDeviceList(devices_array, ctypes.byref(count), size)
    if rc == ctypes.c_uint(-1).value:
        return {"available": False, "reason": f"GetRawInputDeviceList read failed: {ctypes.get_last_error()}", "devices": []}

    devices: list[dict[str, Any]] = []
    for item in devices_array[: count.value]:
        name_size = ctypes.c_uint(0)
        user32.GetRawInputDeviceInfoW(item.hDevice, RIDI_DEVICENAME, None, ctypes.byref(name_size))
        name = ""
        if name_size.value:
            buffer = ctypes.create_unicode_buffer(name_size.value)
            if user32.GetRawInputDeviceInfoW(item.hDevice, RIDI_DEVICENAME, buffer, ctypes.byref(name_size)) != ctypes.c_uint(-1).value:
                name = buffer.value
        devices.append(
            {
                "handle": hex(int(item.hDevice or 0)),
                "type": RIM_TYPE_NAMES.get(int(item.dwType), f"unknown_{int(item.dwType)}"),
                "name": name,
                "looks_like_game_controller": looks_like_controller_name(name),
            }
        )
    return {"available": True, "devices": devices, "controller_like_count": sum(1 for device in devices if device["looks_like_game_controller"])}


class XINPUT_GAMEPAD(ctypes.Structure):
    _fields_ = [
        ("wButtons", ctypes.c_ushort),
        ("bLeftTrigger", ctypes.c_ubyte),
        ("bRightTrigger", ctypes.c_ubyte),
        ("sThumbLX", ctypes.c_short),
        ("sThumbLY", ctypes.c_short),
        ("sThumbRX", ctypes.c_short),
        ("sThumbRY", ctypes.c_short),
    ]


class XINPUT_STATE(ctypes.Structure):
    _fields_ = [("dwPacketNumber", ctypes.c_ulong), ("Gamepad", XINPUT_GAMEPAD)]


def load_xinput() -> tuple[Any | None, str | None, str | None]:
    if os.name != "nt":
        return None, None, "XInput is Windows-only."
    for name in ("xinput1_4", "xinput1_3", "xinput9_1_0"):
        try:
            return ctypes.WinDLL(name), name, None
        except OSError:
            continue
    return None, None, "No XInput DLL could be loaded."


def collect_xinput_slots() -> dict[str, Any]:
    dll, dll_name, error = load_xinput()
    if dll is None:
        return {"available": False, "dll": dll_name, "error": error, "slots": []}
    slots: list[dict[str, Any]] = []
    for index in range(4):
        state = XINPUT_STATE()
        rc = int(dll.XInputGetState(index, ctypes.byref(state)))
        connected = rc == 0
        slot: dict[str, Any] = {
            "slot": index,
            "return_code": rc,
            "connected": connected,
            "not_connected": rc == ERROR_DEVICE_NOT_CONNECTED,
        }
        if connected:
            slot["packet_number"] = int(state.dwPacketNumber)
            slot["buttons"] = int(state.Gamepad.wButtons)
            slot["left_trigger"] = int(state.Gamepad.bLeftTrigger)
            slot["right_trigger"] = int(state.Gamepad.bRightTrigger)
            slot["left_thumb"] = [int(state.Gamepad.sThumbLX), int(state.Gamepad.sThumbLY)]
            slot["right_thumb"] = [int(state.Gamepad.sThumbRX), int(state.Gamepad.sThumbRY)]
        slots.append(slot)
    return {"available": True, "dll": dll_name, "slots": slots, "connected_count": sum(1 for slot in slots if slot["connected"])}


def looks_like_controller_name(name: str) -> bool:
    lowered = name.lower()
    tokens = ("gamepad", "game controller", "xbox", "joystick", "usb2ble", "hid#vid_303a")
    return any(token in lowered for token in tokens)


def summarize_pnp_inventory(inventory: dict[str, Any]) -> dict[str, Any]:
    controller_like: list[dict[str, Any]] = []
    for section in inventory.values():
        devices = section.get("devices", [])
        if not isinstance(devices, list):
            continue
        for device in devices:
            if not isinstance(device, dict):
                continue
            haystack = " ".join(str(device.get(key, "")) for key in ("FriendlyName", "Name", "InstanceId", "DeviceID"))
            if looks_like_controller_name(haystack):
                controller_like.append(device)
    return {"controller_like_count": len(controller_like), "controller_like_devices": controller_like}


class BrowserProbeHandler(http.server.BaseHTTPRequestHandler):
    sample_file: pathlib.Path

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802
        if urllib.parse.urlparse(self.path).path not in {"/", "/index.html"}:
            self.send_error(404)
            return
        body = BROWSER_PROBE_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "text/html; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        if urllib.parse.urlparse(self.path).path != "/sample":
            self.send_error(404)
            return
        length = int(self.headers.get("content-length", "0"))
        payload = self.rfile.read(length)
        try:
            sample = json.loads(payload.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_error(400)
            return
        with self.sample_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(sample, separators=(",", ":"), sort_keys=True) + "\n")
        self.send_response(204)
        self.end_headers()


class ReusableThreadingTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def browser_candidates() -> dict[str, list[str]]:
    local = os.environ.get("LOCALAPPDATA", "")
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    return {
        "edge": [
            shutil.which("msedge") or "",
            str(pathlib.Path(program_files) / "Microsoft" / "Edge" / "Application" / "msedge.exe"),
            str(pathlib.Path(program_files_x86) / "Microsoft" / "Edge" / "Application" / "msedge.exe"),
        ],
        "chrome": [
            shutil.which("chrome") or "",
            str(pathlib.Path(program_files) / "Google" / "Chrome" / "Application" / "chrome.exe"),
            str(pathlib.Path(program_files_x86) / "Google" / "Chrome" / "Application" / "chrome.exe"),
            str(pathlib.Path(local) / "Google" / "Chrome" / "Application" / "chrome.exe"),
        ],
    }


def find_browser(name: str) -> str | None:
    for candidate in browser_candidates().get(name, []):
        if candidate and pathlib.Path(candidate).exists():
            return candidate
    return None


def load_browser_samples(path: pathlib.Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    samples: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            samples.append(parsed)
    return samples


def summarize_browser_samples(samples: list[dict[str, Any]]) -> dict[str, Any]:
    connected = []
    for sample in samples:
        gamepads = sample.get("gamepads")
        if not isinstance(gamepads, list):
            continue
        connected.extend(gamepad for gamepad in gamepads if isinstance(gamepad, dict) and gamepad.get("connected") is True)
    return {
        "sample_count": len(samples),
        "connected_gamepad_observations": len(connected),
        "ids": sorted({str(gamepad.get("id", "")) for gamepad in connected if gamepad.get("id")}),
        "mappings": sorted({str(gamepad.get("mapping", "")) for gamepad in connected}),
        "gamepad_visible": bool(connected),
    }


def run_browser_probe(
    browser: str,
    run_dir: pathlib.Path,
    host: str,
    port: int,
    duration: float,
    sample_ms: int,
    temp_browser_profile: bool,
) -> dict[str, Any]:
    browser_path = find_browser(browser)
    if browser_path is None:
        return {"enabled": True, "ok": False, "browser": browser, "reason": f"{browser} executable was not found."}

    run_dir.mkdir(parents=True, exist_ok=True)
    sample_file = run_dir / "browser_gamepad_samples.jsonl"
    sample_file.touch()
    user_data_dir = run_dir / "browser_user_data" if temp_browser_profile else None
    if user_data_dir is not None:
        user_data_dir.mkdir(parents=True, exist_ok=True)
    BrowserProbeHandler.sample_file = sample_file
    with ReusableThreadingTCPServer((host, port), BrowserProbeHandler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        query = urllib.parse.urlencode({"autoArm": "1", "sampleMs": str(sample_ms)})
        url = f"http://{host}:{port}/?{query}"
        command = [
            browser_path,
            "--new-window",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-timer-throttling",
            url,
        ]
        if user_data_dir is not None:
            command.insert(-1, f"--user-data-dir={user_data_dir}")
        launch = run_command(command, timeout=10.0)
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            time.sleep(0.2)
        server.shutdown()
        thread.join(timeout=2.0)

    samples = load_browser_samples(sample_file)
    return {
        "enabled": True,
        "ok": True,
        "browser": browser,
        "browser_path": browser_path,
        "launch": launch,
        "sample_file": str(sample_file),
        "temp_browser_profile": temp_browser_profile,
        "browser_user_data_dir": str(user_data_dir) if user_data_dir is not None else None,
        "summary": summarize_browser_samples(samples),
    }


def gameinput_status() -> dict[str, Any]:
    system_root = pathlib.Path(os.environ.get("SystemRoot", r"C:\Windows"))
    candidates = [
        system_root / "System32" / "GameInput.dll",
        system_root / "SysWOW64" / "GameInput.dll",
    ]
    found = [str(path) for path in candidates if path.exists()]
    return {
        "available_dlls": found,
        "status": "future_work",
        "note": "GameInput is not exercised by this lightweight probe; use SDK-backed tooling later if a game target needs it.",
    }


def write_notes(run_dir: pathlib.Path, summary: dict[str, Any]) -> None:
    notes = [
        "# Windows Gamepad Probe",
        "",
        "This is diagnostic inventory only. It does not prove Windows or game compatibility.",
        "",
        "## Layer Summary",
        "",
        f"- PnP controller-like devices: {summary['pnp']['controller_like_count']}",
        f"- Raw Input controller-like devices: {summary['raw_input'].get('controller_like_count', 0)}",
        f"- XInput connected slots: {summary['xinput'].get('connected_count', 0)}",
        f"- Browser gamepad visible: {summary['browser'].get('summary', {}).get('gamepad_visible', False) if summary['browser'].get('enabled') else 'not run'}",
        "",
        "## Manual Fallback",
        "",
        "- Open `joy.cpl` from Run or PowerShell to view Windows Game Controllers.",
        "- XInput usually sees Xbox-compatible controllers only; Generic BLE HID gamepads may be visible through HID/Raw Input or browser layers while absent from XInput.",
        "- Browser Gamepad API, XInput, Raw Input/HID, GameInput, Steam Input, and a real game can each disagree.",
    ]
    (run_dir / "operator_notes.md").write_text("\n".join(notes) + "\n", encoding="utf-8")


def build_summary(args: argparse.Namespace, run_dir: pathlib.Path) -> dict[str, Any]:
    pnp = collect_pnp_inventory()
    pnp_summary = summarize_pnp_inventory(pnp)
    raw_input = collect_raw_input_devices()
    xinput = collect_xinput_slots()
    browser: dict[str, Any]
    if args.browser == "none":
        browser = {"enabled": False, "reason": "Browser probe not requested."}
    else:
        browser = run_browser_probe(
            args.browser,
            run_dir,
            args.host,
            args.port,
            args.browser_duration,
            args.sample_ms,
            args.temp_browser_profile,
        )
    return {
        "captured_at": utc_stamp(),
        "platform": sys.platform,
        "run_dir": str(run_dir),
        "pnp": pnp_summary,
        "raw_input": raw_input,
        "xinput": xinput,
        "browser": browser,
        "gameinput": gameinput_status(),
        "joy_cpl": {
            "command": "joy.cpl",
            "note": "Manual Windows Game Controllers control-panel fallback; not launched by default.",
        },
        "no_controller_found": (
            pnp_summary["controller_like_count"] == 0
            and raw_input.get("controller_like_count", 0) == 0
            and xinput.get("connected_count", 0) == 0
            and not browser.get("summary", {}).get("gamepad_visible", False)
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=pathlib.Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--browser", choices=["none", "edge", "chrome"], default="none")
    parser.add_argument("--browser-duration", type=float, default=8.0)
    parser.add_argument("--sample-ms", type=int, default=100)
    parser.add_argument(
        "--temp-browser-profile",
        action="store_true",
        help="Launch the browser with a fresh user-data directory under the probe output folder.",
    )
    args = parser.parse_args()

    stamp = utc_stamp()
    run_dir = args.out_dir / f"windows_gamepad_probe_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    summary = build_summary(args, run_dir)
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    inventory = collect_pnp_inventory()
    (run_dir / "pnp_inventory.json").write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_notes(run_dir, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
