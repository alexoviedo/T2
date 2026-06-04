#!/usr/bin/env python3
"""Run Windows BLE identity advertisement/pairing witness flows."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import subprocess
import sys
import time
from typing import Any


DEFAULT_OUT_DIR = pathlib.Path("target/windows-ble-identity")
EXPECTED_TOPOLOGY = ("2109:2813", "044f:b10a", "044f:b687")
PERSONA_COMMANDS = {
    "generic": ("START_BLE_GENERIC_GAMEPAD", "USB2BLE Gamepad"),
    "generic_unsigned_6axis": (
        "START_BLE_GENERIC_GAMEPAD_VARIANT generic_unsigned_6axis",
        "USB2BLE Gamepad U6",
    ),
    "xbox": ("START_BLE_XBOX_CONTROLLER", "Xbox Wireless Controller"),
}
PREFIXES = (
    "INFO:",
    "STATUS:",
    "USB_STATUS:",
    "USB_DEVICES:",
    "BLE_ACTION:",
    "BLE_ADVERTISING_INFO:",
    "BLE_ADVERTISING_EVENTS_JSON:",
    "BLE_COMPAT_VARIANTS_JSON:",
    "BLE_COMPAT_PROFILE_JSON:",
    "BLE_IDENTITY_INFO_JSON:",
    "BLE_IDENTITY_STRATEGIES_JSON:",
    "BLE_IDENTITY_STRATEGY_JSON:",
    "ERROR:",
)


def utc_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_command(command: list[str], timeout: float = 60.0) -> dict[str, Any]:
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
        return {
            "command": command,
            "returncode": None,
            "output": exc.stdout or "",
            "ok": False,
            "timeout": True,
        }
    return {
        "command": command,
        "returncode": result.returncode,
        "output": result.stdout,
        "ok": result.returncode == 0,
    }


def powershell_text(script: str, timeout: float = 45.0) -> dict[str, Any]:
    return run_command(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ],
        timeout=timeout,
    )


def discover_ports() -> list[str]:
    result = powershell_text("[System.IO.Ports.SerialPort]::GetPortNames()")
    ports = []
    for line in str(result.get("output", "")).splitlines():
        value = line.strip()
        if re.fullmatch(r"COM\d+", value, re.IGNORECASE):
            ports.append(value.upper())
    return sorted(set(ports), key=lambda item: int(item[3:]))


def serial_command(port: str, commands: list[str], timeout: float = 5.0) -> dict[str, Any]:
    return run_command(
        [
            sys.executable,
            "tools/serial_command.py",
            "--port",
            port,
            "--timeout",
            str(timeout),
            *commands,
        ],
        timeout=max(20.0, timeout * (len(commands) + 2)),
    )


def response_lines(output: str) -> list[str]:
    return [line for line in output.splitlines() if line.startswith(PREFIXES)]


def select_port(explicit_port: str | None) -> tuple[str, dict[str, Any]]:
    if explicit_port:
        return explicit_port, {"explicit_port": explicit_port}
    discovery: dict[str, Any] = {
        "ports": discover_ports(),
        "attempts": [],
        "pnp_ports": powershell_text(
            "Get-CimInstance Win32_SerialPort | Select-Object DeviceID,Name,Description,PNPDeviceID,Manufacturer | Format-List *"
        ),
    }
    for port in discovery["ports"]:
        attempt = serial_command(port, ["GET_INFO", "GET_STATUS"], timeout=3.0)
        discovery["attempts"].append({"port": port, **attempt})
        if "INFO:" in str(attempt.get("output", "")):
            return port, discovery
    raise RuntimeError("no USB2BLE serial control-plane port responded")


def run_watcher(out_dir: pathlib.Path, run_name: str, duration: float) -> dict[str, Any]:
    result = run_command(
        [
            sys.executable,
            "tools/windows_ble_advertising_watcher.py",
            "--out-dir",
            str(out_dir),
            "--run-name",
            run_name,
            "--duration",
            str(duration),
        ],
        timeout=duration + 30,
    )
    try:
        parsed = json.loads(str(result.get("output", "")).strip())
    except json.JSONDecodeError:
        parsed = {}
    return {"process": result, "summary": parsed}


def collect_host_inventory(out_dir: pathlib.Path, label: str) -> dict[str, Any]:
    scripts = {
        "bluetooth": "Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue | Format-List *",
        "hidclass": "Get-PnpDevice -Class HIDClass -ErrorAction SilentlyContinue | Format-List *",
        "named": "Get-PnpDevice -PresentOnly | Where-Object { $_.FriendlyName -match 'USB2BLE|Xbox|Gamepad|Controller|Bluetooth|HID' } | Format-List *",
    }
    results: dict[str, Any] = {}
    for name, script in scripts.items():
        result = powershell_text(script)
        results[name] = result
        (out_dir / f"{label}_{name}.txt").write_text(str(result.get("output", "")), encoding="utf-8")
    return results


def safe_cache_inventory(out_dir: pathlib.Path, label: str) -> dict[str, Any]:
    result = run_command(
        [
            sys.executable,
            "tools/windows_ble_cache_witness.py",
            "--dry-run",
            "--out-dir",
            str(out_dir / f"{label}_cache"),
        ],
        timeout=90,
    )
    return result


def topology_ok(text: str) -> bool:
    lower = text.lower()
    return all(
        item in lower or item.replace(":", ",pid=") in lower or item.replace(":", ",pid&") in lower
        for item in EXPECTED_TOPOLOGY
    )


def poll_baseline(port: str, total_seconds: float = 30.0) -> dict[str, Any]:
    deadline = time.monotonic() + total_seconds
    attempts: list[dict[str, Any]] = []
    last: dict[str, Any] | None = None
    commands = [
        "GET_INFO",
        "GET_STATUS",
        "GET_USB_STATUS",
        "LIST_USB_DEVICES",
        "LIST_BLE_COMPAT_VARIANTS",
        "GET_BLE_IDENTITY_INFO",
    ]
    while time.monotonic() < deadline:
        last = serial_command(port, commands, timeout=5.0)
        attempts.append(last)
        if topology_ok(str(last.get("output", ""))):
            return {"ok": True, "attempts": attempts, "last": last}
        time.sleep(2.0)
    return {"ok": False, "attempts": attempts, "last": last or {}}


def run_persona(
    port: str,
    root: pathlib.Path,
    strategy: str,
    persona: str,
    duration: float,
    pair: bool,
    manual_pair_ok: bool,
) -> dict[str, Any]:
    command, expected_name = PERSONA_COMMANDS[persona]
    run_dir = root / strategy / persona
    run_dir.mkdir(parents=True, exist_ok=True)
    transcript: list[dict[str, Any]] = []

    for commands in (
        ["FORGET_BLE_BONDS"],
        ["SET_BLE_IDENTITY_STRATEGY " + strategy],
        [command],
        ["GET_BLE_IDENTITY_INFO", "GET_BLE_ADVERTISING_INFO", "GET_BLE_ADVERTISING_EVENTS", "GET_BLE_COMPAT_PROFILE"],
    ):
        result = serial_command(port, commands, timeout=5.0)
        transcript.append({"commands": commands, **result})
        time.sleep(1.0)

    watcher = run_watcher(run_dir, "windows_ble_scan", duration)
    cache_before = safe_cache_inventory(run_dir, "before_pair") if pair else {"skipped": True}
    host_before = collect_host_inventory(run_dir, "before_pair") if pair else {}
    manual_prompt = None
    if pair and manual_pair_ok:
        manual_prompt = (
            f'Open Windows Bluetooth settings. Pair/connect "{expected_name}", then press Enter.'
        )
        print(manual_prompt, flush=True)
        input()
    host_after = collect_host_inventory(run_dir, "after_pair") if pair else {}
    gamepad_probe = (
        run_command([sys.executable, "tools/windows_gamepad_probe.py"], timeout=90)
        if pair
        else {"skipped": True}
    )
    (run_dir / "gamepad_probe.txt").write_text(str(gamepad_probe.get("output", "")), encoding="utf-8")

    summary = {
        "strategy": strategy,
        "persona": persona,
        "expected_name": expected_name,
        "serial_transcript": transcript,
        "watcher": watcher,
        "cache_before": cache_before,
        "host_before_collected": bool(host_before),
        "host_after_collected": bool(host_after),
        "pair_requested": pair,
        "manual_prompt": manual_prompt,
        "gamepad_probe_returncode": gamepad_probe.get("returncode"),
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    (run_dir / "serial_transcript.txt").write_text(
        "\n\n".join(str(item.get("output", "")) for item in transcript),
        encoding="utf-8",
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default=None)
    parser.add_argument(
        "--strategy",
        choices=("legacy_public", "persona_static_random_experimental"),
        default="legacy_public",
    )
    parser.add_argument("--personas", default="generic,generic_unsigned_6axis,xbox")
    parser.add_argument("--no-pair", action="store_true")
    parser.add_argument("--pair", action="store_true")
    parser.add_argument("--manual-pair-ok", action="store_true")
    parser.add_argument("--duration", type=float, default=15.0)
    parser.add_argument("--out-dir", type=pathlib.Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.out_dir / f"windows_ble_identity_witness_{utc_stamp()}"
    root.mkdir(parents=True, exist_ok=True)
    pair = args.pair and not args.no_pair
    port, discovery = select_port(args.port)
    (root / "serial_discovery.json").write_text(json.dumps(discovery, indent=2, sort_keys=True), encoding="utf-8")
    baseline_poll = poll_baseline(port)
    baseline = baseline_poll["last"]
    (root / "target_baseline.txt").write_text(str(baseline.get("output", "")), encoding="utf-8")
    (root / "target_baseline_poll.json").write_text(
        json.dumps(baseline_poll, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    personas = [item.strip() for item in args.personas.split(",") if item.strip()]
    summaries = []
    if not baseline_poll["ok"]:
        summary = {
            "selected_port": port,
            "topology_ok": False,
            "error": "expected USB topology was not present; persona tests were skipped",
        }
        (root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps({"run_dir": str(root), **summary}, indent=2, sort_keys=True))
        return 1
    for persona in personas:
        if persona not in PERSONA_COMMANDS:
            summaries.append({"persona": persona, "skipped": True, "reason": "unknown persona"})
            continue
        summaries.append(run_persona(port, root, args.strategy, persona, args.duration, pair, args.manual_pair_ok))
    final = {
        "selected_port": port,
        "topology_ok": True,
        "strategy": args.strategy,
        "pair": pair,
        "personas": personas,
        "summaries": summaries,
    }
    (root / "summary.json").write_text(json.dumps(final, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"run_dir": str(root), **final}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
