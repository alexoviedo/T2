# Acceptance Checklist

This document defines the validation steps required for each milestone.

## M0 — Repo skeleton, contracts, and build discipline

- [x] `cargo check` passes for all crates in the workspace.
- [x] `cargo test --workspace` passes for all host-supported crates.
- [x] `clippy` reports no warnings for pure crates.
- [x] `rustfmt --check` confirms canonical formatting.
- [x] `usb2ble-contracts` exports `CONTRACT_VERSION`.
- [x] `usb2ble-storage` provides in-memory implementations for Profile/Config/Bond stores.
- [x] Documentation files are complete and reflect project requirements.
- [x] CI workflow is present and passing.

## M1 — Boot, serial control plane, and operator witness

- [x] Firmware prints startup banner with build info (name, version) and contract version.
- [x] `GET_INFO` returns valid response.
- [x] `GET_STATUS` returns valid system state.
- [x] `GET_PROFILE` returns valid active profile.
- [x] Serial framing handles text-based commands over UART on both host and target.
- [x] UART framing handles fragmented input and multiple commands correctly via `UartReadResult`.
- [x] Build, Flash, and Monitor scripts exist in `scripts/` and are functional wrappers around `cargo build` and `espflash`.
- [x] Command loop sends explicit `ERROR` responses for malformed input.
- [x] Target-side `init()` and `Uart` are functional for ESP32-S3 (espidf).

## M2A — USB witness: contracts, app-state, and control-plane groundwork

- [x] Contracts defined for USB device/interface identity and events.
- [x] `AppState` refactored to separate physical devices from HID interfaces.
- [x] `GET_USB_STATUS` and `LIST_USB_DEVICES` implemented in control plane.
- [x] `GET_USB_DESCRIPTOR` and `GET_LAST_USB_REPORT` support explicit `NotFound` error.
- [x] `handle_usb_event` logic verified with multi-interface cleanup tests on host.
- [x] Platform `EspUsbIngress` plumbing (channel-based) established.
- [x] Real target USB stack initialization placeholder added.

## M2B.1 — real attach/detach + identity witness

- [x] ESP32-S3 target path installs USB host and registers host client with return-code checks.
- [x] Code-path emits `DeviceAttached` using target USB host enumeration and VID/PID lookup.
- [x] Code-path emits HID `InterfaceDiscovered` from active config descriptor parsing.
- [x] Code-path emits `DeviceDetached` and removes device/interface bookkeeping.
- [x] `GET_USB_STATUS` and `LIST_USB_DEVICES` provide the witness surface for attach/detach identity state.
- [x] CI workflow includes ESP32-S3 target-build preflight job (`scripts/check_target_build.sh`).
- [x] Target build preflight verified for `xtensa-esp32s3-espidf` in GitHub Actions.
- [ ] Real-hardware witness transcript captured and checked in for this revision.

## M2B.1 Validation Commands

```bash
cargo fmt --all -- --check
cargo clippy --workspace --all-targets --locked -- -D warnings
cargo build --workspace --locked
cargo test --workspace --locked
bash -n scripts/*.sh
./scripts/check_target_build.sh
```

## M2B.1 Required Evidence (real hardware only)

> NOTE: Do not paste simulated output in this section.

