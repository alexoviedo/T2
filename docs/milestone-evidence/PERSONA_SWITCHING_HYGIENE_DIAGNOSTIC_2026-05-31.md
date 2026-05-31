# Persona Switching Hygiene Diagnostic - 2026-05-31

Status: diagnostic evidence. This proves the witness tooling can detect and
reject stale browser Gamepad API slots during Generic/Xbox persona switching,
and it documents the remaining macOS Bluetooth/cache reconnect blocker. It does
not prove Generic virtual browser replay success.

## Summary

USB2BLE was tested with diagnostic virtual normalized-input replay after a
successful Xbox virtual bridge witness. The prior Generic browser run had
accepted Chrome's stale Xbox-shaped standard Gamepad API slot while the target
had switched to `generic_gamepad`. The updated browser witness now records
session labels, expected persona/mapping fields, axes/buttons counts, and stale
slot markers.

Strict Generic replay rejected the stale Xbox-shaped slot. With the target still
connected, the bridge published Generic virtual-input reports, but Chrome did
not expose an acceptable Generic Gamepad API slot. After `FORGET_BLE_BONDS` and
an ESP32-S3 reset, the target advertised the Generic persona but macOS/Chrome
did not reconnect automatically. A no-human Generic->Xbox hygiene sequence then
failed cleanly with no stale browser samples and no false pass.

## Context

- Date/time: 2026-05-31T18:32:01Z to 2026-05-31T18:38:21Z
- Commit: `a8bb5192323833cf07467c8732e6ea721f8f328b` plus working-tree changes
  described by this evidence
- Serial port: `/dev/cu.usbmodem5B5E0200881`
- Host: MacBook Pro 15-inch 2016 on macOS 12.7.x
- Browser: Google Chrome local Gamepad witness page
- Personas tested: `xbox_wireless_controller`, `generic_gamepad`
- Input source: diagnostic virtual normalized-input replay
- Human physical input required: no
- Human browser/Bluetooth action required during this diagnostic: no

## Commands Run

```text
python3 tools/virtual_input_bridge_witness.py --port /dev/cu.usbmodem5B5E0200881 --persona generic --scenarios all --duration-per-scenario 0.75 --witness-port 8820 --no-human --assume-bluetooth-connected --auto-arm --no-physical-input

python3 tools/serial_command.py --port /dev/cu.usbmodem5B5E0200881 --timeout 3 GET_STATUS GET_BRIDGE_STATUS GET_VIRTUAL_INPUT_STATUS FORGET_BLE_BONDS

espflash reset --chip esp32s3 --port /dev/cu.usbmodem5B5E0200881 --non-interactive

python3 tools/virtual_input_bridge_witness.py --port /dev/cu.usbmodem5B5E0200881 --persona generic --scenarios all --duration-per-scenario 0.75 --witness-port 8821 --browser-timeout 20 --no-human --assume-bluetooth-connected --auto-arm --no-physical-input

python3 tools/persona_switch_hygiene.py --port /dev/cu.usbmodem5B5E0200881 --sequence generic,xbox --witness-port-start 8830 --duration-per-scenario 0.6 --no-human
```

## Diagnostic Results

| Run | Persona | Target BLE | Browser expected slot | Stale captures | Published delta | Result |
| --- | --- | --- | --- | --- | --- | --- |
| Prior artifact analysis | Generic | Connected | Stale Xbox-shaped standard slot detected | yes | n/a | false Generic browser evidence identified |
| Strict Generic replay | Generic | Connected | Not seen | 0 | 58 | fail: no acceptable Generic browser slot |
| Bond-clear/reset Generic replay | Generic | Advertising / not connected | Not seen | 0 | 0 | fail: host did not reconnect automatically |
| No-human hygiene sequence | Generic -> Xbox | Not connected for both runs | Not seen | 0 | 0 for both | fail: no false pass, reconnect blocked |

The browser witness rejected the stale slot shape during Generic runs:

```text
expectedPersona=generic
expectedMapping=none
rejectStale=1
sessionLabel=generic-20260531T183210Z
```

The strict Generic run showed target-side publication while Chrome did not
surface a matching Generic slot:

```text
target_ble_connected=true
browser_capture_count=0
browser_expected_gamepad_seen=false
browser_stale_capture_count=0
matched_expected_count=0
expected_count=12
published_delta=58
```

After target-side bond clear and reset, the target no longer had a host
connection:

```text
STATUS:ble=Advertising;profile=none;persona=generic_gamepad;bonds=false;
BRIDGE_STATUS:enabled=true;persona=generic_gamepad;...published=0;...skipped_not_connected=519;last_error=not_connected;
```

The reusable hygiene workflow then avoided a false success:

```text
persona_switching_hygiene_passed=false
pass_count=0
fail_count=2
stale_capture_count=0
human_prompted=false
```

## Artifacts

- `target/persona-switching-diagnosis/persona_switching_20260531T183201Z`
- `target/virtual-input-bridge-witness/generic_virtual_bridge_20260531T183210Z`
- `target/virtual-input-bridge-witness/generic_virtual_bridge_20260531T183428Z`
- `target/persona-switching-hygiene/persona_switch_20260531T183637Z`
- `target/virtual-input-bridge-witness/generic_virtual_bridge_20260531T183637Z`
- `target/virtual-input-bridge-witness/xbox_virtual_bridge_20260531T183821Z`

## Conclusion

The tooling now distinguishes stale browser Gamepad API slots from the active
target persona. This prevents a stale Xbox-shaped `STANDARD GAMEPAD` slot from
being counted as Generic browser evidence.

Generic virtual browser replay remains unproven in this diagnostic. On this
host, a fully automated no-human persona switch did not restore a clean Generic
Gamepad API slot after the Xbox run. Target-side bond clear and reset left the
device advertising and not connected, so the next run needs either manual macOS
Bluetooth cache cleanup/reconnect evidence or deeper host-side Bluetooth cleanup
automation.

## Limitations

- This is virtual normalized-input diagnostic evidence, not physical USB
  movement evidence.
- It does not prove Generic virtual browser replay success.
- It does not prove BLE bond persistence, reconnect robustness, or product-ready
  persona switching.
- It does not prove broad host/browser support.
- It does not prove Xbox console, proprietary Xbox Wireless, Windows, Android,
  iOS, Linux, native game/app, or final Flight Pack calibration compatibility.
