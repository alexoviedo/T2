# Windows Xbox XInput Witness - 2026-06-04

Status: single-persona Windows Xbox-path witness from Alex's Windows PC. This
run proves that, after clean Windows Bluetooth cache setup and manual Windows
Settings pairing, USB2BLE's Xbox BLE-compatible persona appears as
`Xbox Wireless Controller`, exposes HID `045e:0b13`, connects to XInput slot 0,
and accepts deterministic plus virtual Flight Pack Xbox reports through XInput.
It also records a Windows Game Controllers control-panel (`joy.cpl`) app smoke
where Alex observed axis/trigger movement during the corrected live virtual
sequence.

This is not broad Windows compatibility, broad game compatibility, Xbox console
compatibility, proprietary Xbox Wireless compatibility, BLE bond persistence,
physical HOTAS movement, or final calibration evidence.

## Context

- Date/time: 2026-06-04 around 14:11-14:36 Mountain time.
- Commit: `d9f697fb1412d5cdfa19efabc9b8e7f44aa427a1`
- Branch: `main`
- CI gate: latest GitHub Actions run for `main` was green before hardware work:
  <https://github.com/alexoviedo/T2/actions/runs/26976030051>
- Windows host: Alex's Windows 11 PC. `Get-ComputerInfo`/registry reported
  product name `Windows 10 Home`, display version `25H2`, build `26200.8457`.
- Selected serial port: `COM3`
- Serial device: WCH CH343, `USB\VID_1A86&PID_55D3\5B5E020088`
- Witness artifact root:
  `target/windows-xbox-game-witness/windows_xbox_game_20260604_141157`
- Controller-panel artifact root:
  `target/windows-game-compatibility/joy_cpl_xbox_20260604_142838`

No firmware was flashed in this chunk. No physical HOTAS controls were moved.

## Repo And Validation Gate

The run started from clean, synced `main`:

```text
BRANCH=main
HEAD=d9f697fb1412d5cdfa19efabc9b8e7f44aa427a1
UPSTREAM=d9f697fb1412d5cdfa19efabc9b8e7f44aa427a1
STATUS_COUNT=0
```

Local no-hardware validation passed before hardware work:

```text
.\scripts\validate_no_hardware.ps1
python tools\check_evidence_docs.py --verbose
python tools\check_persona_acceptance.py
python tools\check_xbox_ble_profile.py
git diff --check
```

## Target Topology

The target was autodetected as `COM3`, WCH CH343. The practical RJ12 Flight Pack
topology was present:

```text
USB_STATUS:devices=3;interfaces=2;
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b10a|id=3,vid=044f,pid=b687
```

This proves target-side USB topology only. It does not prove physical HOTAS
movement.

## Identity Strategy

`legacy_public` remained the default strategy in the target-reported strategy
list. For this single-persona Xbox witness, the explicit experimental strategy
was selected to avoid the previously observed Generic/U6/Xbox address collision:

```text
SET_BLE_IDENTITY_STRATEGY persona_static_random_experimental
START_BLE_XBOX_CONTROLLER
```

Target identity:

```text
strategy=persona_static_random_experimental
active_persona=xbox_wireless_controller
active_variant=xbox_compatibility
base_address=90:70:69:07:0D:7E
current_address=CB:B3:AE:FA:FC:EF
address_type=static_random
identity_applied=true
```

The strategy remains explicit and experimental. It was not made default.

## Advertising And Pairing

After manual Windows cache cleanup, the target advertised:

```text
device_name=Xbox Wireless Controller
advertised_uuids=1812
own_addr_type=static_random
identity_strategy=persona_static_random_experimental
current_addr=CB:B3:AE:FA:FC:EF
derived_addr=CB:B3:AE:FA:FC:EF
```

The native Windows BLE watcher saw the advertisement:

```text
expected_name: Xbox Wireless Controller
addresses: CB:B3:AE:FA:FC:EF
match_count: 94
rssi_min: -32
rssi_max: -28
```

Windows cache cleanup and pairing were not fully automated:

- USB2BLE-related old Xbox nodes were safely identified by derived address and
  HID VID/PID, but `pnputil /remove-device` returned `Access is denied`.
- Alex removed USB2BLE-related Bluetooth entries in Windows Settings.
- Automated WinRT pairing discovered `Xbox Wireless Controller` and reported
  `can_pair=true`, but the pair attempt returned `pair_status=FAILED`.
- Alex paired/connected `Xbox Wireless Controller` through Windows Settings.

After manual pairing, target state was:

