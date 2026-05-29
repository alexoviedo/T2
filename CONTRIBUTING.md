# Contributing

Thanks for helping make USB2BLE better. This project values reproducible
evidence over optimistic status claims.

## Development Setup

```bash
./scripts/validate_no_hardware.sh
./scripts/check_target_build.sh
```

The first command is safe without hardware. The second requires the ESP32-S3
Xtensa/ESP-IDF toolchain.

The web app expects Node `20.19+`.

## Evidence Rules

- Code and checked-in evidence are the source of truth.
- Put generated transcripts, screenshots, JSON summaries, and browser captures
  under `target/`.
- Commit only concise reviewed summaries under `docs/milestone-evidence/`.
- Add each checked-in evidence document to `docs/EVIDENCE_INDEX.md`.
- Do not present host simulation, browser Gamepad API, or CLI-only evidence as
  stronger than it is.
- Do not claim game/app compatibility, BLE bond persistence, final calibration,
  broad host/browser support, or iPhone support without matching evidence.

## Hardware Witnesses

If a run requires physical movement, Bluetooth pairing, Chrome Web Serial device
selection, macOS permission UI, or game UI interaction, prompt the operator with
one exact action and wait. Never fabricate target, browser, or host evidence.

## Pull Requests

Good pull requests include:

- a focused description of the change,
- commands run,
- evidence docs or target artifacts when behavior claims change,
- honest limitations and known follow-up work.

Before changing ESP-IDF build wiring, run `scripts/verify_cloud_equivalent.sh`
or explain exactly why it cannot run.
