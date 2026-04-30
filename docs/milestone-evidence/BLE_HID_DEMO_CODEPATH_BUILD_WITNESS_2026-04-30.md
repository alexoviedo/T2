# BLE HID Demo Code Path Build Witness - 2026-04-30

## Scope

This is a build/code-path witness only. It is **not** a hardware BLE pairing,
connection, or input-report witness.

The change adds a target-buildable ESP32-S3 BLE HID transport path for the first
Generic Gamepad demo persona. The transport accepts persona descriptors and
encoded persona reports, so future Xbox Wireless-style output can be added as a
separate persona/report encoder instead of changing USB ingestion or the BLE
publication API.

## Commands Added

```text
START_BLE_GENERIC_GAMEPAD
SEND_BLE_SELF_TEST_REPORT
PUBLISH_GENERIC_GAMEPAD_REPORT
FORGET_BLE_BONDS
```

`SEND_BLE_SELF_TEST_REPORT` is intentionally synthetic and must not be presented
as USB hardware behavior.

## Verification

Ran:

```bash
RUSTUP_TOOLCHAIN=esp cargo test --workspace --offline
RUSTUP_TOOLCHAIN=esp ./scripts/verify_cloud_equivalent.sh
```

Result:

```text
cargo fmt --all -- --check: pass
cargo clippy --workspace --all-targets --locked -- -D warnings: pass
cargo build --workspace --locked: pass
cargo test --workspace --locked: pass
bash -n scripts/*.sh: pass
ESP32-S3 target build preflight: pass
```

Target build result:

```text
Target build preflight passed for xtensa-esp32s3-espidf.
```

## Follow-Up Target Witness

After flashing the same build to `/dev/cu.usbmodem5B5E0200881`, the target boot
and BLE advertising start were witnessed. See:

```text
docs/milestone-evidence/BLE_HID_GENERIC_GAMEPAD_ADVERTISING_WITNESS_2026-04-30.md
```

## Not Proven By This Build Witness

- ESP32-S3 advertises successfully as a BLE HID device.
- A host can pair/connect to the Generic Gamepad persona.
- `SEND_BLE_SELF_TEST_REPORT` produces visible host input.
- `PUBLISH_GENERIC_GAMEPAD_REPORT` sends a live USB-derived report over BLE.