```text
STATUS:ble=Connected;profile=none;persona=xbox_wireless_controller;bonds=false;
```

Target `bonds=false` means this run does not prove BLE bond persistence.

## Windows HID And XInput Identity

Windows PnP/HID showed the Xbox-like BLE HID identity:

```text
Bluetooth: Xbox Wireless Controller
InstanceId: BTHLE\DEV_CBB3AEFAFCEF\...

HIDClass: HID-compliant game controller
InstanceId: HID\{00001812-0000-1000-8000-00805F9B34FB}&DEV&VID_045E&PID_0B13&REV_0515&CBB3AEFAFCEF&IG_00\...

HIDClass: Bluetooth LE XINPUT compatible input device
InstanceId: BTHLEDEVICE\{00001812-0000-1000-8000-00805F9B34FB}_DEV_VID&02045E_PID&0B13_REV&0515_CBB3AEFAFCEF\...
```

`tools/windows_gamepad_probe.py` showed XInput slot 0 connected:

```text
xinput dll: xinput1_4
connected_count: 1
slot 0: connected=true, buttons=0, left_trigger=0, right_trigger=0
slots 1-3: not connected
```

Raw Input enumeration saw the HID device path but did not classify it as a
controller-like Raw Input device. GameInput was not exercised by this probe.

## Deterministic Xbox Reports

The bridge was stopped for direct deterministic persona reports so bridge
publication would not overwrite test reports. All sampled scenarios kept XInput
slot 0 connected.

| Scenario | XInput observation |
| --- | --- |
| `neutral` | buttons `0`, triggers `0/0`, sticks near neutral |
| `left_stick_left` | left thumb `-32768,-1` |
| `left_stick_right` | left thumb `32767,-1` |
| `left_stick_up` | left thumb `0,32767` |
| `left_stick_down` | left thumb `0,-32768` |
| `right_stick_left` | right thumb `-32768,-1` |
| `right_stick_right` | right thumb `32767,-1` |
| `right_stick_up` | right thumb `0,32767` |
| `right_stick_down` | right thumb `0,-32768` |
| `left_trigger_max` | left trigger `255` |
| `right_trigger_max` | right trigger `255` |
| `button_a` | buttons `4096` |
| `button_b` | buttons `8192` |
| `button_x` | buttons `16384` |
| `button_y` | buttons `32768` |
| `button_lb` | buttons `256` |
| `button_rb` | buttons `512` |
| `button_view` | buttons `32` |
| `button_menu` | buttons `16` |
| `hat_up` | buttons `1` |
| `hat_right` | buttons `8` |
| `hat_down` | buttons `2` |
| `hat_left` | buttons `4` |

This proves deterministic Xbox reports move the expected XInput fields on this
PC. It does not prove a real game will consume the same controls.

## Virtual Flight Pack Xbox Mapping

Virtual normalized input was used, not physical USB movement:

```text
START_VIRTUAL_INPUT
PUBLISH_VIRTUAL_INPUT_FRAME neutral
START_BRIDGE
```

The practical Xbox mapping under test:

- stick -> XInput left stick
- RJ12 rudder -> XInput right stick X
- left toe -> left trigger
- right toe -> right trigger
- TWCS throttle intentionally unmapped for this Xbox practical profile

All sampled scenarios kept XInput slot 0 connected:

| Virtual scenario | XInput observation |
| --- | --- |
| `neutral` | buttons `0`, triggers `0/0`, sticks near neutral |
| `stick_left` | left thumb `-32768,-1` |
| `stick_right` | left thumb `32767,-1` |
| `stick_forward` | left thumb `0,32767` |
| `stick_back` | left thumb `0,-32768` |
| `rudder_left` | right thumb `32767,-1` |
| `rudder_right` | right thumb `-32768,-1` |
| `left_toe_released` | left trigger `0` |
| `left_toe_pressed` | left trigger `255` |
| `right_toe_released` | right trigger `0` |
| `right_toe_pressed` | right trigger `255` |

Bridge counters stayed healthy and `last_error=none`. This proves virtual
normalized-input mapping through the Xbox persona to Windows XInput on this PC.
It does not prove physical HOTAS movement.

## joy.cpl Control-Panel App Smoke

After the XInput gates passed, `joy.cpl` was launched as the lowest-friction
real Windows controller-panel app witness.

Computer Use automation was unavailable in this session (`native pipe path is
unavailable`), so the allowed manual observation fallback was used. Alex opened
`Xbox Wireless Controller` Properties in the Game Controllers window. Before
the corrected live sequence, Alex reported no control changes. A first attempted
live script had a PowerShell argument-passing bug and did not send serial
commands, so that observation is treated only as pre-sequence baseline.

