# Xbox Host-Visible Diagnostic - 2026-05-29

Status: partial diagnostic evidence. This proves deterministic Xbox Report ID 1 payloads were host-visible in Chrome through a non-Xbox browser identity, but it does not prove an Xbox-like browser identity, broad Xbox compatibility, Xbox console compatibility, proprietary Xbox Wireless compatibility, Windows/Android/iOS/Linux compatibility, BLE bond persistence, or refined Xbox Flight Pack host-visible mapping.

## Summary

USB2BLE was rebuilt and flashed with a deterministic Xbox diagnostic publish command, then tested against macOS 12.7.x and Google Chrome using the existing browser Gamepad witness. The target successfully ran the Xbox BLE compatibility profile, macOS Bluetooth connected to the device, and deterministic Xbox Report ID 1 payloads were published over the active BLE connection.

Chrome exposed the device as `USB2BLE Gamepad (STANDARD GAMEPAD)`, not as `Xbox Wireless Controller` or `Vendor: 045e Product: 0b13`. Deterministic Xbox report scenarios produced browser Gamepad API changes for left stick, right stick, left trigger, right trigger, and one button through that non-Xbox identity. The diagnostic therefore proves host-visible input movement, but fails the Xbox-like identity criterion for this milestone.

Alex observed that the macOS Bluetooth UI initially showed `USB2BLE`, then presented the connection as `Xbox Wireless Controller` after connecting. That host identity nuance should be treated as diagnostic, not as a broad compatibility claim.

## Target Context

- Date/time: 2026-05-29T21:50:36Z
- Commit: `31b7446c99f0d38c6da0e54eb9798325d26a4f0f`
- Serial port: `/dev/cu.usbmodem5B5E0200881`
- Host: MacBook Pro 15-inch 2016 on macOS 12.7.x
- Browser: Google Chrome, local Gamepad witness page
- Active persona: `xbox_wireless_controller`
- Active compatibility variant: `xbox_compatibility`
- Bluetooth identity under test: `Xbox Wireless Controller`
- Firmware action: rebuilt and flashed before diagnostic run

## Commands Run

```text
./scripts/check_target_build.sh
./scripts/build.sh
./scripts/flash.sh --port /dev/cu.usbmodem5B5E0200881
python3 tools/xbox_host_visible_witness.py --port /dev/cu.usbmodem5B5E0200881 --witness-port 8778 --browser-timeout 8
```

## Profile Checker

`tools/check_xbox_ble_profile.py` passed against the source-defined Xbox profile:

```text
30 pass, 0 warn, 0 fail
```

## Transcript Excerpts

Target connected as Xbox persona:

```text
STATUS:ble=Connected;profile=none;persona=xbox_wireless_controller;bonds=false;
BLE_ADVERTISING_INFO:persona=xbox_wireless_controller;state=Connected;variant=xbox_compatibility;device_name=Xbox Wireless Controller;appearance=0x03c4;advertised_uuids=1812;security=bond;bonds=false;
```

Deterministic wake reports published over the connected BLE path:

```text
PUBLISH_XBOX_TEST_REPORT button_a
BLE_ACTION:action=publish_xbox_test_report;state=Connected;persona=xbox_wireless_controller;report_id=1;bytes=00800080008000800000000000010000;
PUBLISH_XBOX_TEST_REPORT left_stick_right
BLE_ACTION:action=publish_xbox_test_report;state=Connected;persona=xbox_wireless_controller;report_id=1;bytes=ffff0080008000800000000000000000;
```

Browser witness result:

```text
browser_capture_file=target/xbox-host-visible-witness/xbox_host_visible_20260529T215036Z/browser_captures.jsonl
browser_identity_observed=USB2BLE Gamepad (STANDARD GAMEPAD)
browser_identity_matched_xbox=false
xbox_host_visible_witness_passed=false
```

Representative browser-visible scenario deltas:

```text
left_stick_right: browser axis A0 changed 0.0 -> 1.0
right_stick_right: browser axis A2 changed 0.0 -> 1.0
left_trigger_max: browser button B6 changed 0.0 -> 1.0
right_trigger_max: browser button B7 changed 0.0 -> 1.0
button_a: browser button B0 changed 0.0 -> 1.0
```

## Pass / Fail Table

| Check | Result |
| --- | --- |
| Firmware rebuilt and flashed with deterministic Xbox diagnostic command | PASS |
| Target reports `xbox_compatibility` profile | PASS |
| Xbox profile checker passes | PASS |
| macOS Bluetooth connection reached target `Connected` state | PASS |
| Deterministic Report ID 1 payload publishes while connected | PASS |
| Browser capture file created | PASS |
| Chrome Gamepad API exposed a connected gamepad | PASS |
| Chrome Gamepad API exposed Xbox-like identity | FAIL |
| Browser-visible left stick scenario | PASS via A0 |
| Browser-visible right stick scenario | PASS via A2 |
| Browser-visible left trigger scenario | PASS via B6 |
| Browser-visible right trigger scenario | PASS via B7 |
| Browser-visible button scenario | PASS via B0 |

## Artifacts

- `target/xbox-host-visible-witness/xbox_host_visible_20260529T215036Z`
- `target/xbox-host-visible-witness/xbox_host_visible_20260529T215036Z/summary.json`
- `target/xbox-host-visible-witness/xbox_host_visible_20260529T215036Z/scenario_results.json`
- `target/xbox-host-visible-witness/xbox_host_visible_20260529T215036Z/serial_transcript.txt`
- `target/xbox-host-visible-witness/xbox_host_visible_20260529T215036Z/browser_captures.jsonl`
- `target/xbox-host-visible-witness/xbox_host_visible_20260529T215036Z/xbox_profile_check.json`

## Limitations

- This is a partial diagnostic witness, not an Xbox-like identity success.
- The run proves macOS Bluetooth connection at the target state, connected BLE report publishing, and browser-visible deterministic movement through Chrome's standard gamepad surface.
- The browser identity was `USB2BLE Gamepad (STANDARD GAMEPAD)`, not Xbox-like.
- The macOS Bluetooth UI identity changed during connection, so future work should capture screenshots or system Bluetooth logs for the identity transition.
- No Xbox console, proprietary Xbox Wireless, Windows, Android, iOS, Linux, native game, or broad browser compatibility is proven.
- BLE bond persistence and reconnect behavior are not proven.