- **Board model:** TODO exact carrier board model; observed target is ESP32-S3 rev v0.2, 16 MB flash over WCH USB Single Serial
- **Powered hub used:** HooToo SHUTTLE HT-UC001, observed as `VID=2109, PID=2813`
- **Candidate USB input device used:** AFTERGLOW PL-3702 Xbox-style wired gamepad, observed as `VID=0e6f, PID=0213`; instrumented run shows vendor-specific interfaces (`CLASS=ff`), not HID class `03`
- **HID-class USB input device used:** USB keyboard, exact model not captured, observed as `VID=30fa, PID=2031` with HID interfaces `CLASS=03, SUBCLASS=01, PROTOCOL=01` and `CLASS=03, SUBCLASS=00, PROTOCOL=02`
- **HID-class HOTAS device used:** THRUSTMASTER T.16000 FCS HOTAS, observed as `VID=044f, PID=b10a` with HID interface `CLASS=03, SUBCLASS=00, PROTOCOL=00`
- **HID-class Flight Pack device set used:** THRUSTMASTER T.16000M FCS FLIGHT PACK, composed of T.16000M FCS flight stick, TWCS throttle, and TFRP rudder pedals; observed as `VID=044f, PID=b687`, `VID=044f, PID=b679`, and `VID=044f, PID=b10a`, each with HID interface `CLASS=03, SUBCLASS=00, PROTOCOL=00`
- **Direct connection topology:** Blocked with available hardware; physical connector/port geometry did not allow direct AFTERGLOW-to-ESP32-S3 host-path attachment
- **Hub connection topology:** ESP32-S3 USB host path -> HooToo SHUTTLE HT-UC001 -> AFTERGLOW PL-3702; ESP32-S3 USB host path -> HooToo SHUTTLE HT-UC001 -> USB keyboard; ESP32-S3 USB host path -> HooToo SHUTTLE HT-UC001 -> THRUSTMASTER T.16000 FCS HOTAS; ESP32-S3 USB host path -> HooToo SHUTTLE HT-UC001 -> THRUSTMASTER T.16000M FCS FLIGHT PACK devices
- **Build command:** `RUSTUP_TOOLCHAIN=esp ./scripts/verify_cloud_equivalent.sh`
- **Flash command:** `./scripts/flash.sh --chip esp32s3 --port /dev/cu.usbmodem5B5E0200881 --monitor --non-interactive`
- **Monitor command:** `./scripts/monitor.sh --port /dev/cu.usbmodem5B5E0200881`
- **Actual boot transcript:** `docs/milestone-evidence/M2B1_HUB_WITNESS_2026-04-28.md`
- **Direct pre-plug `GET_USB_STATUS` / `LIST_USB_DEVICES`:** Not captured; blocked by available cabling/port geometry
- **Direct post-plug attach transcript and `GET_USB_STATUS` / `LIST_USB_DEVICES`:** Not captured; blocked by available cabling/port geometry
- **Direct post-unplug detach transcript and `GET_USB_STATUS` / `LIST_USB_DEVICES`:** Not captured; blocked by available cabling/port geometry
- **Hub pre-plug `GET_USB_STATUS` / `LIST_USB_DEVICES`:** `docs/milestone-evidence/M2B1_HUB_WITNESS_2026-04-28.md`
- **Hub post-plug attach transcript and `GET_USB_STATUS` / `LIST_USB_DEVICES`:** `docs/milestone-evidence/M2B1_HUB_WITNESS_2026-04-28.md`
- **Hub post-unplug detach transcript and `GET_USB_STATUS` / `LIST_USB_DEVICES`:** `docs/milestone-evidence/M2B1_HUB_WITNESS_2026-04-28.md`

## M2B.2 — descriptor/report capture (Hardware witness captured)

- [x] `GET_USB_DESCRIPTOR` returns real descriptor bytes from hardware.
- [x] `GET_LAST_USB_REPORT` returns real input reports from hardware.
- [x] Verified complete descriptor/report flow with a real USB HID device on target.

## M2B.2 Current Evidence

- **Descriptor capture evidence:** `docs/milestone-evidence/M2B2_DESCRIPTOR_WITNESS_2026-04-29.md`
- **Verified descriptor/report device:** THRUSTMASTER T.16000 FCS HOTAS through HooToo SHUTTLE HT-UC001, `VID=044f, PID=b10a`, interface `0`
- **Descriptor command:** `GET_USB_DESCRIPTOR 4:0` in the descriptor-only run; `[DESCRIPTOR] Device: ID=2, IFACE=0, BYTES=134` in the final report-capture boot
- **Descriptor result:** 134-byte HID report descriptor returned as `USB_DESCRIPTOR:<hex>`
- **Input report command:** `GET_LAST_USB_REPORT 2:0`
- **Input report result:** 64-byte HID input report returned as `USB_REPORT:<hex>`
- **Remaining scope:** BLE publishing and report coverage for every Flight Pack component remain future work.

