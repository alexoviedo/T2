#!/usr/bin/env python3
"""Summarize Xbox host-visible standard-layout witness artifacts."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from asap_demo_rehearsal import utc_stamp
import xbox_host_visible_witness as witness


def latest_run(root: pathlib.Path) -> pathlib.Path:
    runs = sorted(root.glob("xbox_host_visible_*"))
    if not runs:
        raise FileNotFoundError(f"no xbox_host_visible_* runs under {root}")
    return runs[-1]


def load_results(run_dir: pathlib.Path) -> tuple[dict, list[dict]]:
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    results = json.loads((run_dir / "scenario_results.json").read_text(encoding="utf-8"))
    if not isinstance(summary, dict) or not isinstance(results, list):
        raise ValueError(f"invalid witness artifact shape in {run_dir}")
    return summary, results


def likely_cause(diagnosis: dict) -> str:
    unexpected_buttons = diagnosis.get("unexpected_button_indices") or []
    missing = diagnosis.get("missing_expected_indices") or []
    if unexpected_buttons and missing:
        return (
            "Browser standard mapping is present, but logical Xbox button labels do not all "
            "line up with Chrome's observed standard button indices. This points to encoder "
            "logical button ordering or host remapping expectations, not to stick/trigger encoding."
        )
    if missing:
        return "Some expected browser standard controls did not move; inspect descriptor/report encoding."
    return "No standard-layout mismatch detected in the supplied artifact."


def write_outputs(run_dir: pathlib.Path, out_dir: pathlib.Path) -> dict:
    summary, results = load_results(run_dir)
    diagnosis = witness.layout_diagnosis(results)
    browser = summary.get("browser_gamepad", {})
    output = {
        "source_run": str(run_dir),
        "browser_id": browser.get("id"),
        "browser_mapping": browser.get("mapping"),
        "browser_axes_count": browser.get("axes_count"),
        "browser_buttons_count": browser.get("buttons_count"),
        "standard_layout": summary.get("standard_layout", {}),
        "likely_mismatch_cause": likely_cause(diagnosis),
        "diagnosis": diagnosis,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    witness.write_layout_diagnosis(out_dir, diagnosis)
    notes = [
        "# Xbox Standard Layout Diagnosis",
        "",
        f"- Source run: `{run_dir}`",
        f"- Browser ID: `{browser.get('id')}`",
        f"- Browser mapping: `{browser.get('mapping')}`",
        f"- Likely mismatch cause: {output['likely_mismatch_cause']}",
        "",
        "See `layout_diagnosis.md` and `layout_diagnosis.json` for the scenario table.",
    ]
    (out_dir / "operator_notes.md").write_text("\n".join(notes) + "\n", encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifact-dir",
        type=pathlib.Path,
        default=None,
        help="Existing xbox_host_visible_* run to summarize. Defaults to latest.",
    )
    parser.add_argument(
        "--witness-root",
        type=pathlib.Path,
        default=pathlib.Path("target/xbox-host-visible-witness"),
    )
    parser.add_argument(
        "--out-dir",
        type=pathlib.Path,
        default=pathlib.Path("target/xbox-standard-layout-diagnosis"),
    )
    args = parser.parse_args()

    source = args.artifact_dir or latest_run(args.witness_root)
    run_dir = args.out_dir / f"xbox_standard_layout_{utc_stamp()}"
    output = write_outputs(source, run_dir)
    print(json.dumps({"run_dir": str(run_dir), **output}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        raise SystemExit(130)
