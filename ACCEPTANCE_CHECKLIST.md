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

- **Board model:** TODO (required for acceptance)
- **HID device used:** TODO (required for acceptance)
- **Power / connection path:** TODO (required for acceptance)
- **Build command:** `./scripts/build.sh`
- **Flash command:** `espflash flash target/xtensa-esp32s3-espidf/debug/usb2ble-fw --monitor`
- **Monitor command:** `./scripts/monitor.sh`
- **Actual boot transcript:** TODO (required for acceptance)
- **Actual pre-plug `GET_USB_STATUS` / `LIST_USB_DEVICES`:** TODO (required for acceptance)
- **Actual post-plug `GET_USB_STATUS` / `LIST_USB_DEVICES`:** TODO (required for acceptance)
- **Actual post-unplug `GET_USB_STATUS` / `LIST_USB_DEVICES`:** TODO (required for acceptance)

## M2B.2 — descriptor/report capture (Pending)

- [ ] `GET_USB_DESCRIPTOR` returns real descriptor bytes from hardware.
- [ ] `GET_LAST_USB_REPORT` returns real input reports from hardware.
- [ ] Verified with real USB HID devices on target.
