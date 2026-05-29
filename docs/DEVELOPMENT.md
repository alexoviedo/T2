# Development Workflow

This project treats code and checked-in evidence as the source of truth. Status
docs should only advance when the repo contains a reproducible transcript,
browser capture, screenshot, CI artifact, or target witness that proves the
claim.

## No-Hardware Validation

Run this before opening a PR or after changing code, docs, scripts, web UI, or
evidence references:

```bash
./scripts/validate_no_hardware.sh
```

The helper is safe without an ESP32-S3, HOTAS, hub, serial device, Bluetooth
pairing, browser chooser, or physical controls. It runs Rust formatting,
clippy, host build/tests, shell syntax checks, Python compile checks, evidence
reference validation, launch-readiness validation, Python unit tests, and web
checks when `web/` exists.

The web build expects Node `20.19+`. CI pins Node `20.19`; local older Node 20
builds may fail even when the app code is fine.

## Target Preflight

ESP32-S3 target preflight is separate because it depends on the local Xtensa
and ESP-IDF setup:

```bash
./scripts/check_target_build.sh
```

Before changing ESP-IDF build wiring, run `scripts/verify_cloud_equivalent.sh`
or document exactly why it cannot run.

## Evidence Rules

- Put concise, reviewed evidence summaries under `docs/milestone-evidence/`.
- Keep generated transcripts, screenshots, browser captures, and JSON summaries
  under `target/`; do not commit the full target artifact directory.
- Add every checked-in evidence summary to `docs/EVIDENCE_INDEX.md`.
- State what the evidence proves and what it does not prove.
- Browser Gamepad API evidence is host-visible HID evidence, not game/app
  compatibility.
- Do not claim BLE bond persistence, broad host/browser support, final Flight
  Pack calibration quality, Xbox host-visible refined mapping, or real
  game/app compatibility without matching checked-in evidence.

## Public Launch Checks

Run the launch checker before public announcements or release tags:

```bash
python3 tools/check_launch_readiness.py --verbose
```

It verifies required public files, README links, issue templates, the evidence
index, and root license presence.

## Human-Only Steps

Future Codex/operator chunks may use local hardware and browsers, but they
should not silently skip human-only actions. If a run requires moving a HOTAS
control, pressing a pedal, selecting a Chrome Web Serial device, approving a
macOS permission prompt, pairing Bluetooth, or interacting with a real game UI,
the operator prompt must say exactly what action is required and pause until it
is complete.

When Alex is away, skip those tasks, keep any generated target artifacts under
`target/`, and report the exact blocker.

## Witness Helper Maintenance

Several witness helpers share serial command, artifact-writing, browser sample,
and operator-prompt patterns. Keep near-term changes local unless a helper bug
or new workflow needs shared behavior. A future low-risk refactor should move
common serial transcript, JSON artifact, and evidence-summary helpers into a
small `tools/` library without changing target protocol behavior.