The corrected live virtual sequence then sent serial commands and captured
XInput samples for stick, rudder, and toe scenarios. During that corrected
sequence, Alex reported that the `joy.cpl` Properties page showed movement.

Corrected live sequence examples:

| Corrected live scenario | XInput observation during `joy.cpl` run |
| --- | --- |
| `stick_left` | left thumb `-32768,-1` |
| `stick_right` | left thumb `32767,-1` |
| `stick_forward` | left thumb `0,32767` |
| `stick_back` | left thumb `0,-32768` |
| `rudder_left` | right thumb `32767,-1` |
| `rudder_right` | right thumb `-32768,-1` |
| `left_toe_pressed` | left trigger `255` |
| `left_toe_released` | left trigger `0` |
| `right_toe_pressed` | right trigger `255` |
| `right_toe_released` | right trigger `0` |

This is a Windows controller-panel app smoke, not a game compatibility claim.

## Artifacts

- `target/windows-xbox-game-witness/windows_xbox_game_20260604_141157/repo_state.txt`
- `target/windows-xbox-game-witness/windows_xbox_game_20260604_141157/branch_state.txt`
- `target/windows-xbox-game-witness/windows_xbox_game_20260604_141157/ci_status.txt`
- `target/windows-xbox-game-witness/windows_xbox_game_20260604_141157/phase1_local_validation.txt`
- `target/windows-xbox-game-witness/windows_xbox_game_20260604_141157/serial_discovery.txt`
- `target/windows-xbox-game-witness/windows_xbox_game_20260604_141157/target_baseline.txt`
- `target/windows-xbox-game-witness/windows_xbox_game_20260604_141157/usb_topology.txt`
- `target/windows-xbox-game-witness/windows_xbox_game_20260604_141157/cache_before.txt`
- `target/windows-xbox-game-witness/windows_xbox_game_20260604_141157/cache_removal_attempt.txt`
- `target/windows-xbox-game-witness/windows_xbox_game_20260604_141157/cache_after.txt`
- `target/windows-xbox-game-witness/windows_xbox_game_20260604_141157/xbox_pairing/`
- `target/windows-xbox-game-witness/windows_xbox_game_20260604_141157/xinput_deterministic/`
- `target/windows-xbox-game-witness/windows_xbox_game_20260604_141157/xbox_virtual_mapping/`
- `target/windows-xbox-game-witness/windows_xbox_game_20260604_141157/evidence_summary_tables.txt`
- `target/windows-game-compatibility/joy_cpl_xbox_20260604_142838/joy_cpl_launch.txt`
- `target/windows-game-compatibility/joy_cpl_xbox_20260604_142838/joy_cpl_live_virtual_sequence_corrected.txt`
- `target/windows-game-compatibility/joy_cpl_xbox_20260604_142838/joy_cpl_corrected_live_xinput_summary.json`
- `target/windows-game-compatibility/joy_cpl_xbox_20260604_142838/operator_observation.txt`

## Conclusion

For the single-persona Xbox BLE-compatible path on Alex's Windows PC:

- Windows discovered `Xbox Wireless Controller` at `CB:B3:AE:FA:FC:EF`.
- Manual Windows Settings pairing connected the device.
- Windows exposed HID `045e:0b13` and the Bluetooth LE XInput-compatible input
  device.
- XInput slot 0 connected.
- Deterministic Xbox report scenarios drove useful sticks, triggers, buttons,
  and D-pad fields through XInput.
- Virtual Flight Pack Xbox mapping drove stick, rudder, and toe-brake mappings
  through XInput.
- `joy.cpl` Properties showed movement during the corrected virtual sequence.

`persona_static_random_experimental` should remain explicit and non-default.
This witness did not retest cache-free persona switching and does not supersede
the earlier finding that cache-free Generic/U6/Xbox switching remains unproven.

## Limitations

- Evidence is from Alex's Windows PC only.
- Manual Windows Settings cache removal and pairing were required.
- Automated WinRT pairing failed.
- BLE bond persistence and reconnect behavior were not proven.
- Virtual input does not prove physical HOTAS movement.
- `joy.cpl` is a Windows controller-panel app smoke, not a real game
  compatibility claim.
- No Steam, installed game, browser game, or external/native game was tested.
- Broad Windows compatibility is not claimed.
- Xbox console compatibility and proprietary Xbox Wireless compatibility are
  not claimed.
- Final calibration quality and physical-control feel are not proven.
