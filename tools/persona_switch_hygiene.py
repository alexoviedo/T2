#!/usr/bin/env python3
"""Run virtual bridge witnesses as a persona-switching hygiene check."""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
from typing import Any

from asap_demo_rehearsal import utc_stamp


DEFAULT_PORT = "/dev/cu.usbmodem5B5E0200881"


def run_command(command: list[str]) -> tuple[int, str]:
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    return result.returncode, result.stdout


def latest_run_dir(base: pathlib.Path, persona: str) -> pathlib.Path | None:
    matches = sorted(base.glob(f"{persona}_virtual_bridge_*"), key=lambda path: path.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def load_summary(run_dir: pathlib.Path | None) -> dict[str, Any] | None:
    if run_dir is None:
        return None
    summary = run_dir / "summary.json"
    if not summary.exists():
        return None
    try:
        value = json.loads(summary.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def persona_result(summary: dict[str, Any] | None) -> dict[str, Any]:
    if summary is None:
        return {
            "run_dir": None,
            "passed": False,
            "browser_expected_gamepad_seen": False,
            "browser_stale_capture_count": None,
            "published_delta": None,
            "failed_expected_scenarios": ["missing_summary"],
        }
    browser = summary.get("browser_gamepad")
    browser_summary = None
    if isinstance(browser, dict):
        browser_summary = {
            "id": browser.get("id"),
            "mapping": browser.get("mapping"),
            "axes_count": len(browser.get("axes", [])),
            "buttons_count": len(browser.get("buttons", [])),
            "session_id": browser.get("session_id"),
            "session_label": browser.get("session_label"),
        }
    return {
        "run_dir": summary.get("run_dir"),
        "passed": bool(summary.get("virtual_bridge_witness_passed")),
        "target_ble_connected": bool(summary.get("target_ble_connected")),
        "browser_gamepad_seen": bool(summary.get("browser_gamepad_seen")),
        "browser_expected_gamepad_seen": bool(summary.get("browser_expected_gamepad_seen")),
        "browser_stale_capture_count": summary.get("browser_stale_capture_count"),
        "browser_capture_count": summary.get("browser_capture_count"),
        "published_delta": summary.get("published_delta"),
        "matched_expected_count": summary.get("matched_expected_count"),
        "expected_count": summary.get("expected_count"),
        "failed_expected_scenarios": summary.get("failed_expected_scenarios", []),
        "human_prompted": bool(summary.get("human_prompted")),
        "browser_gamepad": browser_summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--sequence", default="xbox,generic")
    parser.add_argument("--witness-port-start", type=int, default=8810)
    parser.add_argument("--duration-per-scenario", type=float, default=0.75)
    parser.add_argument("--out-dir", type=pathlib.Path, default=pathlib.Path("target/persona-switching-hygiene"))
    parser.add_argument("--witness-out-dir", type=pathlib.Path, default=pathlib.Path("target/virtual-input-bridge-witness"))
    parser.add_argument("--no-human", action="store_true")
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()

    personas = [part.strip() for part in args.sequence.split(",") if part.strip()]
    unknown = [persona for persona in personas if persona not in {"generic", "xbox"}]
    if unknown:
        raise SystemExit(f"Unknown persona(s): {', '.join(unknown)}")

    stamp = utc_stamp()
    run_dir = args.out_dir / f"persona_switch_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    command_outputs: list[dict[str, Any]] = []
    for index, persona in enumerate(personas):
        witness_port = args.witness_port_start + index
        command = [
            sys.executable,
            "tools/virtual_input_bridge_witness.py",
            "--port",
            args.port,
            "--persona",
            persona,
            "--scenarios",
            "all",
            "--duration-per-scenario",
            str(args.duration_per_scenario),
            "--witness-port",
            str(witness_port),
            "--auto-arm",
            "--assume-bluetooth-connected",
            "--no-physical-input",
        ]
        if args.no_human:
            command.append("--no-human")
        if args.no_open:
            command.append("--no-open")

        before = latest_run_dir(args.witness_out_dir, persona)
        code, output = run_command(command)
        after = latest_run_dir(args.witness_out_dir, persona)
        if after == before:
            after = None
        summary = load_summary(after)
        result = persona_result(summary)
        result["persona"] = persona
        result["returncode"] = code
        result["witness_port"] = witness_port
        results.append(result)
        command_outputs.append(
            {
                "persona": persona,
                "command": command,
                "returncode": code,
                "output": output,
                "run_dir": str(after) if after else None,
            }
        )

    pass_count = sum(1 for result in results if result["passed"])
    stale_count = sum(int(result.get("browser_stale_capture_count") or 0) for result in results)
    summary = {
        "captured_at": stamp,
        "sequence": personas,
        "run_dir": str(run_dir),
        "pass_count": pass_count,
        "fail_count": len(results) - pass_count,
        "stale_capture_count": stale_count,
        "persona_switching_hygiene_passed": pass_count == len(results) and stale_count == 0,
        "results": results,
    }

    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (run_dir / "command_outputs.json").write_text(
        json.dumps(command_outputs, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    notes = [
        "# Persona Switching Hygiene Notes",
        "",
        f"- Sequence: `{','.join(personas)}`",
        f"- Pass count: `{pass_count}/{len(results)}`",
        f"- Stale captures: `{stale_count}`",
        "",
        "This workflow uses diagnostic virtual normalized-input replay and browser",
        "slot hygiene checks. It does not prove physical USB movement.",
    ]
    for result in results:
        notes.extend(
            [
                "",
                f"## {result['persona']}",
                "",
                f"- Passed: `{result['passed']}`",
                f"- Run dir: `{result.get('run_dir')}`",
                f"- Browser expected gamepad seen: `{result.get('browser_expected_gamepad_seen')}`",
                f"- Stale capture count: `{result.get('browser_stale_capture_count')}`",
                f"- Failed scenarios: `{result.get('failed_expected_scenarios')}`",
            ]
        )
    (run_dir / "operator_notes.md").write_text("\n".join(notes) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["persona_switching_hygiene_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
