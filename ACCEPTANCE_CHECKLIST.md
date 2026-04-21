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
- [x] UART framing handles fragmented input and multiple commands correctly.
- [x] Build, Flash, and Monitor scripts exist in `scripts/` and are functional wrappers around `cargo build` and `espflash`.
- [x] Command loop sends explicit `ERROR` responses for malformed input.
- [x] Target-side `init()` and `Uart` are functional for ESP32-S3 (espidf).

## Validation Commands

```bash
# Full workspace validation
cargo fmt --all
cargo clippy --workspace -- -D warnings
cargo test --workspace

# M1 Specific
./scripts/build.sh
```

## M1 Acceptance Evidence

### Host Evidence
- **Integration Tests:** `crates/usb2ble-fw/src/integration_tests.rs` verifies sequential commands and fragmented input (`GET_` followed by `INFO\n`).
- **UART Framing:** `crates/usb2ble-platform-esp32/src/lib.rs` unit tests verify buffer draining and multi-command chunk handling.

### Target (ESP32-S3) Evidence
- **Build:** `./scripts/build.sh` produces a binary for `xtensa-esp32s3-espidf`.
- **Boot Banner (Captured):**
```text
--- USB2BLE FIRMWARE BOOT ---
Name: usb2ble
Version: 0.1.0-m1
Contract Version: 1
Status: M1 Real
Ready for commands.
```
- **Control Plane Round-trip (Captured):**
```text
>> GET_INFO
<< INFO:version=1;name=usb2ble;persona=none;
>> GET_STATUS
<< STATUS:ble=Idle;profile=none;bonds=false;
>> INVALID_CMD
<< ERROR:Generic
```
