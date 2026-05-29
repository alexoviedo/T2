#!/usr/bin/env python3
"""Generate source-defined BLE compatibility profile snapshots."""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

from asap_demo_rehearsal import utc_stamp
from check_ble_hid_profile import builtin_profile


DEFAULT_VARIANTS = "generic_default,generic_hogp_strict,ios_keyboard_icade_fallback,xbox_compatibility"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variants", default=DEFAULT_VARIANTS)
    parser.add_argument("--out-dir", default="target/ble-compat")
    args = parser.parse_args()

    stamp = utc_stamp()
    run_dir = pathlib.Path(args.out_dir) / f"profile_snapshots_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    variants = [variant.strip() for variant in args.variants.split(",") if variant.strip()]
    snapshot_paths: list[str] = []
    errors: list[str] = []

    for variant in variants:
        try:
            profile = builtin_profile(variant)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        path = run_dir / f"{variant}.json"
        path.write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        snapshot_paths.append(str(path))

    check_json = run_dir / "profile_check.json"
    check_cmd = [
        sys.executable,
        "tools/check_ble_hid_profile.py",
        *sum((["--profile-json", path] for path in snapshot_paths), []),
        "--out-json",
        str(check_json),
        "--quiet",
    ]
    check_result = subprocess.run(
        check_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    ) if snapshot_paths else None
    if check_result and check_result.returncode != 0:
        errors.append("profile checker reported structural failures")

    summary = {
        "run_dir": str(run_dir),
        "variants": variants,
        "snapshot_paths": snapshot_paths,
        "profile_check_json": str(check_json) if check_json.exists() else None,
        "profile_check_returncode": None if check_result is None else check_result.returncode,
        "errors": errors,
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
