# Persona Switching Hygiene Diagnostic - 2026-05-31

Status: diagnostic evidence. This proves the witness tooling can detect and
reject stale browser Gamepad API slots during Generic/Xbox persona switching,
and it documents the remaining macOS Bluetooth/cache and Chrome Gamepad API
exposure blockers. It does not prove Generic virtual browser replay success.

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

A follow-up manual-cache-cleanup run removed the stale macOS Bluetooth entries
and reconnected only `USB2BLE Gamepad` as the Generic persona. After that step,
the target and macOS agreed that Generic BLE HID was connected, and macOS HID
enumeration showed `USB2BLE Gamepad` through `AppleUserHIDEventService` with
GameController capabilities. However, Chrome's Gamepad witness still captured
zero samples, including after an operator clicked Arm and after the target sent
Generic BLE self-test reports. The remaining blocker is now narrower than
"Bluetooth not connected": macOS sees the Generic HID device, but Chrome did
not expose it to the Gamepad API in this session.

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
- Human browser/Bluetooth action required during initial diagnostic: no
- Follow-up human GUI actions: Alex removed/forgot stale `USB2BLE Gamepad` and
  `Xbox Wireless Controller` Bluetooth entries, connected `USB2BLE Gamepad`, and
  clicked Arm on the browser witness page.

## Commands Run

```text
python3 tools/virtual_input_bridge_witness.py --port /dev/cu.usbmodem5B5E0200881 --persona generic --scenarios all --duration-per-scenario 0.75 --witness-port 8820 --no-human --assume-bluetooth-connected --auto-arm --no-physical-input

python3 tools/serial_command.py --port /dev/cu.usbmodem5B5E0200881 --timeout 3 GET_STATUS GET_BRIDGE_STATUS GET_VIRTUAL_INPUT_STATUS FORGET_BLE_BONDS

espflash reset --chip esp32s3 --port /dev/cu.usbmodem5B5E0200881 --non-interactive

python3 tools/virtual_input_bridge_witness.py --port /dev/cu.usbmodem5B5E0200881 --persona generic --scenarios all --duration-per-scenario 0.75 --witness-port 8821 --browser-timeout 20 --no-human --assume-bluetooth-connected --auto-arm --no-physical-input

python3 tools/persona_switch_hygiene.py --port /dev/cu.usbmodem5B5E0200881 --sequence generic,xbox --witness-port-start 8830 --duration-per-scenario 0.6 --no-human

python3 tools/virtual_input_bridge_witness.py --port /dev/cu.usbmodem5B5E0200881 --persona generic --scenarios all --duration-per-scenario 0.75 --witness-port 8842 --browser-timeout 20 --no-human --assume-bluetooth-connected --auto-arm --no-physical-input --run-prefix generic_virtual_bridge_clean

python3 tools/virtual_input_bridge_witness.py --port /dev/cu.usbmodem5B5E0200881 --persona generic --scenarios all --duration-per-scenario 0.75 --witness-port 8843 --browser-timeout 20 --no-human --assume-bluetooth-connected --auto-arm --no-physical-input --run-prefix generic_virtual_bridge_clean --browser-wake-self-test
```

## Diagnostic Results

| Run | Persona | Target BLE | Browser expected slot | Stale captures | Published delta | Result |
| --- | --- | --- | --- | --- | --- | --- |
| Prior artifact analysis | Generic | Connected | Stale Xbox-shaped standard slot detected | yes | n/a | false Generic browser evidence identified |
| Strict Generic replay | Generic | Connected | Not seen | 0 | 58 | fail: no acceptable Generic browser slot |
| Bond-clear/reset Generic replay | Generic | Advertising / not connected | Not seen | 0 | 0 | fail: host did not reconnect automatically |
| No-human hygiene sequence | Generic -> Xbox | Not connected for both runs | Not seen | 0 | 0 for both | fail: no false pass, reconnect blocked |
| Manual cache cleanup + Generic reconnect | Generic | Connected | Not seen | 0 | 69 | fail: macOS HID connected, Chrome Gamepad API captured zero samples |
| Manual cache cleanup + Generic self-test wake | Generic | Connected | Not seen | 0 | 68 | fail: self-test wake sent, Chrome Gamepad API still captured zero samples |

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

