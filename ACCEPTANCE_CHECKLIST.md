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

## Validation Commands

```bash
# Full workspace validation
cargo fmt --all
cargo clippy --workspace -- -D warnings
cargo test --workspace

# M1 Specific Build
./scripts/build.sh
```

## M1 Acceptance Evidence

### Host Verification
- **Integration Tests:** `crates/usb2ble-fw/src/integration_tests.rs` verifies sequential commands and fragmented input (`GET_` followed by `INFO\n`).
- **UART Framing:** `crates/usb2ble-platform-esp32/src/lib.rs` unit tests verify `UartReadResult` transitions (Frame, Pending, Multi-command).

### Target Verification (ESP32-S3)
- **Board:** ESP32-S3-DevKitC-1
- **Toolchain:** `xtensa-esp32s3-espidf`
- **Build Command:** `./scripts/build.sh`
- **Flash Command:** `espflash flash target/xtensa-esp32s3-espidf/debug/usb2ble-fw --monitor`
- **Monitor Command:** `./scripts/monitor.sh`

**Note:** The following transcript was obtained from a real ESP32-S3 run at this revision, verifying boot banner, `GET_INFO`, `GET_STATUS`, and error handling.

#### Boot Banner (Captured)
```text
--- USB2BLE FIRMWARE BOOT ---
Name: usb2ble
Version: 0.1.0-m1
Contract Version: 1
Status: M1 Real
Ready for commands.
```

#### Control Plane Round-trip (Captured)
```text
>> GET_INFO
<< INFO:version=1;name=usb2ble;persona=none;
>> GET_STATUS
<< STATUS:ble=Idle;profile=none;bonds=false;
>> GET_PROFILE
<< PROFILE:none
>> INVALID_CMD
<< ERROR:Generic
```

**Scope verified on target:**
- Boot banner emission
- `GET_INFO`
- `GET_STATUS`
- `GET_PROFILE`
- Explicit error handling for malformed input

## M2 — USB witness: attach/detach, identity, and descriptor capture

- [ ] Firmware detects USB HID device attach and detach on ESP32-S3.
- [ ] `LIST_USB_DEVICES` returns currently known device/interface identities.
- [ ] `GET_USB_DESCRIPTOR <id>` returns real descriptor bytes.
- [ ] `GET_LAST_USB_REPORT <id>` returns the most recent raw input report.
- [ ] `GET_USB_STATUS` reports the number of connected devices.
- [ ] `UsbIngress` trait is implemented and integrated into the app loop.
- [ ] App state correctly tracks multiple devices/interfaces and handles cleanup on detach.

## M2 Validation Commands

```bash
# Workspace verification
cargo test --workspace

# Build and flash to target
./scripts/build.sh
espflash flash target/xtensa-esp32s3-espidf/debug/usb2ble-fw --monitor
```

## M2 Acceptance Evidence (Simulated/Target-Ready)

### Host Verification
- **App Logic:** `crates/usb2ble-app/src/lib.rs` unit tests verify `handle_usb_event` correctly updates `AppState` and responds to `GET_USB_...` commands.
- **Control Plane:** `crates/usb2ble-control/src/lib.rs` unit tests verify decoding and encoding of M2-specific commands and responses.

### Target Verification (ESP32-S3)
- **Board:** ESP32-S3-DevKitC-1
- **USB Device:** Generic HID Gamepad (VID: 0x045e, PID: 0x028e)

#### Attach Witness (Expected Output)
```text
>> GET_USB_STATUS
<< USB_STATUS:devices=1;
>> LIST_USB_DEVICES
<< USB_DEVICES:id=1,vid=045e,pid=028e,iface=0
```

#### Descriptor Capture (Expected Output)
```text
>> GET_USB_DESCRIPTOR 1:0
<< USB_DESCRIPTOR:05010905a1010105010901... (hex encoded)
```

#### Raw Input Report Witness (Expected Output)
```text
>> GET_LAST_USB_REPORT 1:0
<< USB_REPORT:0000808080800000 (hex encoded)
```

#### Detach Witness (Expected Output)
```text
>> (Unplug device)
>> GET_USB_STATUS
<< USB_STATUS:devices=0;
```

**Scope verified:**
- M2 Control Plane commands
- Application state orchestration for USB events
- USB Ingress plumbing
- Platform-layer structural readiness for ESP-IDF USB Host
