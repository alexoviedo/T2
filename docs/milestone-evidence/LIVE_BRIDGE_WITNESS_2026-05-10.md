# Live Bridge Witness - 2026-05-10

## Summary

Real ESP32-S3 hardware witness for explicit live bridge mode.

Live bridge mode is the continuous USB-derived BLE publication path intended for
real games/apps. This witness proves that `START_BRIDGE` enables automatic
report publication for both Xbox and Generic personas, that `GET_BRIDGE_STATUS`
tracks publish counters, and that `STOP_BRIDGE` disables the mode. Manual
publish commands remain diagnostic.

This is not a broad game/app compatibility claim. Browser Gamepad API evidence
is included because it is useful host-visible evidence, but actual game/app
compatibility still requires separate checked-in evidence.

## Environment

- Firmware commit: `83161a9a1c94d5261586ec110256420894633589`
- Firmware version: `0.4.2-ble-hid-demo`
- Board/port: ESP32-S3 on `/dev/cu.usbmodem5B5E0200881`
- Host OS: macOS 12.7.5 (`21H1222`)
- Hub: HooToo SHUTTLE HT-UC001 powered USB hub
- USB devices observed for Generic run:
  - Hub: `2109:2813`
  - TWCS throttle: `044f:b687`
  - T.16000M stick: `044f:b10a`

## Xbox Live Bridge Run

- Helper summary: `target/live-bridge-witness/xbox_demo_20260510T002024Z/summary.json`
- Serial transcript: `target/live-bridge-witness/xbox_demo_20260510T002024Z/serial_transcript.txt`
- Browser witness JSONL: `target/live-bridge-witness/xbox_demo_20260510T002024Z/gamepad-witness/gamepad_witness_20260510T002024Z.jsonl`
- Active persona: `xbox_wireless_controller`
- Browser identity observed: `Xbox Wireless Controller (STANDARD GAMEPAD Vendor: 045e Product: 0b13)`

Key serial evidence:

```text
START_BLE_XBOX_CONTROLLER
BLE_ACTION:action=start_xbox_controller;state=Advertising;
GET_STATUS
STATUS:ble=Connected;profile=none;persona=xbox_wireless_controller;bonds=false;
START_BRIDGE
BRIDGE_STATUS:enabled=true;persona=xbox_wireless_controller;rate_hz=50;last_publish_ms=none;published=0;skipped_duplicate=0;skipped_rate=0;skipped_not_connected=0;skipped_not_ready=0;last_error=none;
GET_BRIDGE_STATUS
BRIDGE_STATUS:enabled=true;persona=xbox_wireless_controller;rate_hz=50;last_publish_ms=29612;published=6;skipped_duplicate=5;skipped_rate=0;skipped_not_connected=0;skipped_not_ready=0;last_error=none;
STOP_BRIDGE
BRIDGE_STATUS:enabled=false;persona=xbox_wireless_controller;rate_hz=50;last_publish_ms=30931;published=7;skipped_duplicate=6;skipped_rate=0;skipped_not_connected=0;skipped_not_ready=0;last_error=none;
GET_XBOX_GAMEPAD_REPORT
ENCODED_REPORT:persona=xbox_wireless_controller;report_id=1;bytes=847ca47a00007778ff01ff0300000000;
```

Result:

| Check | Result |
| --- | --- |
| Xbox persona started | Pass |
| BLE connected | Pass |
| Xbox self-test report was 16 bytes | Pass |
| Xbox USB-derived report was 16 bytes | Pass |
| Bridge enabled | Pass |
| Bridge published count increased | Pass, `0 -> 7` |
| Bridge stopped | Pass |
| Browser saw Xbox VID/PID | Pass |

## Generic Live Bridge Run

- Helper summary: `target/live-bridge-witness/demo_rehearsal_20260510T002242Z/summary.json`
- Serial transcript: `target/live-bridge-witness/demo_rehearsal_20260510T002242Z/serial_transcript.txt`
- Browser witness JSONL: `target/live-bridge-witness/demo_rehearsal_20260510T002242Z/gamepad-witness/gamepad_witness_20260510T002242Z.jsonl`
- Active persona: `generic_gamepad`

Key serial evidence:

```text
START_BLE_GENERIC_GAMEPAD
BLE_ACTION:action=start_generic_gamepad;state=Connected;
GET_STATUS
STATUS:ble=Connected;profile=none;persona=generic_gamepad;bonds=false;
START_BRIDGE
BRIDGE_STATUS:enabled=true;persona=generic_gamepad;rate_hz=50;last_publish_ms=none;published=6;skipped_duplicate=6;skipped_rate=0;skipped_not_connected=0;skipped_not_ready=0;last_error=none;
GET_BRIDGE_STATUS
BRIDGE_STATUS:enabled=true;persona=generic_gamepad;rate_hz=50;last_publish_ms=107197;published=11;skipped_duplicate=10;skipped_rate=0;skipped_not_connected=0;skipped_not_ready=0;last_error=none;
STOP_BRIDGE
BRIDGE_STATUS:enabled=false;persona=generic_gamepad;rate_hz=50;last_publish_ms=108059;published=12;skipped_duplicate=11;skipped_rate=0;skipped_not_connected=0;skipped_not_ready=0;last_error=none;
GET_GENERIC_GAMEPAD_REPORT
ENCODED_REPORT:persona=generic_gamepad;report_id=1;bytes=00000885fca5faff7f1f00008078f8;
```

Result:

| Check | Result |
| --- | --- |
| Generic persona started | Pass |
| BLE connected | Pass |
| USB hub/TWCS/T.16000M detected | Pass |
| `flight_pack_demo` profile selected | Pass |
| Stick source maps to gamepad `x` | Pass |
| Bridge enabled | Pass |
| Bridge published count increased | Pass, `6 -> 12` in the same boot session |
| Bridge stopped | Pass |
| Browser saw input change | Pass |

Note: macOS/browser naming remained cached as `Xbox Wireless Controller
(Vendor: 303a Product: 4001)` for the Generic run. The VID/PID matched the
Generic identity, and this witness does not treat browser display name as a
pass criterion.

## Honest Conclusion

Proven:

- `START_BRIDGE`, `GET_BRIDGE_STATUS`, and `STOP_BRIDGE` work on real ESP32-S3 hardware.
- Live bridge mode automatically publishes USB-derived reports for the active Xbox persona.
- Live bridge mode automatically publishes USB-derived reports for the active Generic persona.
- Bridge status counters provide reproducible evidence that publication happened while bridge mode was enabled.
- Browser Gamepad API saw host-visible input changes during these runs.

Not proven:

- Broad game/app compatibility.
- Long-duration stability.
- Final HOTAS/TWCS/TFRP calibration.
- Final Generic browser display-name behavior after macOS caches prior BLE identities.
