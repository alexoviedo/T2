# Xbox BLE Demo Runbook

## Status

- Generic BLE Gamepad: known working hardware path.
- Xbox mapping/report encoding: implemented and host-tested.
- Xbox BLE identity/report publishing: implemented and target-witnessed on ESP32-S3.
- Xbox macOS pairing/input compatibility: real witness captured for macOS 12.7.5.
- Broader game/app compatibility is not claimed.

This runbook tests the Generic HID transport boundary with an Xbox Wireless
Controller compatibility persona. It targets Xbox Wireless Controller model
1914 / Series X|S BLE compatibility:

- Device name: `Xbox Wireless Controller`
- VID: `0x045e`
- PID: `0x0b13`
- Manufacturer: `Microsoft`
- Version / bcdDevice: `0x0515`
- Appearance: gamepad

The VID/PID above are the BLE compatibility identity, not the USB identity.
Elite Series 2 BLE compatibility appears to use PID `0x0b22` and is future
work.

## Build And Flash

```sh
cargo fmt --all -- --check
cargo clippy --workspace --all-targets --locked -- -D warnings
cargo build --workspace --locked
cargo test --workspace --locked
bash -n scripts/*.sh
./scripts/check_target_build.sh
./scripts/build.sh
./scripts/flash.sh --port /dev/cu.usbmodem5B5E0200881
```

Start the serial monitor:

```sh
./scripts/monitor.sh --port /dev/cu.usbmodem5B5E0200881
```

## Manual Xbox BLE Flow

Reset the ESP32-S3 before switching from the Generic persona to the Xbox
persona. The firmware intentionally supports one active BLE HID report map per
boot/session.

```text
GET_STATUS
START_BLE_XBOX_CONTROLLER
GET_STATUS
```

Expected start response:

```text
BLE_ACTION:action=start_xbox_controller;state=Advertising;
```

On the Mac, pair/connect to:

```text
Xbox Wireless Controller
```

Then confirm:

```text
GET_STATUS
```

Desired connected evidence:

```text
STATUS:ble=Connected;...
```

The connected line should include:

```text
persona=xbox_wireless_controller;
```

Send the deterministic Xbox self-test twice:

```text
SEND_XBOX_SELF_TEST_REPORT
SEND_XBOX_SELF_TEST_REPORT
```

Expected response shape:

```text
BLE_ACTION:action=send_xbox_self_test;state=Connected;persona=xbox_wireless_controller;report_id=1;bytes=<32 hex chars>;
```

The 32 hex chars represent the 16-byte Xbox input payload. The self-test
alternates A pressed/released and left_x max/min while leaving unrelated
controls neutral.

After moving or pressing one attached USB control, test the USB-derived Xbox
path:

```text
GET_XBOX_GAMEPAD_REPORT
PUBLISH_XBOX_GAMEPAD_REPORT
```

Expected report response:

```text
ENCODED_REPORT:persona=xbox_wireless_controller;report_id=1;bytes=<32 hex chars>;
```

Expected publish response when connected:

```text
BLE_ACTION:action=publish_xbox_gamepad;state=Connected;persona=xbox_wireless_controller;report_id=1;bytes=<32 hex chars>;
```

## Rehearsal Helper

Serial-only required proof plus optional browser witness:

```sh
python3 tools/xbox_demo_rehearsal.py \
  --port /dev/cu.usbmodem5B5E0200881 \
  --browser-witness
```

Self-test only, without requiring live USB movement:

```sh
python3 tools/xbox_demo_rehearsal.py \
  --port /dev/cu.usbmodem5B5E0200881 \
  --skip-live-publish
```

The helper saves:

- `serial_transcript.txt`
- `summary.json`
- optional browser Gamepad witness JSONL capture

Browser/Gamepad API visibility is useful evidence. The 2026-05-09 witness saw a
standard gamepad with Xbox VID/PID, but the browser display name was
`USB2BLE Gamepad`; use VID `045e` and PID `0b13` as the reliable browser-side
identity signal for this pass.

## Recovery

If the Mac does not show `Xbox Wireless Controller` within about 30 seconds:

```text
GET_STATUS
```

If the device is still advertising, restart the macOS Bluetooth scan. If it is
not advertising, reset the ESP32-S3 and rerun:

```text
START_BLE_XBOX_CONTROLLER
```

If pairing fails or macOS remembers stale data:

```text
FORGET_BLE_BONDS
```

Then remove/forget the device in macOS Bluetooth settings, reset the ESP32-S3,
and start the Xbox persona again.

If you attempt to switch personas without reset, the expected error is:

```text
ERROR:PersonaAlreadyActive
```

If you publish a report for a persona that is not active, the expected error is:

```text
ERROR:PersonaMismatch
```

If the host is paired but not connected, the expected publish error is:

```text
ERROR:BleNotConnected
```

## Evidence To Capture

- Exact boot/version lines.
- Exact `START_BLE_XBOX_CONTROLLER` response.
- Whether macOS sees `Xbox Wireless Controller`.
- Whether macOS pairs/connects.
- Exact `GET_STATUS` after pairing.
- Exact `SEND_XBOX_SELF_TEST_REPORT` responses.
- Exact `GET_XBOX_GAMEPAD_REPORT` and `PUBLISH_XBOX_GAMEPAD_REPORT` output.
- Browser/Gamepad API result if visible.

See `docs/milestone-evidence/XBOX_BLE_WITNESS_2026-05-09.md` for the first
real macOS pairing/input witness. Do not extend that claim to other hosts or
games without new checked-in evidence.
