# Project Status Handoff

Date: 2026-05-28

This handoff reconciles the current docs with checked-in code and evidence. It
does not add new hardware claims.

## Current Honest State

USB2BLE is past the original M4 normalized-input slice and now has witnessed
demo-bridge paths for both Generic Gamepad and Xbox BLE personas. The honest
label is: **post-M4 demo bridge / pre-product-hardening**.

Checked-in evidence supports:

- USB attach/detach identity through the HooToo powered hub.
- HID descriptor capture and raw HID input report capture.
- HID capability summaries and normalized input for T.16000/TWCS/TFRP paths.
- Generic Gamepad report encoding, mapping diagnostics, BLE pairing/input, and
  browser Gamepad API visibility.
- `flight_pack_demo` Generic Gamepad publish from real T.16000M movement.
- Xbox Wireless Controller BLE identity/report publishing on ESP32-S3, with
  macOS 12.7.5 pairing/input witness and browser Xbox VID/PID support.
- Explicit `START_BRIDGE` live bridge mode for Generic and Xbox personas.
- A 300-second Xbox live bridge soak.
- Web Serial-facing runtime configuration command substrate and web app build
  wiring.
- Durable runtime config persistence across an actual board reset, with
  post-reboot loaded config matching the imported config.
- Browser Web Serial configurator smoke in Google Chrome, covering connect,
  config/status/schema/catalog load, Flight Pack Generic import, save, load,
  and `START_CONFIGURED`.
- CI host checks, ESP32-S3 target preflight, firmware packaging, latest GitHub
  Release refresh, and Pages deployment.

## What Works Now

- No-hardware host validation through `scripts/validate_no_hardware.sh`.
- ESP32-S3 target preflight through `./scripts/check_target_build.sh` when the
  local Xtensa/ESP-IDF toolchain is installed.
- Runtime config protocol evidence through
  `tools/config_persistence_witness.py` when a serial port is explicitly
  provided.
- Runtime config reboot-persistence evidence through
  `docs/milestone-evidence/CONFIG_PERSISTENCE_WITNESS_2026-05-28.md`.
- Browser Web Serial configurator smoke evidence through
  `docs/milestone-evidence/WEB_SERIAL_CONFIGURATOR_SMOKE_2026-05-28.md`.
- Generic BLE demo rehearsal through `tools/asap_demo_rehearsal.py` when
  hardware is connected.
- Xbox BLE compatibility rehearsal through `tools/xbox_demo_rehearsal.py` when
  hardware is connected.
- Live bridge smoke/soak helpers through `tools/live_bridge_soak.py`.
- Game/app evidence workflow in `docs/GAME_COMPATIBILITY_WITNESS.md`.

## Not Yet Proven

- Broad game/app compatibility for either Generic or Xbox personas.
- Any console compatibility.
- Host breadth beyond the checked-in macOS/browser witnesses.
- Durable BLE bond persistence.
- Browser breadth beyond the checked-in Google Chrome Web Serial configurator
  smoke.
- Final Flight Pack calibration, deadzones, semantic TWCS/TFRP labels, and exact
  RJ12 pedal axis labels.
- Generic long-duration live bridge soak.
- Stable browser Gamepad API display name for Xbox across clean host state.
- Direct-attach USB witness; current direct attach remains blocked by available
  cabling/port geometry.

Browser Gamepad API evidence is useful host-visible HID evidence, but it is not
a game/app compatibility witness.

## No-Hardware Validation

Safe without ESP32, HOTAS, hub, serial port, BLE pairing, or browser device
access:

```bash
./scripts/validate_no_hardware.sh
```

The helper runs:

```bash
cargo fmt --all -- --check
cargo clippy --workspace --all-targets --locked -- -D warnings
cargo build --workspace --locked
cargo test --workspace --locked
bash -n scripts/*.sh
cd web && npm ci && npm test && npm run build
```

ESP32-S3 target preflight is intentionally separate because it depends on the
local Xtensa/ESP-IDF setup:

```bash
./scripts/check_target_build.sh
```

The older `scripts/verify_cloud_equivalent.sh` still runs the host checks plus
target preflight and is useful when the ESP toolchain is available.

## Next Hardware Validation Setup

Use the known witnessed setup:

- ESP32-S3 board on USB serial.
- HooToo SHUTTLE HT-UC001 powered hub on the ESP32-S3 USB host path.
- T.16000M stick USB on the hub.
- TWCS throttle USB on the hub.
- Optional TFRP pedals connected to TWCS over RJ12.
- macOS host for Bluetooth pairing and browser witness.

Recommended order:

1. Flash or confirm a current firmware image.
2. Run Generic live bridge rehearsal:
   `python3 tools/asap_demo_rehearsal.py --port <PORT> --live-bridge`
3. Run Xbox live bridge rehearsal:
   `python3 tools/xbox_demo_rehearsal.py --port <PORT> --browser-witness --live-bridge`
4. Run Generic long soak:
   `python3 tools/live_bridge_soak.py --port <PORT> --persona generic --duration-seconds 300 --sample-interval-seconds 5 --browser-witness`
5. Run Flight Pack calibration witness:
   `python3 tools/flight_pack_calibration_witness.py --port <PORT> --out-dir target/flight-pack-calibration`
6. For real compatibility claims, follow
   `docs/GAME_COMPATIBILITY_WITNESS.md` with live bridge enabled in an actual
   app/game.

## Recommended Next Implementation Chunks

- Generic 300-second live bridge soak and checked-in evidence.
- Flight Pack calibration/axis-label evidence and profile refinement.
- Web Serial configurator hardening from the checked-in smoke baseline,
  especially recovery/error UX under live target report chatter.
- Runtime config recovery/error-path hardening using
  `docs/CONFIG_PERSISTENCE_WITNESS.md` as the target-side protocol baseline.
- First real game/app compatibility witness using
  `docs/GAME_COMPATIBILITY_WITNESS.md`.
- Reconnect/bond recovery hardening with checked-in transcripts.

## Suggested Next Prompt

```text
Use the T2 / USB2BLE repo. Do not rewrite docs broadly. With hardware connected,
run the Generic live bridge soak and Flight Pack calibration witness from
docs/PROJECT_STATUS_HANDOFF.md, check in only concise evidence documents under
docs/milestone-evidence/, and update the compatibility matrix only for claims
directly proven by those artifacts.
```
