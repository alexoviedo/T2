#!/usr/bin/env python3
"""Run a refined Generic Flight Pack live-bridge soak with browser sampling."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys
import time
from typing import Any

from asap_demo_rehearsal import (
    CommandRecord,
    SerialPort,
    parse_int_field,
    parse_semicolon_fields,
    print_record,
    response_with_prefix,
    run_commands,
    utc_stamp,
)
from generic_axis_exposure_witness import (
    STEPS,
    axis_stats,
    capture_window,
    load_samples,
    observed_devices,
    open_browser,
    select_port,
    start_server,
    wait_for_samples,
)


DEFAULT_OUT_DIR = "target/refined-generic-live-bridge-soak"
DEFAULT_BROWSER_PORT = 8768
EXPECTED_STEPS = (
    "throttle_min",
    "throttle_max",
    "rudder_left",
    "rudder_right",
    "left_toe_released",
    "left_toe_pressed",
    "right_toe_released",
    "right_toe_pressed",
)


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


def bridge_status_from_record(record: CommandRecord) -> dict[str, str]:
    line = response_with_prefix([record], "BRIDGE_STATUS:")
    return parse_semicolon_fields(line)


def status_fields_from_record(record: CommandRecord) -> dict[str, str]:
    line = response_with_prefix([record], "STATUS:")
    return parse_semicolon_fields(line)


def config_fields_from_records(records: list[CommandRecord]) -> dict[str, str]:
    return parse_semicolon_fields(response_with_prefix(records, "CONFIG_STATUS:"))


def field_delta(statuses: list[dict[str, str]], field: str) -> tuple[int | None, int | None, int | None]:
    values = [value for status in statuses for value in [parse_int_field(status, field)] if value is not None]
    if len(values) < 2:
        return (values[0], values[-1], 0) if values else (None, None, None)
    return values[0], values[-1], values[-1] - values[0]


def bool_field(status: dict[str, str], field: str) -> bool | None:
    value = status.get(field)
    if value is None:
        return None
    return value.lower() == "true"


def browser_axis_ranges(samples: list[dict[str, Any]], indices: tuple[int, ...]) -> dict[str, dict[str, Any]]:
    ranges: dict[str, dict[str, Any]] = {}
    for index in indices:
        values = [
            float(sample["axes"][index])
            for sample in samples
            if isinstance(sample.get("axes"), list) and len(sample["axes"]) > index
        ]
        if not values:
            ranges[f"A{index}"] = {"samples": 0, "min": None, "max": None, "delta": None}
            continue
        ranges[f"A{index}"] = {
            "samples": len(values),
            "min": min(values),
            "max": max(values),
            "delta": max(values) - min(values),
            "first": values[0],
            "last": values[-1],
        }
    return ranges


def browser_connected(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        sample
        for sample in samples
        if sample.get("connected") is True and isinstance(sample.get("axes"), list)
    ]


def chrome_version() -> str | None:
    if sys.platform != "darwin":
        return None
    import subprocess

    result = subprocess.run(
        ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "--version"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return None


def run_marker_windows(
    label: str,
    serial: SerialPort,
    capture_file: pathlib.Path,
    timeout: float,
    window_seconds: float,
    alerts: bool,
    assume_ready: bool,
) -> tuple[list[dict[str, Any]], list[CommandRecord]]:
    selected = [step for step in STEPS if step.key in EXPECTED_STEPS]
    summaries: list[dict[str, Any]] = []
    records: list[CommandRecord] = []
    print()
    print(f"Starting {label} sanity movement windows.")
    for step in selected:
        summary, step_records = capture_window(
            serial,
            step,
            capture_file,
            timeout,
            window_seconds,
            alerts,
            assume_ready,
        )
        summary["phase"] = label
        summaries.append(summary)
        records.extend(step_records)
        print(
            json.dumps(
                {
                    "phase": label,
                    "step": step.key,
                    "changed_browser_axis_indices": summary["changed_browser_axis_indices"],
                    "decoded_axes": (summary.get("encoded_report") or {}).get("axes"),
                },
                sort_keys=True,
            )
        )
    return summaries, records


def poll_soak(
    serial: SerialPort,
    duration_seconds: float,
    sample_interval_seconds: float,
    timeout: float,
) -> tuple[list[dict[str, Any]], list[CommandRecord]]:
    samples: list[dict[str, Any]] = []
    records: list[CommandRecord] = []
    start = time.monotonic()
    next_sample = start
    sample_index = 0
    while True:
        now = time.monotonic()
        elapsed = now - start
        if elapsed > duration_seconds and sample_index > 0:
            break
        if now < next_sample:
            time.sleep(min(0.1, next_sample - now))
            continue

        status_record = CommandRecord("GET_STATUS", serial.command_response("GET_STATUS", timeout))
        bridge_record = CommandRecord(
            "GET_BRIDGE_STATUS",
            serial.command_response("GET_BRIDGE_STATUS", timeout),
        )
        report_record = CommandRecord(
            "GET_GENERIC_GAMEPAD_REPORT",
            serial.command_response("GET_GENERIC_GAMEPAD_REPORT", timeout),
        )
        for record in (status_record, bridge_record, report_record):
            print_record(record)
            records.append(record)
        samples.append(
            {
                "sample": sample_index,
                "elapsed_seconds": round(elapsed, 3),
                "status": status_fields_from_record(status_record),
                "bridge_status": bridge_status_from_record(bridge_record),
                "status_record": status_record.to_json(),
                "bridge_record": bridge_record.to_json(),
                "report_record": report_record.to_json(),
            }
        )
        sample_index += 1
        next_sample += sample_interval_seconds
    return samples, records


def build_summary(
    run_dir: pathlib.Path,
    port: str,
    stamp: str,
    duration_seconds: float,
    interval_seconds: float,
    all_records: list[CommandRecord],
    soak_samples: list[dict[str, Any]],
    movement_summaries: list[dict[str, Any]],
    browser_samples: list[dict[str, Any]],
    errors: list[str],
) -> dict[str, Any]:
    bridge_statuses = [
        sample["bridge_status"]
        for sample in soak_samples
        if isinstance(sample.get("bridge_status"), dict)
    ]
    status_samples = [
        sample["status"] for sample in soak_samples if isinstance(sample.get("status"), dict)
    ]
    connected_browser = browser_connected(browser_samples)
    _changed, browser_stats, browser_axes_length = axis_stats(browser_samples)
    last_errors = [
        status.get("last_error", "none")
        for status in bridge_statuses
        if status.get("last_error", "none") != "none"
    ]

    published_start, published_end, published_delta = field_delta(bridge_statuses, "published")
    duplicate_start, duplicate_end, duplicate_delta = field_delta(bridge_statuses, "skipped_duplicate")
    rate_start, rate_end, rate_delta = field_delta(bridge_statuses, "skipped_rate")
    not_connected_start, not_connected_end, not_connected_delta = field_delta(
        bridge_statuses, "skipped_not_connected"
    )
    not_ready_start, not_ready_end, not_ready_delta = field_delta(bridge_statuses, "skipped_not_ready")

    bridge_enabled_start = bool_field(bridge_statuses[0], "enabled") if bridge_statuses else None
    bridge_enabled_end = bool_field(bridge_statuses[-1], "enabled") if bridge_statuses else None
    browser_connected_start = bool(connected_browser and connected_browser[0].get("connected") is True)
    browser_connected_end = bool(connected_browser and connected_browser[-1].get("connected") is True)
    expected_axis_ranges = browser_axis_ranges(browser_samples, (2, 3, 4, 5))

    if not bridge_statuses:
        errors.append("no bridge status samples captured")
    if bridge_enabled_start is not True or bridge_enabled_end is not True:
        errors.append("bridge was not enabled at soak start/end")
    if any(status.get("ble") != "Connected" for status in status_samples):
        errors.append("one or more serial status samples were not BLE Connected")
    if any(status.get("persona") != "generic_gamepad" for status in status_samples):
        errors.append("one or more serial status samples did not report generic_gamepad")
    if not_connected_delta not in (0, None):
        errors.append("skipped_not_connected increased during soak")
    if not_ready_delta not in (0, None):
        errors.append("skipped_not_ready increased during soak")
    if last_errors:
        errors.append("bridge last_error was not none")
    if published_delta is None or published_delta <= 0:
        errors.append("bridge published counter did not increase")
    if not browser_connected_start or not browser_connected_end:
        errors.append("browser Gamepad samples were not connected at start/end")
    if len(connected_browser) < max(20, int(duration_seconds * 2)):
        errors.append("browser sample count was lower than expected for continuous sampling")
    if browser_axes_length is None or browser_axes_length < 6:
        errors.append("browser axes length did not expose at least six axes")

    movement_checks = {}
    for target, expected_index in {"z": 2, "rx": 3, "ry": 4, "rz": 5}.items():
        windows = [
            window
            for window in movement_summaries
            if window.get("generic_target") == target
            and expected_index in (window.get("changed_browser_axis_indices") or [])
        ]
        movement_checks[target] = bool(windows)
        if not windows:
            errors.append(f"no sanity movement window changed expected browser axis for {target}")

    return {
        "run_dir": str(run_dir),
        "captured_at": stamp,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "port": port,
        "browser": chrome_version(),
        "duration_seconds": duration_seconds,
        "sample_interval_seconds": interval_seconds,
        "sample_count_serial": len(soak_samples),
        "sample_count_browser": len(browser_samples),
        "sample_count_browser_connected": len(connected_browser),
        "bridge_enabled_start": bridge_enabled_start,
        "bridge_enabled_end": bridge_enabled_end,
        "published_start": published_start,
        "published_end": published_end,
        "published_delta": published_delta,
        "skipped_duplicate_start": duplicate_start,
        "skipped_duplicate_end": duplicate_end,
        "skipped_duplicate_delta": duplicate_delta,
        "skipped_rate_start": rate_start,
        "skipped_rate_end": rate_end,
        "skipped_rate_delta": rate_delta,
        "skipped_not_connected_start": not_connected_start,
        "skipped_not_connected_end": not_connected_end,
        "skipped_not_connected_delta": not_connected_delta,
        "skipped_not_ready_start": not_ready_start,
        "skipped_not_ready_end": not_ready_end,
        "skipped_not_ready_delta": not_ready_delta,
        "last_error_values": sorted(set(status.get("last_error", "none") for status in bridge_statuses)),
        "browser_connected_start": browser_connected_start,
        "browser_connected_end": browser_connected_end,
        "browser_axes_length": browser_axes_length,
        "browser_axis_stats": browser_stats,
        "observed_browser_axis_ranges": expected_axis_ranges,
        "movement_checks": movement_checks,
        "observed_devices": observed_devices(all_records),
        "config_status": config_fields_from_records(all_records),
        "errors": sorted(set(errors)),
        "refined_generic_soak_passed": not errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="auto", help="Serial port or 'auto'.")
    parser.add_argument("--timeout", type=float, default=4.0)
    parser.add_argument("--duration-seconds", type=float, default=300.0)
    parser.add_argument("--sample-interval-seconds", type=float, default=5.0)
    parser.add_argument("--movement-window-seconds", type=float, default=2.0)
    parser.add_argument("--browser-port", type=int, default=DEFAULT_BROWSER_PORT)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--assume-ready", action="store_true")
    parser.add_argument("--quiet-alerts", action="store_true")
    parser.add_argument("--skip-browser-open", action="store_true")
    parser.add_argument("--skip-movement-markers", action="store_true")
    args = parser.parse_args()

    stamp = utc_stamp()
    run_dir = pathlib.Path(args.out_dir) / f"refined_generic_soak_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    capture_file = run_dir / "browser_captures.jsonl"
    capture_file.touch()

    port = select_port(args.port, args.timeout)
    server, _thread = start_server(capture_file, args.browser_port)
    if not args.skip_browser_open:
        open_browser(args.browser_port)
    print(f"Browser witness URL: http://127.0.0.1:{args.browser_port}/")
    print(f"Saving artifacts: {run_dir}")

    errors: list[str] = []
    all_records: list[CommandRecord] = []
    movement_summaries: list[dict[str, Any]] = []
    soak_samples: list[dict[str, Any]] = []
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
                "START_CONFIGURED",
                "GET_STATUS",
                "GET_BRIDGE_STATUS",
            ],
            args.timeout,
        )
        all_records.extend(preflight)

        devices = observed_devices(all_records)
        for name, present in devices.items():
            if not present:
                errors.append(f"missing expected USB device: {name}")
        config = config_fields_from_records(all_records)
        if config.get("persona") != "generic_gamepad":
            errors.append("loaded config persona is not generic_gamepad")
        if config.get("profile") != "custom_runtime":
            errors.append("loaded config profile is not custom_runtime")
        if config.get("mappings") != "6":
            errors.append("loaded config does not report six mappings")

        browser_samples = wait_for_samples(capture_file, 5, 8.0)
        if len(browser_samples) < 5:
            print()
            print("Click Arm in the browser Gamepad witness page and make sure USB2BLE Gamepad is connected in Bluetooth.")
            if not args.assume_ready:
                input("Press Enter when the browser is armed and sampling...")
            browser_samples = wait_for_samples(capture_file, 5, 15.0)
        if len(browser_samples) < 5:
            errors.append("browser witness did not produce continuous samples")

        if not errors and not args.skip_movement_markers:
            summaries, records = run_marker_windows(
                "pre_soak",
                serial,
                capture_file,
                args.timeout,
                args.movement_window_seconds,
                not args.quiet_alerts,
                args.assume_ready,
            )
            movement_summaries.extend(summaries)
            all_records.extend(records)

        print()
        print(
            f"Starting {args.duration_seconds:.0f}s soak; polling serial every {args.sample_interval_seconds:.1f}s."
        )
        soak_samples, soak_records = poll_soak(
            serial,
            args.duration_seconds,
            args.sample_interval_seconds,
            args.timeout,
        )
        all_records.extend(soak_records)

        if not errors and not args.skip_movement_markers:
            summaries, records = run_marker_windows(
                "post_soak",
                serial,
                capture_file,
                args.timeout,
                args.movement_window_seconds,
                not args.quiet_alerts,
                args.assume_ready,
            )
            movement_summaries.extend(summaries)
            all_records.extend(records)

        final_records = run_commands(serial, ["GET_BRIDGE_STATUS", "GET_STATUS"], args.timeout)
        all_records.extend(final_records)
    finally:
        serial.close()
        server.shutdown()
        server.server_close()

    browser_samples = load_samples(capture_file)
    summary = build_summary(
        run_dir,
        port,
        stamp,
        args.duration_seconds,
        args.sample_interval_seconds,
        all_records,
        soak_samples,
        movement_summaries,
        browser_samples,
        errors,
    )
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_jsonl(run_dir / "bridge_status_samples.jsonl", soak_samples)
    (run_dir / "movement_summaries.json").write_text(
        json.dumps(movement_summaries, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_transcript(run_dir / "serial_transcript.txt", all_records)
    (run_dir / "operator_notes.md").write_text(
        "# Refined Generic Live Bridge Soak Notes\n\n"
        "- This is browser Gamepad API / BLE HID host-visible evidence, not game/app compatibility.\n"
        "- The browser page posts continuous Gamepad samples while armed.\n"
        "- The soak uses the persisted refined Generic Flight Pack runtime config and `START_CONFIGURED`.\n",
        encoding="utf-8",
    )
    print(f"Saved soak artifacts: {run_dir}")
    print(json.dumps({k: summary[k] for k in ("refined_generic_soak_passed", "errors")}, indent=2))
    return 0 if summary["refined_generic_soak_passed"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        raise SystemExit(130)
