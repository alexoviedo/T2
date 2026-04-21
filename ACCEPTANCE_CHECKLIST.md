# Acceptance Checklist

This document defines the validation steps required for each milestone.

## M0 — Repo skeleton, contracts, and build discipline

- [ ] `cargo check` passes for all crates in the workspace.
- [ ] `cargo test --workspace` passes for all host-supported crates.
- [ ] `clippy` reports no warnings for pure crates.
- [ ] `rustfmt --check` confirms canonical formatting.
- [ ] `usb2ble-contracts` exports `CONTRACT_VERSION`.
- [ ] `usb2ble-storage` provides in-memory implementations for Profile/Config/Bond stores.
- [ ] Documentation files are complete and reflect project requirements.
- [ ] CI workflow is present and passing.

## M1 — Boot, serial control plane, and operator witness

- [ ] Firmware prints startup banner with version info.
- [ ] `GET_INFO` returns valid JSON response.
- [ ] `GET_STATUS` returns valid system state.
- [ ] Serial framing handles partial or corrupted packets gracefully.

## Validation Commands

```bash
# Full workspace validation
cargo fmt --all -- --check
cargo clippy --workspace -- -D warnings
cargo test --workspace
```
