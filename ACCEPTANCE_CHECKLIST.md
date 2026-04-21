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

- [x] Firmware prints startup banner with version info.
- [x] `GET_INFO` returns valid response.
- [x] `GET_STATUS` returns valid system state.
- [x] `GET_PROFILE` returns valid active profile.
- [x] Serial framing handles text-based commands over UART.
- [x] Build, Flash, and Monitor scripts exist in `scripts/`.

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
- **Firmware entrypoint:** `crates/usb2ble-fw/src/lib.rs` implements `main` with banner and loop.
- **Control plane:** `crates/usb2ble-control/src/lib.rs` implements `GET_INFO`, `GET_STATUS`, `GET_PROFILE`.
- **App semantics:** `crates/usb2ble-app/src/lib.rs` handles commands and state.
- **Platform abstraction:** `crates/usb2ble-platform-esp32/src/lib.rs` provides `Uart` stub.
- **Build system:** `scripts/build.sh` successfully compiles the workspace.
- **Tests:** `cargo test` passes for `usb2ble-control` and `usb2ble-app` logic.
