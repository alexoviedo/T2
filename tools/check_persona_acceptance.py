#!/usr/bin/env python3
"""Check evidence readiness for USB2BLE BLE personas without hardware."""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
from dataclasses import dataclass
from typing import Any


ROOT = pathlib.Path(".")


@dataclass(frozen=True)
class Check:
    layer: str
    item: str
    status: str
    note: str

    def to_json(self) -> dict[str, str]:
        return {
            "layer": self.layer,
            "item": self.item,
            "status": self.status,
            "note": self.note,
        }


PERSONAS: dict[str, dict[str, Any]] = {
    "generic_gamepad": {
        "descriptor_checker": "tools/check_ble_hid_profile.py",
        "target_evidence": [
            "docs/milestone-evidence/BLE_HID_MAC_PAIRING_INPUT_WITNESS_2026-04-30.md",
            "docs/milestone-evidence/REFINED_GENERIC_AXIS_EXPOSURE_WITNESS_2026-05-28.md",
            "docs/milestone-evidence/REFINED_GENERIC_LIVE_BRIDGE_SOAK_WITNESS_2026-05-28.md",
        ],
        "real_usb_input_evidence": [
            "docs/milestone-evidence/REFINED_GENERIC_AXIS_EXPOSURE_WITNESS_2026-05-28.md",
            "docs/milestone-evidence/REFINED_GENERIC_LIVE_BRIDGE_SOAK_WITNESS_2026-05-28.md",
        ],
        "virtual_input_evidence": [],
        "deterministic_persona_report_evidence": [],
        "host_evidence": [
            "docs/milestone-evidence/REFINED_GENERIC_AXIS_EXPOSURE_WITNESS_2026-05-28.md",
        ],
        "game_app_evidence": [
            "docs/milestone-evidence/GAME_COMPATIBILITY_WITNESS_2026-05-28_SELF_HOSTED_SKY_RUN.md",
        ],
        "matrix_terms": ["generic_gamepad", "Generic Gamepad"],
        "claim_terms": ["Refined Generic"],
    },
    "xbox_wireless_controller": {
        "descriptor_checker": "tools/check_xbox_ble_profile.py",
        "target_evidence": [
            "docs/milestone-evidence/XBOX_BLE_PROFILE_V1_2026-05-29.md",
        ],
        "real_usb_input_evidence": [],
        "virtual_input_evidence": [
            "docs/milestone-evidence/VIRTUAL_INPUT_XBOX_BRIDGE_WITNESS_2026-05-30.md",
        ],
        "deterministic_persona_report_evidence": [
            "docs/milestone-evidence/XBOX_STANDARD_LAYOUT_DIAGNOSTIC_2026-05-29.md",
        ],
        "host_evidence": [
            "docs/milestone-evidence/XBOX_STANDARD_LAYOUT_DIAGNOSTIC_2026-05-29.md",
        ],
        "game_app_evidence": [],
        "matrix_terms": ["xbox_wireless_controller", "Xbox Wireless Controller"],
        "claim_terms": ["Xbox BLE Profile v1", "Xbox macOS/Chrome deterministic diagnostic"],
    },
    "ble_keyboard": {
        "descriptor_checker": None,
        "target_evidence": [],
        "real_usb_input_evidence": [],
        "virtual_input_evidence": [],
        "deterministic_persona_report_evidence": [],
        "host_evidence": [],
        "game_app_evidence": [],
        "matrix_terms": ["Keyboard/iCade", "ble_keyboard"],
        "claim_terms": ["Keyboard/iCade"],
        "planned": True,
    },
}


def file_contains_any(path: pathlib.Path, terms: list[str]) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    return any(term in text for term in terms)


