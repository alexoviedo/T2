# USB2BLE

## Current status
- `main` is at demo-bridge code-path status after M4 normalized-input evidence.
- ESP32-S3 target-build preflight is expected to pass in CI.
- Real powered-hub hardware witness transcripts are checked in for attach/detach identity, HID descriptor capture, raw input-report capture, HID capability summary, baseline normalized input, and the practical RJ12 Flight Pack topology.
- Host-tested demo bridge code now encodes current normalized USB state into a Generic Gamepad report via `GET_GENERIC_GAMEPAD_REPORT`.
- Host-tested mapping diagnostics now explain how normalized source controls map into the Generic Gamepad persona via `GET_GENERIC_GAMEPAD_MAPPING`.
- Real target smoke evidence for `GET_GENERIC_GAMEPAD_REPORT` is checked in for the RJ12 Flight Pack topology.
- Real target smoke evidence for `GET_GENERIC_GAMEPAD_MAPPING` is checked in for the TWCS plus T.16000M topology.
- Real target operator movement evidence now shows T.16000M stick movement changing raw USB reports and mapped Generic Gamepad diagnostics after a USB host session reset.
- Real target delta evidence now covers TWCS throttle movement, TFRP pedal movement through TWCS/RJ12, and a mapped T.16000M trigger press.
- Real target detach cleanup evidence now shows a detached downstream HID device removed from USB status, descriptors, and cached reports while the hub remains attached.
- A curated `flight_pack_demo` profile is implemented, host-tested, target-build verified, and target-witnessed for the T.16000M + TWCS/RJ12 demo path.
- Target BLE HID demo firmware now starts the Generic Gamepad persona, reaches `ble=Advertising`, connects to a Mac host, and publishes both synthetic and live USB-derived Generic Gamepad reports over BLE.
- Browser Gamepad API witness evidence is checked in for the BLE Generic Gamepad path, including synthetic self-test changes, one live USB-derived publish, and one `flight_pack_demo` T.16000M stick movement.
- The hosted `latest` GitHub Release firmware image has been downloaded, flashed to the ESP32-S3, and smoke-verified through the serial control plane.

## What this project is building toward
- ESP32-S3 USB HID to BLE bridge.
- eventual powered USB-C hub support.
- eventual multiple USB HID inputs.
- mapping to BLE Generic Gamepad is now started with a pure auto-mapping and persona-encoding path.
- eventual BLE Xbox Wireless-style output.
- the BLE transport is intentionally persona-driven so Xbox Wireless-style output can be added later as a separate persona/report encoder.

## Current milestone: M4
- target scope is HID report decoding and normalized live-input diagnostics.
- descriptor/report/summary/normalized-input control-plane fulfillment is proven for the THRUSTMASTER T.16000 FCS HOTAS through the HooToo powered hub.
- expanded Flight Pack evidence proves normalized input for the TFRP pedals and T.16000 stick in one full-pack run, TWCS normalized input when connected through the same hub without the other Flight Pack devices, and simultaneous normalized input for the recommended two-USB topology: pedals connected to TWCS by RJ12, with TWCS USB plus stick USB through the HooToo hub.
- explicit calibrated TWCS/TFRP axis targets, exact RJ12 pedal axis labels, and simultaneous normalized streaming from all three separate Flight Pack USB devices remain open for full M4 completion.
- BLE Generic Gamepad publishing now has real Mac host and browser Gamepad API witnesses; final app/game compatibility and HOTAS mapping remain open.

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
- `GET_GENERIC_GAMEPAD_REPORT` returns an encoded Generic Gamepad report from the latest normalized input frames, ready for the future BLE publish layer.
- `GET_GENERIC_GAMEPAD_MAPPING` explains each selected Generic Gamepad mapping decision, including source VID/PID/interface, source control, target control, value, and reason.
- `flight_pack_demo` selects an explicit T.16000M + TWCS/RJ12 profile when both known devices are present, while `generic_auto` remains the fallback for other HID combinations.
- `START_BLE_GENERIC_GAMEPAD` starts the target BLE HID Generic Gamepad persona.
- `SEND_BLE_SELF_TEST_REPORT` publishes an explicit synthetic Generic Gamepad report when a BLE host is connected.
- `PUBLISH_GENERIC_GAMEPAD_REPORT` publishes the latest encoded USB-derived Generic Gamepad report when a BLE host is connected.
- `FORGET_BLE_BONDS` clears BLE bonds through the BLE transport.
- `tools/gamepad_witness/server.py` serves a repo-local browser Gamepad API witness page and captures snapshots under `target/gamepad-witness/`.
- `tools/mapping_delta_witness.py` captures clean before/after or timed-watch `GET_GENERIC_GAMEPAD_MAPPING` deltas for one physical control.
- `tools/usb_report_delta_witness.py` captures lower-level `GET_LAST_USB_REPORT` byte deltas so raw USB movement can be proven before debugging normalization or mapping.
- `tools/detach_cleanup_witness.py` captures before/detach/after cleanup evidence for one downstream USB HID device.
- CI packages a flashable ESP32-S3 merged firmware image with `scripts/package_firmware.sh`, uploads it as the `usb2ble-fw-esp32s3-flashable` GitHub Actions artifact, and refreshes a `latest` GitHub Release on `main` pushes after host and target jobs both pass.
- ESP32-S3 target preflight build.
- host simulation for app/control-plane testing only.

## What is not implemented yet
- direct-attach hardware transcript remains blocked by available cabling/port geometry.
- full target IR diagnostic dump.
- calibrated TWCS/TFRP profile refinements beyond the current demo rules.
- exact RJ12 pedal axis labels.
- game/application compatibility beyond the browser Gamepad API witness.
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

## Firmware artifact
```bash
./scripts/check_target_build.sh
./scripts/package_firmware.sh
espflash write-bin --chip esp32s3 --port <PORT> 0x0 target/firmware/usb2ble-fw-esp32s3-merged.bin
```
GitHub Actions uploads the same merged image plus a manifest and ELF as the
`usb2ble-fw-esp32s3-flashable` artifact. On `main` pushes, the release job
publishes those files to the `latest` GitHub Release after host checks and
ESP32-S3 target packaging both pass.

## Hardware verification
See: `docs/HARDWARE_M2B1_VERIFICATION.md`

## ASAP demo runbook
See: `docs/ASAP_DEMO_RUNBOOK.md`

## Integrity rules for agents
* code and checked-in evidence are the source of truth.
* do not claim hardware verification without real transcript evidence.
* do not present host simulation as target proof.
* do not advance a future milestone before its prerequisite hardware evidence is checked in.
