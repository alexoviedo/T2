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
