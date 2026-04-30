# Generic Gamepad Mapping Diagnostic Codepath Witness - 2026-04-30

## Scope

This is host-tested codepath evidence for `GET_GENERIC_GAMEPAD_MAPPING`.

It does not claim new hardware behavior. It proves that the control plane,
application layer, and Generic Gamepad auto mapper can produce a diagnostic
response explaining how normalized source controls map into persona controls.

## Command

```text
GET_GENERIC_GAMEPAD_MAPPING
```

Expected response shape:

```text
GENERIC_GAMEPAD_MAPPING:profile=generic_auto;persona=generic_gamepad;entries=<n>;mappings=src=<device>:<interface>:<vid>:<pid>:<source_control>,target=<target|none>,value=<kind:value>,reason=<reason>|...;
```

Each mapping entry includes:

- USB source device ID and interface ID
- USB VID/PID
- normalized source control ID
- target Generic Gamepad control, or `none`
- normalized value
- stable decision reason

## Host Verification

Focused tests run:

```bash
cargo test -p usb2ble-mapping
cargo test -p usb2ble-control
cargo test -p usb2ble-app
cargo fmt --all -- --check
cargo +esp test --workspace --locked
cargo +esp clippy --workspace --all-targets --locked -- -D warnings
RUSTUP_TOOLCHAIN=esp ./scripts/check_target_build.sh
```

Results:

```text
usb2ble-mapping: 4 passed
usb2ble-control: 5 passed
usb2ble-app: 4 passed
cargo fmt --all -- --check: pass
cargo +esp test --workspace --locked: pass
cargo +esp clippy --workspace --all-targets --locked -- -D warnings: pass
Target build preflight passed for xtensa-esp32s3-espidf.
```

The default local `stable` toolchain is rustc `1.85.0`, and
`cargo test --workspace --locked` is blocked there because locked dependency
`home@0.5.12` requires rustc `1.88`. The installed `esp` toolchain is rustc
`1.90.0-nightly`, so the locked workspace test and clippy checks above were run
with `cargo +esp`.

## Proven

- The mapper produces diagnostics for mapped axes/buttons and unmapped controls.
- The serial control plane decodes `GET_GENERIC_GAMEPAD_MAPPING`.
- The serial control plane encodes `GENERIC_GAMEPAD_MAPPING` responses.
- The application can build mapping diagnostics from latest normalized input
  frames.

## Not Proven

- Target hardware smoke execution is covered separately in
  `docs/milestone-evidence/GENERIC_GAMEPAD_MAPPING_TARGET_WITNESS_2026-04-30.md`.
- Operator movement/delta evidence for `GET_GENERIC_GAMEPAD_MAPPING`.
- Final T.16000M/TWCS/TFRP mapping and calibration.
- Xbox Wireless-style BLE output.