def command_passes(command: list[str]) -> bool:
    result = subprocess.run(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    return result.returncode == 0


def add_file_checks(checks: list[Check], layer: str, item: str, paths: list[str], claimed: bool) -> None:
    if not paths:
        status = "warn" if claimed else "pass"
        checks.append(Check(layer, item, status, "no evidence required for planned/unclaimed persona"))
        return
    missing = [path for path in paths if not pathlib.Path(path).exists()]
    if missing:
        checks.append(Check(layer, item, "fail", "missing: " + ", ".join(missing)))
    else:
        checks.append(Check(layer, item, "pass", ", ".join(paths)))


def add_optional_evidence_check(checks: list[Check], item: str, paths: list[str]) -> None:
    if not paths:
        checks.append(Check("evidence", item, "warn", "not claimed by current evidence set"))
        return
    add_file_checks(checks, "evidence", item, paths, claimed=True)


def evaluate_persona(persona: str, artifact_dir: pathlib.Path | None = None) -> dict[str, Any]:
    if persona not in PERSONAS:
        raise ValueError(f"unknown persona: {persona}")
    spec = PERSONAS[persona]
    planned = bool(spec.get("planned"))
    claimed = not planned
    checks: list[Check] = []

    checker = spec.get("descriptor_checker")
    if checker is None:
        checks.append(Check("source", "descriptor_checker", "warn", "not implemented yet"))
    else:
        status = "pass" if pathlib.Path(checker).exists() and command_passes(["python3", checker, "--quiet"]) else "fail"
        checks.append(Check("source", "descriptor_checker", status, str(checker)))

    add_file_checks(checks, "evidence", "target_side_witness", spec["target_evidence"], claimed)
    add_optional_evidence_check(checks, "real_usb_input_witness", spec["real_usb_input_evidence"])
    add_optional_evidence_check(checks, "virtual_input_witness", spec["virtual_input_evidence"])
    add_optional_evidence_check(
        checks,
        "deterministic_persona_report_witness",
        spec["deterministic_persona_report_evidence"],
    )
    add_file_checks(checks, "evidence", "host_visible_witness", spec["host_evidence"], claimed)
    add_optional_evidence_check(checks, "game_app_witness", spec["game_app_evidence"])

    if artifact_dir is not None:
        checks.append(
            Check(
                "artifact",
                "artifact_dir",
                "pass" if artifact_dir.exists() else "warn",
                str(artifact_dir),
            )
        )

    matrix_ok = file_contains_any(pathlib.Path("docs/HOST_COMPATIBILITY_MATRIX.md"), spec["matrix_terms"])
    checks.append(
        Check(
            "docs",
            "host_compatibility_matrix",
            "pass" if matrix_ok else ("warn" if planned else "fail"),
            "docs/HOST_COMPATIBILITY_MATRIX.md",
        )
    )

    public_claims_ok = file_contains_any(pathlib.Path("docs/PUBLIC_CLAIMS.md"), spec["claim_terms"])
    checks.append(
        Check(
            "docs",
            "public_claim_boundary",
            "pass" if public_claims_ok else ("warn" if planned else "fail"),
            "docs/PUBLIC_CLAIMS.md",
        )
    )

    statuses = [check.status for check in checks]
    return {
        "persona": persona,
        "pass_count": statuses.count("pass"),
        "warn_count": statuses.count("warn"),
        "fail_count": statuses.count("fail"),
        "acceptance_gate_passed": statuses.count("fail") == 0,
        "checks": [check.to_json() for check in checks],
    }


def print_table(summary: dict[str, Any]) -> None:
    print(f"\nPersona: {summary['persona']}")
    print(f"{'Layer':<12} {'Item':<30} {'Status':<7} Note")
    print(f"{'-'*12} {'-'*30} {'-'*7} {'-'*20}")
    for check in summary["checks"]:
        print(f"{check['layer']:<12} {check['item']:<30} {check['status']:<7} {check['note']}")
    print(
        json.dumps(
            {
                "pass_count": summary["pass_count"],
                "warn_count": summary["warn_count"],
                "fail_count": summary["fail_count"],
                "acceptance_gate_passed": summary["acceptance_gate_passed"],
            },
            sort_keys=True,
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--persona", action="append", choices=sorted(PERSONAS))
    parser.add_argument("--artifact-dir", type=pathlib.Path)
    parser.add_argument("--out-json", type=pathlib.Path)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    personas = args.persona or ["generic_gamepad", "xbox_wireless_controller"]
    summaries = [evaluate_persona(persona, args.artifact_dir) for persona in personas]
    result = {
        "personas_checked": len(summaries),
        "fail_count": sum(summary["fail_count"] for summary in summaries),
        "warn_count": sum(summary["warn_count"] for summary in summaries),
        "summaries": summaries,
    }
    if args.out_json:
        args.out_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not args.quiet:
        for summary in summaries:
            print_table(summary)
        print(json.dumps({"personas_checked": result["personas_checked"], "fail_count": result["fail_count"], "warn_count": result["warn_count"]}, indent=2))
    return 1 if result["fail_count"] else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        raise SystemExit(130)
