#!/usr/bin/env python3
"""Witness helper for the public USB2BLE Gamepad API tester page.

This drives deterministic Xbox reports from the target while a desktop browser
captures Gamepad API evidence from the public/static tester page. It does not
use or require physical HOTAS movement.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import urlopen
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from serial_command import SerialPort  # type: ignore
from windows_gamepad_probe import collect_xinput_slots, find_browser  # type: ignore


DEFAULT_PUBLIC_URL = "https://alexoviedo.github.io/T2/gamepad-test.html"
DEFAULT_SCENARIOS = [
    "neutral",
    "left_stick_left",
    "left_stick_right",
    "left_stick_up",
    "left_stick_down",
    "right_stick_left",
    "right_stick_right",
    "left_trigger_max",
    "right_trigger_max",
    "button_a",
    "button_b",
    "hat_up",
    "hat_right",
    "hat_down",
    "hat_left",
]


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_tester_url(
    base_url: str,
    *,
    expected_profile: str,
    capture_seconds: float,
    auto_download: bool,
    auto_arm: bool,
    sample_ms: int,
) -> str:
    """Return tester URL with capture parameters merged into any existing query."""

    parts = urlsplit(base_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.update(
        {
            "autoArm": "1" if auto_arm else "0",
            "expectedProfile": expected_profile,
            "captureMs": str(int(capture_seconds * 1000)),
            "sampleMs": str(sample_ms),
        }
    )
    if auto_download:
        query["autoDownload"] = "1"
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def summarize_browser_evidence(evidence: dict[str, Any] | None) -> dict[str, Any]:
    if not evidence:
        return {
            "downloaded": False,
            "gamepad_count": 0,
            "changed_axes": [],
            "changed_buttons": [],
            "profile": None,
        }

    primary = evidence.get("primary_gamepad") or {}
    summary = evidence.get("summary") or {}
    changed_axes = summary.get("changed_axes")
    changed_buttons = summary.get("changed_buttons")
    if changed_axes is None:
        changed_axes = primary.get("changed_axes") or []
    if changed_buttons is None:
        changed_buttons = primary.get("changed_buttons") or []

    return {
        "downloaded": True,
        "schema": evidence.get("schema"),
        "profile": evidence.get("expected_profile"),
        "gamepad_count": evidence.get("gamepad_count", 0),
        "gamepad_id": primary.get("id"),
        "mapping": primary.get("mapping"),
        "changed_axes": changed_axes,
        "changed_buttons": changed_buttons,
        "sample_count": evidence.get("sample_count"),
    }


def browser_evidence_passes(evidence: dict[str, Any] | None, expected_profile: str) -> tuple[bool, list[str]]:
    summary = summarize_browser_evidence(evidence)
    reasons: list[str] = []
    if not summary["downloaded"]:
        reasons.append("browser evidence JSON was not downloaded")
    if summary.get("gamepad_count", 0) < 1:
        reasons.append("tester reported no connected gamepad")
    if expected_profile == "xbox-standard" and summary.get("mapping") not in ("standard", None):
        reasons.append(f"expected standard mapping for Xbox profile, saw {summary.get('mapping')!r}")
    if not summary.get("changed_axes"):
        reasons.append("tester did not report changed axes")
    if not summary.get("changed_buttons"):
        reasons.append("tester did not report changed buttons")
    return not reasons, reasons


def xinput_has_connected_slot(slots: dict[str, Any]) -> bool:
    for slot in slots.get("slots", []):
        if slot.get("connected"):
            return True
    return False


def choose_xinput_slot(slots: dict[str, Any]) -> int | None:
    for slot in slots.get("slots", []):
        if slot.get("connected"):
            return int(slot.get("slot"))
    return None


def xinput_scenario_moved(scenario: str, slot: dict[str, Any]) -> bool:
    buttons = int(slot.get("buttons", 0))
    left_thumb = slot.get("left_thumb") or [0, 0]
    right_thumb = slot.get("right_thumb") or [0, 0]
    left_x = int(left_thumb[0])
    left_y = int(left_thumb[1])
    right_x = int(right_thumb[0])
    checks = {
        "left_stick_left": lambda: left_x < -8000,
        "left_stick_right": lambda: left_x > 8000,
        "left_stick_up": lambda: left_y > 8000,
        "left_stick_down": lambda: left_y < -8000,
        "right_stick_left": lambda: right_x < -8000,
        "right_stick_right": lambda: right_x > 8000,
        "left_trigger_max": lambda: int(slot.get("left_trigger", 0)) >= 180,
        "right_trigger_max": lambda: int(slot.get("right_trigger", 0)) >= 180,
        "button_a": lambda: bool(buttons & 0x1000),
        "button_b": lambda: bool(buttons & 0x2000),
        "hat_up": lambda: bool(buttons & 0x0001),
        "hat_right": lambda: bool(buttons & 0x0008),
        "hat_down": lambda: bool(buttons & 0x0002),
        "hat_left": lambda: bool(buttons & 0x0004),
        "dpad_up": lambda: bool(buttons & 0x0001),
        "dpad_right": lambda: bool(buttons & 0x0008),
        "dpad_down": lambda: bool(buttons & 0x0002),
        "dpad_left": lambda: bool(buttons & 0x0004),
    }
    check = checks.get(scenario)
    return True if check is None else bool(check())


def autodetect_ports() -> list[str]:
    cmd = [
        "powershell",
        "-NoProfile",
        "-Command",
        "[System.IO.Ports.SerialPort]::GetPortNames() | Sort-Object",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def probe_port(port: str, timeout: float) -> bool:
    serial: SerialPort | None = None
    try:
        serial = SerialPort(port)
        responses = serial.command_response("GET_INFO", timeout)
        joined = "\n".join(responses)
        return "INFO:" in joined or "USB2BLE" in joined or "firmware" in joined.lower()
    except Exception:
        return False
    finally:
        if serial is not None:
            serial.close()


def select_port(explicit_port: str | None, timeout: float) -> str:
    if explicit_port:
        return explicit_port
    ports = autodetect_ports()
    for port in ports:
        if probe_port(port, timeout):
            return port
    if ports:
        return ports[0]
    raise RuntimeError("no serial ports detected")


def send_command(
    session: SerialPort,
    command: str,
    transcript: list[dict[str, Any]],
    *,
    fatal: bool = False,
) -> str:
    started = time.time()
    entry: dict[str, Any] = {
        "timestamp": iso_now(),
        "command": command,
    }
    try:
        responses = session.command_response(command, 5.0)
        response = "\n".join(responses) if responses else "<no matching response>"
        entry["responses"] = responses
        entry["response"] = response
        entry["elapsed_ms"] = round((time.time() - started) * 1000, 1)
        transcript.append(entry)
        return response
    except Exception as exc:
        entry["error"] = str(exc)
        entry["elapsed_ms"] = round((time.time() - started) * 1000, 1)
        transcript.append(entry)
        if fatal:
            raise
        return f"ERROR:{exc}"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")


def create_browser_profile(profile_dir: Path, download_dir: Path) -> None:
    profile_dir = profile_dir.resolve()
    download_dir = download_dir.resolve()
    default_dir = profile_dir / "Default"
    default_dir.mkdir(parents=True, exist_ok=True)
    download_dir.mkdir(parents=True, exist_ok=True)
    prefs = {
        "download": {
            "default_directory": str(download_dir),
            "directory_upgrade": True,
            "prompt_for_download": False,
        },
        "profile": {"default_content_setting_values": {"automatic_downloads": 1}},
        "safebrowsing": {"enabled": True},
    }
    (default_dir / "Preferences").write_text(json.dumps(prefs), encoding="utf-8")


def free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def launch_browser(
    browser_name: str,
    url: str,
    profile_dir: Path,
    download_dir: Path,
    debug_port: int,
) -> subprocess.Popen[str]:
    browser_path = find_browser(browser_name)
    if browser_path is None:
        raise RuntimeError(f"{browser_name} executable was not found")
    profile_dir = profile_dir.resolve()
    download_dir = download_dir.resolve()
    create_browser_profile(profile_dir, download_dir)
    cmd = [
        str(browser_path),
        f"--user-data-dir={profile_dir}",
        "--new-window",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-timer-throttling",
        "--disable-renderer-backgrounding",
        "--remote-debugging-address=127.0.0.1",
        f"--remote-debugging-port={debug_port}",
        "--window-size=1180,920",
        url,
    ]
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True)


def websocket_send(sock: socket.socket, payload: dict[str, Any]) -> None:
    data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    header = bytearray([0x81])
    length = len(data)
    if length < 126:
        header.append(0x80 | length)
    elif length < 65536:
        header.extend([0x80 | 126, (length >> 8) & 0xFF, length & 0xFF])
    else:
        header.extend(
            [
                0x80 | 127,
                (length >> 56) & 0xFF,
                (length >> 48) & 0xFF,
                (length >> 40) & 0xFF,
                (length >> 32) & 0xFF,
                (length >> 24) & 0xFF,
                (length >> 16) & 0xFF,
                (length >> 8) & 0xFF,
                length & 0xFF,
            ]
        )
    mask = os.urandom(4)
    masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(data))
    sock.sendall(bytes(header) + mask + masked)


def recv_exact(sock: socket.socket, length: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < length:
        chunk = sock.recv(length - len(chunks))
        if not chunk:
            raise RuntimeError("websocket closed")
        chunks.extend(chunk)
    return bytes(chunks)


def websocket_recv_text(sock: socket.socket) -> str:
    while True:
        first, second = recv_exact(sock, 2)
        opcode = first & 0x0F
        masked = bool(second & 0x80)
        length = second & 0x7F
        if length == 126:
            hi, lo = recv_exact(sock, 2)
            length = (hi << 8) | lo
        elif length == 127:
            raw_len = recv_exact(sock, 8)
            length = int.from_bytes(raw_len, "big")
        mask = recv_exact(sock, 4) if masked else b""
        data = recv_exact(sock, length) if length else b""
        if masked:
            data = bytes(byte ^ mask[index % 4] for index, byte in enumerate(data))
        if opcode == 0x1:
            return data.decode("utf-8")
        if opcode == 0x8:
            raise RuntimeError("websocket close frame received")
        if opcode == 0x9:
            # Ping; reply with pong.
            sock.sendall(bytes([0x8A, len(data)]) + data)


class DevToolsClient:
    def __init__(self, ws_url: str) -> None:
        parts = urlsplit(ws_url)
        if parts.scheme != "ws":
            raise RuntimeError(f"unsupported DevTools URL scheme: {parts.scheme}")
        self._host = parts.hostname or "127.0.0.1"
        self._port = parts.port or 80
        self._path = parts.path
        if parts.query:
            self._path += f"?{parts.query}"
        self._sock = socket.create_connection((self._host, self._port), timeout=10.0)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET {self._path} HTTP/1.1\r\n"
            f"Host: {self._host}:{self._port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        )
        self._sock.sendall(request.encode("ascii"))
        response = b""
        while b"\r\n\r\n" not in response:
            response += self._sock.recv(4096)
        if b" 101 " not in response.split(b"\r\n", 1)[0]:
            raise RuntimeError(f"DevTools websocket handshake failed: {response[:120]!r}")
        self._next_id = 1

    def close(self) -> None:
        self._sock.close()

    def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        message_id = self._next_id
        self._next_id += 1
        payload: dict[str, Any] = {"id": message_id, "method": method}
        if params is not None:
            payload["params"] = params
        websocket_send(self._sock, payload)
        while True:
            message = json.loads(websocket_recv_text(self._sock))
            if message.get("id") != message_id:
                continue
            if "error" in message:
                raise RuntimeError(f"DevTools evaluate failed: {message['error']}")
            return message.get("result", {})

    def evaluate_json(self, expression: str) -> Any:
        message = self.call(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
            },
        )
        result = message.get("result", {})
        value = result.get("value")
        return json.loads(value) if isinstance(value, str) and value else None


def find_devtools_ws_url(debug_port: int, expected_path: str, timeout: float = 10.0) -> str | None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urlopen(f"http://127.0.0.1:{debug_port}/json", timeout=2.0) as response:
                targets = json.loads(response.read().decode("utf-8"))
        except Exception:
            time.sleep(0.25)
            continue
        for target in targets:
            if not isinstance(target, dict):
                continue
            url = str(target.get("url", ""))
            if expected_path in url and target.get("webSocketDebuggerUrl"):
                return str(target["webSocketDebuggerUrl"])
        for target in targets:
            if isinstance(target, dict) and target.get("type") == "page" and target.get("webSocketDebuggerUrl"):
                return str(target["webSocketDebuggerUrl"])
        time.sleep(0.25)
    return None


def capture_page_evidence(debug_port: int, expected_path: str, out_dir: Path) -> tuple[dict[str, Any] | None, str | None]:
    ws_url = find_devtools_ws_url(debug_port, expected_path)
    if ws_url is None:
        return None, "could not find DevTools page target"
    client = DevToolsClient(ws_url)
    try:
        expression = "JSON.stringify(window.__usb2bleGamepadTesterEvidence || null)"
        evidence = client.evaluate_json(expression)
    except Exception as exc:
        return None, str(exc)
    finally:
        client.close()
    if evidence:
        write_json(out_dir / "gamepad_tester_evidence_cdp.json", evidence)
    return evidence, None


def click_arm_button(debug_port: int, expected_path: str) -> tuple[bool, str | None]:
    ws_url = find_devtools_ws_url(debug_port, expected_path)
    if ws_url is None:
        return False, "could not find DevTools page target"
    client = DevToolsClient(ws_url)
    try:
        client.call("Page.bringToFront")
        client.evaluate_json('JSON.stringify((() => { window.focus(); return {"focused": document.hasFocus()}; })())')
        rect = None
        for _ in range(20):
            rect = client.evaluate_json(
                "JSON.stringify((() => {"
                "const el = document.querySelector('#arm');"
                "if (!el) return null;"
                "const r = el.getBoundingClientRect();"
                "return {x: r.left + r.width / 2, y: r.top + r.height / 2, disabled: el.disabled};"
                "})())"
            )
            if rect and not rect.get("disabled"):
                break
            time.sleep(0.25)
        if not rect:
            return False, "Arm button was not found"
        if rect.get("disabled"):
            return False, "Arm button was already disabled"
        x = float(rect["x"])
        y = float(rect["y"])
        client.call(
            "Input.dispatchMouseEvent",
            {"type": "mouseMoved", "x": x, "y": y, "button": "none", "buttons": 0},
        )
        client.call(
            "Input.dispatchMouseEvent",
            {"type": "mousePressed", "x": x, "y": y, "button": "left", "buttons": 1, "clickCount": 1},
        )
        client.call(
            "Input.dispatchMouseEvent",
            {"type": "mouseReleased", "x": x, "y": y, "button": "left", "buttons": 0, "clickCount": 1},
        )
        return True, None
    except Exception as exc:
        return False, str(exc)
    finally:
        client.close()


def collect_xinput_sample(label: str) -> dict[str, Any]:
    slots = collect_xinput_slots()
    return {
        "timestamp": iso_now(),
        "label": label,
        "slots": slots.get("slots", []),
    }


def connected_slot_from_sample(sample: dict[str, Any]) -> dict[str, Any] | None:
    for slot in sample.get("slots", []):
        if slot.get("connected"):
            return slot
    return None


def drive_sequence(
    session: SerialPort,
    scenarios: list[str],
    transcript: list[dict[str, Any]],
    samples_path: Path,
    *,
    settle_seconds: float,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    with samples_path.open("w", encoding="utf-8") as samples:
        for scenario in scenarios:
            if scenario != "neutral":
                send_command(session, "PUBLISH_XBOX_TEST_REPORT neutral", transcript)
                time.sleep(0.25)
            response = send_command(session, f"PUBLISH_XBOX_TEST_REPORT {scenario}", transcript)
            time.sleep(settle_seconds)
            sample = collect_xinput_sample(scenario)
            samples.write(json.dumps(sample, sort_keys=True) + "\n")
            slot = connected_slot_from_sample(sample)
            moved = xinput_scenario_moved(scenario, slot) if slot else False
            results.append(
                {
                    "scenario": scenario,
                    "serial_response": response,
                    "xinput_connected": slot is not None,
                    "xinput_moved": moved,
                    "slot": None if slot is None else slot.get("slot"),
                }
            )
        send_command(session, "PUBLISH_XBOX_TEST_REPORT neutral", transcript)
        time.sleep(0.25)
        sample = collect_xinput_sample("final_neutral")
        samples.write(json.dumps(sample, sort_keys=True) + "\n")
    moved = [row["scenario"] for row in results if row["xinput_moved"]]
    return {
        "scenario_count": len(results),
        "moved_scenarios": moved,
        "results": results,
    }


def wait_for_evidence(download_dir: Path, started_at: float, timeout: float) -> tuple[dict[str, Any] | None, Path | None]:
    deadline = time.time() + timeout
    last_candidate: Path | None = None
    while time.time() < deadline:
        candidates = [
            path
            for path in download_dir.glob("usb2ble-gamepad-evidence-*.json")
            if path.stat().st_mtime >= started_at and not path.name.endswith(".crdownload")
        ]
        if candidates:
            last_candidate = max(candidates, key=lambda path: path.stat().st_mtime)
            try:
                return json.loads(last_candidate.read_text(encoding="utf-8")), last_candidate
            except json.JSONDecodeError:
                time.sleep(0.25)
        time.sleep(0.5)
    return None, last_candidate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_PUBLIC_URL)
    parser.add_argument("--local", action="store_true", help="Use --url as a local tester URL label; no server is started.")
    parser.add_argument("--persona", choices=["xbox"], default="xbox")
    parser.add_argument("--expected-profile", default="xbox-standard")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--port")
    parser.add_argument("--browser", choices=["edge", "chrome"], default="edge")
    parser.add_argument("--capture-seconds", type=float, default=20.0)
    parser.add_argument("--sample-ms", type=int, default=100)
    parser.add_argument("--settle-seconds", type=float, default=0.65)
    parser.add_argument("--serial-timeout", type=float, default=5.0)
    parser.add_argument("--skip-prepare", action="store_true")
    parser.add_argument("--auto-arm", action="store_true", help="Use page autoArm instead of CDP mouse-click arming.")
    parser.add_argument("--no-physical-input", action="store_true", default=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    browser_dir = out_dir / "browser_profile"
    download_dir = out_dir / "downloads"
    transcript: list[dict[str, Any]] = []

    started_at = time.time()
    port = select_port(args.port, args.serial_timeout)
    target_url = build_tester_url(
        args.url,
        expected_profile=args.expected_profile,
        capture_seconds=args.capture_seconds,
        auto_download=True,
        auto_arm=args.auto_arm,
        sample_ms=args.sample_ms,
    )

    browser_proc: subprocess.Popen[str] | None = None
    debug_port = free_tcp_port()
    summary: dict[str, Any] = {
        "schema": "usb2ble_public_gamepad_tester_witness_v1",
        "started_at": iso_now(),
        "url": args.url,
        "tester_url": target_url,
        "persona": args.persona,
        "expected_profile": args.expected_profile,
        "port": port,
        "browser": args.browser,
        "devtools_port": debug_port,
        "no_physical_input": True,
    }

    try:
        session = SerialPort(port)
        try:
            for command in (
                "GET_INFO",
                "GET_STATUS",
                "GET_USB_STATUS",
                "LIST_USB_DEVICES",
                "GET_CONFIG_STATUS",
                "GET_STARTUP_BLE_CONFIG",
                "GET_BLE_IDENTITY_INFO",
                "GET_BLE_CONNECTION_INFO",
                "GET_BLE_BOND_INFO",
            ):
                send_command(session, command, transcript)

            if not args.skip_prepare:
                send_command(session, "SET_BLE_IDENTITY_STRATEGY persona_static_random_experimental", transcript)
                send_command(session, "START_BLE_XBOX_CONTROLLER", transcript)
                time.sleep(1.0)
                send_command(session, "GET_BLE_CONNECTION_INFO", transcript)

            baseline_xinput = collect_xinput_sample("baseline")
            write_json(out_dir / "xinput_baseline.json", baseline_xinput)
            summary["baseline_xinput_connected"] = connected_slot_from_sample(baseline_xinput) is not None
            summary["baseline_xinput_slot"] = (
                connected_slot_from_sample(baseline_xinput) or {}
            ).get("slot")

            browser_launch_time = time.time()
            browser_proc = launch_browser(args.browser, target_url, browser_dir, download_dir, debug_port)
            time.sleep(2.0)
            if not args.auto_arm:
                arm_ok, arm_error = click_arm_button(debug_port, "gamepad-test.html")
                summary["browser_arm_method"] = "cdp_mouse_click"
                summary["browser_arm_ok"] = arm_ok
                if arm_error:
                    summary["browser_arm_error"] = arm_error
                browser_launch_time = time.time()
            else:
                summary["browser_arm_method"] = "autoArm"
                summary["browser_arm_ok"] = True

            sequence = drive_sequence(
                session,
                DEFAULT_SCENARIOS,
                transcript,
                out_dir / "xinput_samples.jsonl",
                settle_seconds=args.settle_seconds,
            )
            summary["xinput_sequence"] = sequence
        finally:
            session.close()

        remaining_capture = browser_launch_time + args.capture_seconds + 2.0 - time.time()
        if remaining_capture > 0:
            time.sleep(remaining_capture)
        evidence, cdp_error = capture_page_evidence(debug_port, "gamepad-test.html", out_dir)
        if cdp_error:
            summary["browser_cdp_error"] = cdp_error
        if evidence:
            summary["browser_evidence_path"] = str(out_dir / "gamepad_tester_evidence_cdp.json")
        else:
            evidence = None

        download_evidence, evidence_path = wait_for_evidence(
            download_dir,
            started_at,
            timeout=8.0,
        )
        if evidence is None and download_evidence is not None:
            evidence = download_evidence
        if evidence_path and "browser_evidence_path" not in summary:
            copied_path = out_dir / "gamepad_tester_evidence.json"
            copied_path.write_text(evidence_path.read_text(encoding="utf-8"), encoding="utf-8")
            summary["browser_evidence_path"] = str(copied_path)
        browser_pass, browser_reasons = browser_evidence_passes(evidence, args.expected_profile)
        summary["browser_evidence"] = summarize_browser_evidence(evidence)
        summary["browser_pass"] = browser_pass
        summary["browser_reasons"] = browser_reasons
        summary["xinput_pass"] = summary.get("baseline_xinput_connected") and len(sequence["moved_scenarios"]) >= 8
        summary["pass"] = bool(summary["xinput_pass"] and browser_pass)
        summary["finished_at"] = iso_now()
        return 0 if summary["pass"] else 2
    finally:
        write_json(out_dir / "serial_transcript.json", transcript)
        write_json(out_dir / "summary.json", summary)
        if browser_proc is not None and browser_proc.poll() is None:
            browser_proc.terminate()
            try:
                browser_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                browser_proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
