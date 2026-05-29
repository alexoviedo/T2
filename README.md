# USB2BLE

USB2BLE is experimental ESP32-S3 firmware that bridges USB HID controllers to
Bluetooth LE gamepad personas, with a Web Serial configurator for runtime
mapping profiles.

The current launch candidate is focused on a practical Thrustmaster Flight Pack
demo path: T.16000M stick over USB, TWCS throttle over USB, and TFRP pedals
through the TWCS RJ12 port via a powered HooToo USB hub.

## What It Does

- Enumerates USB HID devices on the ESP32-S3 USB host path.
- Captures HID descriptors, raw reports, parsed summaries, and normalized input.
- Maps normalized input to BLE Generic Gamepad and Xbox-style report personas.
- Runs an explicit live bridge mode that publishes USB-derived BLE reports.
- Imports, saves, loads, and starts runtime JSON configs over the serial/Web
  Serial-compatible protocol.
- Provides a Vite/TypeScript Web Serial configurator and ESP Web Tools flashing
  surface.

## Current Status

This project is in **alpha / public launch candidate** status. It has real
target, host, browser, soak, and self-hosted browser-game smoke evidence for
the refined Generic Flight Pack path, but it is not a polished consumer product.

Evidence is the source of truth. Start with [docs/EVIDENCE_INDEX.md](docs/EVIDENCE_INDEX.md).

## Proven

- ESP32-S3 target build and flashable firmware packaging in CI.
- Powered hub attach/detach identity, HID descriptor capture, raw report
  capture, HID summary, and normalized input.
- Practical RJ12 Flight Pack axis labels for TWCS throttle, TFRP rudder, and
  both toe brakes.
- Runtime config import/save/load across an actual board reset.
- Chrome Web Serial configurator smoke: connect, load schemas/catalog/config,
  import Flight Pack Generic, save, load, and `START_CONFIGURED`.
- Refined target-side Generic and Xbox mapping/report encoding for the practical
  RJ12 topology.
- Refined Generic BLE live bridge host visibility in Chrome Gamepad API:
  Generic `z/rx/ry/rz` appear as browser axes `A2/A3/A4/A5`.
- Refined Generic 300-second live bridge soak in Chrome.
- Narrow self-hosted browser game/app smoke using the refined Generic profile.
- Xbox BLE identity/report publishing and macOS pairing/input witness for the
  existing Xbox slice.

## Not Yet Proven

- Broad game/app compatibility.
- External or native game compatibility.
- iPhone compatibility.
- Xbox host-visible refined Flight Pack mapping.
- BLE bond persistence and reconnect hardening.
- Final product-quality deadzone/calibration feel.
- Broad host/browser support beyond the checked-in witnesses.
- Simultaneous three-separate-USB Flight Pack streaming.

## Tested Hardware Context

| Area | Evidence-backed status |
| --- | --- |
| ESP32-S3 target | Target build, flash packaging, serial control plane, BLE witnesses |
| HooToo SHUTTLE HT-UC001 powered hub | Powered-hub topology witnessed |
| Thrustmaster T.16000M stick | USB input, mapping, BLE Generic path witnessed |
| Thrustmaster TWCS throttle | USB input, RJ12 pedal host path, refined Generic mapping witnessed |
| Thrustmaster TFRP pedals via TWCS RJ12 | Rudder and toe-brake labels plus refined Generic mapping witnessed |
| Other hubs/controllers/hosts | Not broadly claimed |

## Quickstart

### No-Hardware Validation

```bash
./scripts/validate_no_hardware.sh
./scripts/check_target_build.sh
```

The no-hardware validation is safe without an ESP32-S3, HOTAS, browser chooser,
Bluetooth pairing, or physical controls. The target preflight requires the
Xtensa/ESP-IDF toolchain.

### Build And Flash Locally

```bash
./scripts/check_target_build.sh
./scripts/build.sh
./scripts/flash.sh --port <PORT>
```

### Flash From GitHub Pages

The Pages build publishes the Web Serial configurator and ESP Web Tools manifest
for the latest CI firmware artifact. Until the public repository URL is final,
use the Pages URL from the repository settings or GitHub Actions deployment
summary.

### Configure The Refined Generic Flight Pack Profile

```bash
python3 tools/configure_board.py --port <PORT> preset flight-pack-generic
python3 tools/serial_command.py --port <PORT> GET_CONFIG_STATUS START_CONFIGURED GET_BRIDGE_STATUS
```

The Web Serial configurator can perform the same config import/save/load/start
flow in Chrome or Edge on desktop.

## Useful Commands

```bash
# Serial discovery/probe
python3 tools/serial_command.py --port <PORT> GET_INFO GET_STATUS GET_USB_STATUS LIST_USB_DEVICES

# Config persistence witness
python3 tools/config_persistence_witness.py --port <PORT> --reboot-after-save

# Browser Gamepad API witness server
python3 tools/gamepad_witness/server.py

# Refined Generic live bridge soak
python3 tools/refined_generic_live_bridge_soak.py --port <PORT>

# Self-hosted browser game/app smoke
python3 tools/browser_game_compat_witness.py --port <PORT>
```

Generated witness artifacts go under `target/`. Only concise reviewed evidence
summaries should be committed under `docs/milestone-evidence/`.

## Repository Map

- `crates/usb2ble-*` - Rust firmware, protocol, mapping, HID, persona, and
  storage crates.
- `scripts/` - build, flash, package, and validation helpers.
- `tools/` - serial, config, calibration, soak, browser witness, and evidence
  validation helpers.
- `web/` - Web Serial configurator and firmware flashing UI.
- `docs/` - runbooks, evidence, release notes, public claims, and handoff docs.
- `.github/workflows/ci.yml` - host checks, target preflight, firmware artifact
  packaging, release upload, and Pages deployment.

## Developer Docs

- [Development workflow](docs/DEVELOPMENT.md)
- [Configuration](docs/CONFIGURATION.md)
- [Project status handoff](docs/PROJECT_STATUS_HANDOFF.md)
- [Compatibility matrix](COMPATIBILITY_MATRIX.md)
- [Game/app compatibility witness standard](docs/GAME_COMPATIBILITY_WITNESS.md)
- [Release checklist](docs/RELEASE_CHECKLIST.md)
- [Public claims guide](docs/PUBLIC_CLAIMS.md)

## Safety And Limitations

USB2BLE is experimental firmware. BLE HID behavior can vary by host OS, browser,
Bluetooth cache state, game engine, and controller profile. Do not infer broad
compatibility from a single witness. Do not use this project where input loss,
unexpected controls, or firmware faults could create safety risk.

## License

A root open-source license has not been selected yet. This is tracked as a
launch blocker in [docs/LAUNCH_BLOCKERS.md](docs/LAUNCH_BLOCKERS.md). Do not
redistribute or reuse the project as open-source until Alex explicitly adds a
license.