## M3 — HID descriptor IR and hardware/host parity (Summary witness captured)

- [x] `usb2ble-hid` parses HID short-item report descriptors into `HidDescriptorIr`.
- [x] Parse failures are surfaced as typed errors (`EmptyDescriptor`, `TruncatedItem`, unsupported long items, missing report globals).
- [x] Hardware-captured T.16000 descriptor fixture is committed.
- [x] Capability summary includes axes/buttons/hats/report IDs.
- [x] `GET_HID_SUMMARY` returns target-side parsed summary for a real HID device.
- [x] Host fixture summary matches target `GET_HID_SUMMARY` output for the T.16000 FCS HOTAS.
- [ ] Full target IR dump/parity is exposed over diagnostics.

## M3 Current Evidence

- **Summary evidence:** `docs/milestone-evidence/M3_HID_SUMMARY_WITNESS_2026-04-29.md`
- **Fixture:** `crates/usb2ble-hid/fixtures/thrustmaster_t16000_fcs_044f_b10a_report_descriptor.hex`
- **Verified descriptor device:** THRUSTMASTER T.16000 FCS HOTAS through HooToo SHUTTLE HT-UC001, `VID=044f, PID=b10a`, interface `0`
- **Summary command:** `GET_HID_SUMMARY 2:0`
- **Summary result:** `axes=4`, `buttons=16`, `hats=1`, `report_ids=0`, axis usages `01:30,01:31,01:35,01:36`, hat usage `01:39`
- **Remaining scope:** Full IR diagnostic dump, BLE publishing, and all-device Flight Pack coverage remain future work.

## M4 — live normalized input on hardware (baseline witness captured)

- [x] `usb2ble-hid` decodes input report bit fields from parsed HID IR.
- [x] `usb2ble-input` normalizes buttons, axes, hats, and unknown controls into the shared input model.
- [x] `AppState` retains the latest input report packet by descriptor key.
- [x] `GET_NORMALIZED_INPUT <device>:<interface>` returns a target-side normalized frame for a real HID input report.
- [x] Host tests cover descriptor parsing, report decoding, and normalization for committed fixtures.
- [x] Operator movement delta transcript captured for normalized input.
- [ ] Operator button-press delta transcript captured for normalized input.
- [ ] Detach cleanup transcript captured for normalized input state.
- [x] Normalized report coverage captured for TFRP pedals.
- [x] Normalized report coverage captured for TWCS throttle when connected through the hub without the other Flight Pack devices.
- [x] Normalized report coverage captured for the practical RJ12 Flight Pack topology: TFRP pedals connected to TWCS by RJ12, with TWCS USB plus T.16000M stick USB through the HooToo hub.
- [ ] Normalized report coverage captured for all three separate simultaneous Flight Pack USB devices.

## M4 Current Evidence

- **Normalized input evidence:** `docs/milestone-evidence/M4_NORMALIZED_INPUT_WITNESS_2026-04-29.md`; `docs/milestone-evidence/M4_FLIGHT_PACK_NORMALIZED_WITNESS_2026-04-29.md`; `docs/milestone-evidence/M4_RJ12_TWO_USB_FLIGHT_PACK_WITNESS_2026-04-29.md`
- **Verified normalized-input device:** THRUSTMASTER T.16000 FCS HOTAS through HooToo SHUTTLE HT-UC001, `VID=044f`, `PID=b10a`, interface `0`
- **Additional Flight Pack coverage:** TFRP pedals `044f:b679` normalized in a full-pack run; TWCS throttle `044f:b687` normalized when connected through the hub without the other Flight Pack devices; RJ12 topology normalized with pedals connected to TWCS and both TWCS USB plus T.16000M stick USB streaming together through the hub
- **Normalized command:** `GET_NORMALIZED_INPUT 2:0`
- **Normalized result:** `controls=21`, including 16 buttons, 1 hat, and 4 axes from a real 64-byte target input report
- **Remaining scope:** Button-press delta evidence, normalized detach cleanup evidence, exact RJ12 pedal axis labels, BLE publishing, and all-device simultaneous Flight Pack streaming with three separate USB Flight Pack devices remain future work.