The manual cleanup follow-up captured a narrower blocker. Before cleanup, macOS
still reported `USB2BLE Gamepad` as connected while the target was advertising
and not connected. After Alex removed stale Bluetooth entries and reconnected
only `USB2BLE Gamepad`, the target reported a real Generic BLE connection:

```text
STATUS:ble=Connected;profile=none;persona=generic_gamepad;bonds=false;
```

macOS also exposed the Generic BLE HID device to the HID stack:

```text
Bluetooth Low Energy AppleUserHIDEventService USB2BLE Gamepad
Bluetooth Low Energy IOHIDResource USB2BLE Gamepad
VendorID=0x303a ProductID=0x4001 PrimaryUsagePage=1 PrimaryUsage=5
GameControllerCapabilities=...
```

Even with that OS-level HID visibility, the strict Chrome witness captured no
Gamepad API samples:

```text
target_ble_connected=true
browser_expected_gamepad_seen=false
browser_capture_count=0
browser_stale_capture_count=0
published_delta=69
```

After a Generic BLE self-test wake before browser capture, the result remained
the same:

```text
browser_wake_self_test_sent=true
target_ble_connected=true
browser_capture_count=0
published_delta=68
```

## Artifacts

- `target/persona-switching-diagnosis/persona_switching_20260531T183201Z`
- `target/virtual-input-bridge-witness/generic_virtual_bridge_20260531T183210Z`
- `target/virtual-input-bridge-witness/generic_virtual_bridge_20260531T183428Z`
- `target/persona-switching-hygiene/persona_switch_20260531T183637Z`
- `target/virtual-input-bridge-witness/generic_virtual_bridge_20260531T183637Z`
- `target/virtual-input-bridge-witness/xbox_virtual_bridge_20260531T183821Z`
- `target/persona-switching-hygiene/manual_cache_cleanup_20260531T191922Z`
- `target/virtual-input-bridge-witness/generic_virtual_bridge_clean_20260531T192038Z`
- `target/virtual-input-bridge-witness/generic_virtual_bridge_clean_20260531T192606Z`
- `target/virtual-input-bridge-witness/generic_virtual_bridge_clean_20260531T193016Z`
- `target/virtual-input-bridge-witness/generic_virtual_bridge_clean_20260531T193354Z`

## Conclusion

The tooling now distinguishes stale browser Gamepad API slots from the active
target persona. This prevents a stale Xbox-shaped `STANDARD GAMEPAD` slot from
being counted as Generic browser evidence.

Generic virtual browser replay remains unproven in this diagnostic. On this
host, a fully automated no-human persona switch did not restore a clean Generic
Gamepad API slot after the Xbox run. Manual macOS Bluetooth cache cleanup can
restore a target/macOS Generic BLE HID connection, but Chrome still captured no
Gamepad API samples from the connected Generic device in this session.

The next technical step is a focused Generic Chrome/Gamepad API exposure
diagnostic that starts from this narrower state: connected Generic BLE HID in
macOS `hidutil`/`ioreg`, target bridge publishing, but no Chrome Gamepad API
samples.

## Limitations

- This is virtual normalized-input diagnostic evidence, not physical USB
  movement evidence.
- It does not prove Generic virtual browser replay success.
- Manual Bluetooth cache cleanup and reconnect were required for the follow-up
  Generic connection; fully automatic persona switching remains unproven.
- It does not prove BLE bond persistence, reconnect robustness, or product-ready
  persona switching.
- It does not prove broad host/browser support.
- It does not prove Xbox console, proprietary Xbox Wireless, Windows, Android,
  iOS, Linux, native game/app, or final Flight Pack calibration compatibility.
