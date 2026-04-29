# USB2BLE

## Current status
- `main` is at M4 normalized-input code-path status.
- ESP32-S3 target-build preflight is expected to pass in CI.
- Real powered-hub hardware witness transcripts are checked in for attach/detach identity, HID descriptor capture, raw input-report capture, HID capability summary, baseline normalized input, and the practical RJ12 Flight Pack topology.

## What this project is building toward
- ESP32-S3 USB HID to BLE bridge.
- eventual powered USB-C hub support.
- eventual multiple USB HID inputs.
- eventual mapping to BLE Generic Gamepad.
- eventual BLE Xbox Wireless-style output.
- current milestone does not implement those yet.

## Current milestone: M4
- target scope is HID report decoding and normalized live-input diagnostics.
- descriptor/report/summary/normalized-input control-plane fulfillment is proven for the THRUSTMASTER T.16000 FCS HOTAS through the HooToo powered hub.
- expanded Flight Pack evidence proves normalized input for the TFRP pedals and T.16000 stick in one full-pack run, TWCS normalized input when connected through the same hub without the other Flight Pack devices, and simultaneous normalized input for the recommended two-USB topology: pedals connected to TWCS by RJ12, with TWCS USB plus stick USB through the HooToo hub.
- button-press delta capture, detach cleanup evidence, exact RJ12 pedal axis labels, and simultaneous normalized streaming from all three separate Flight Pack USB devices remain open for full M4 completion.
- no BLE publishing yet.

## What works today
- serial control plane.
- `GET_INFO`
- `GET_STATUS`
- `GET_PROFILE`
- `GET_USB_STATUS`
- `LIST_USB_DEVICES`
- `GET_USB_DESCRIPTOR <device>:<interface>` returns captured HID report descriptor bytes for discovered HID interfaces.
- `GET_LAST_USB_REPORT <device>:<interface>` returns the most recent raw input report after a report is received.
- `GET_HID_SUMMARY <device>:<interface>` returns parsed axes/buttons/hats/report IDs for descriptors that parse successfully.
- `GET_NORMALIZED_INPUT <device>:<interface>` returns a normalized control frame decoded from the latest input report for descriptors that parse successfully.
- ESP32-S3 target preflight build.
- host simulation for app/control-plane testing only.

## What is not implemented yet
- direct-attach hardware transcript remains blocked by available cabling/port geometry.
- full target IR diagnostic dump.
- button-press delta witness for normalized input.
- normalized detach cleanup witness.
- mapping.
- BLE Generic Gamepad output.
- BLE Xbox output.
- powered hub all-device Flight Pack simultaneous report merge for three separate USB Flight Pack devices.

## Repository layout

- `.cargo/config.toml` — ESP-IDF target build configuration for `xtensa-esp32s3-espidf`.
- `.github/workflows/ci.yml` — host checks and ESP32-S3 target preflight build.
- `crates/usb2ble-contracts` — shared contract types, DTOs, and protocol-facing identifiers.
- `crates/usb2ble-control` — serial command decoding and response encoding.
- `crates/usb2ble-app` — application state and command/event handling.
- `crates/usb2ble-platform-esp32` — ESP32/ESP-IDF platform adapters, including USB host witness plumbing.
- `crates/usb2ble-fw` — firmware binary entrypoint and ESP-IDF root crate.
- `scripts/` — build, flash, monitor, and validation helpers.
- `docs/HARDWARE_M2B1_VERIFICATION.md` — local hardware verification playbook.

## Cloud validation
```bash
cargo fmt --all -- --check
cargo clippy --workspace --all-targets --locked -- -D warnings
cargo build --workspace --locked
cargo test --workspace --locked
bash -n scripts/*.sh
./scripts/check_target_build.sh
```

## ESP-IDF toolchain pin
The firmware root crate pins ESP-IDF through `crates/usb2ble-fw/Cargo.toml`:

```toml
[package.metadata.esp-idf-sys]
esp_idf_version = "v5.5.3"
esp_idf_tools_install_dir = "workspace"
```

The checked-in Cargo config must not set `IDF_PATH`; local `IDF_PATH` or
`ESP_IDF_VERSION` environment variables are developer overrides and bypass the
repo default.

## Local ESP32-S3 build
The authoritative command is:
```bash
./scripts/check_target_build.sh
```

Equivalent direct command:
```bash
cargo +esp build -Z build-std=std,panic_abort --locked --package usb2ble-fw --target xtensa-esp32s3-espidf
```

## Flash and monitor
```bash
./scripts/build.sh
./scripts/flash.sh --monitor
```
`--port <PORT>` may be passed through to `scripts/flash.sh` and `scripts/monitor.sh`.

## Hardware verification
See: `docs/HARDWARE_M2B1_VERIFICATION.md`

## Integrity rules for agents
* code and checked-in evidence are the source of truth.
* do not claim hardware verification without real transcript evidence.
* do not present host simulation as target proof.
* do not advance a future milestone before its prerequisite hardware evidence is checked in.
