# Virtual Input Xbox Bridge Witness - 2026-05-30

Status: host-visible virtual normalized-input bridge evidence. This proves the
diagnostic virtual input path can drive the refined Flight Pack Xbox mapping
through the live bridge and into macOS Chrome's Gamepad API without physical
HOTAS/pedal movement.

This is not physical USB movement evidence. Real USB HID reading and practical
RJ12 input labels are covered by separate checked-in evidence.

## Summary

USB2BLE was run on the ESP32-S3 with the `flight-pack-xbox` runtime config and
virtual normalized-input mode enabled. The witness published named Flight Pack
scenarios through:

```text
virtual normalized input -> mapping engine -> Xbox report encoder -> BLE live bridge -> macOS Chrome Gamepad API
```

Chrome observed the connected controller as:

```text
browser_id=USB2BLE Gamepad (STANDARD GAMEPAD)
browser_mapping=standard
browser_axes_count=4
browser_buttons_count=18
```

The browser identity string is not treated as an Xbox-branding claim. The
compatibility claim here is scoped to Chrome's standard Gamepad API layout for
the refined Xbox-compatible BLE persona.

## Context

- Date/time: 2026-05-30T22:34:43Z
- Commit: `4d483c420b8af4af934a68615bdc4173d706eac4` plus working-tree changes
  described by this evidence
- Serial port: `/dev/cu.usbmodem5B5E0200881`
- Host: macOS 12.7.5
- Browser: Google Chrome 148.0.7778.179, local Gamepad witness page
- Active persona: `xbox_wireless_controller`
- Runtime config: `flight-pack-xbox` / `custom_runtime`
- Virtual input mode: enabled during the scenario run, then stopped
- Human physical input required: no
- Human browser/Bluetooth action required during this run: no

## Commands Run

```text
python3 tools/virtual_input_bridge_witness.py --port /dev/cu.usbmodem5B5E0200881 --persona xbox --scenarios all --duration-per-scenario 0.75 --witness-port 8797 --no-human --assume-bluetooth-connected --auto-arm --no-physical-input
```

Supporting checks while developing the witness:

```text
python3 -m py_compile tools/virtual_input_bridge_witness.py tools/serial_command.py tools/asap_demo_rehearsal.py
python3 -m unittest tools.tests.test_ble_compat_tools
```

## Scenario Result

| Scenario | Expected browser control | Observed result |
| --- | --- | --- |
| `stick_left` | A0 left stick X negative | PASS: A0 `0.0 -> -1.0` |
| `stick_right` | A0 left stick X positive | PASS: A0 `0.0 -> 1.0` |
| `stick_forward` | A1 left stick Y negative | PASS: A1 `0.0 -> -1.0` |
| `stick_back` | A1 left stick Y positive | PASS: A1 `0.0 -> 1.0` |
| `rudder_left` | A2 right stick X positive | PASS: A2 `0.0 -> 1.0` |
| `rudder_right` | A2 right stick X negative | PASS: A2 `0.0 -> -1.0` |
| `left_toe_pressed` | B6 left trigger | PASS: B6 `0.0 -> 1.0` |
| `right_toe_pressed` | B7 right trigger | PASS: B7 `0.0 -> 1.0` |

Summary fields from `summary.json`:

```text
virtual_bridge_witness_passed=true
target_ble_connected=true
browser_capture_count=19
matched_expected_count=8
expected_count=8
published_delta=57
human_prompted=false
target_errors=[]
```

## Transcript Excerpts

The target started the refined Xbox runtime config and reported BLE connected:

```text
GET_CONFIG_STATUS
CONFIG_STATUS:valid=true;source=runtime;persona=xbox_wireless_controller;profile=custom_runtime;mappings=18;import_active=false;last_error=none;
START_CONFIGURED
CONFIG_ACTION:action=start_configured;state=ok;detail=persona=xbox_wireless_controller;bridge=false;;
GET_STATUS
STATUS:ble=Connected;profile=none;persona=xbox_wireless_controller;bonds=false;
```

Virtual input mode drove the same mapping/report path used by the live bridge:

```text
PUBLISH_VIRTUAL_INPUT_FRAME rudder_left
XBOX_GAMEPAD_MAPPING:profile=custom_runtime;persona=xbox_wireless_controller;entries=6;mappings=...target=right_x,value=axis:32767...
ENCODED_REPORT:persona=xbox_wireless_controller;report_id=1;bytes=00800080ffff00800000000000000000;

PUBLISH_VIRTUAL_INPUT_FRAME left_toe_pressed
XBOX_GAMEPAD_MAPPING:profile=custom_runtime;persona=xbox_wireless_controller;entries=6;mappings=...target=left_trigger,value=axis:-32768...
ENCODED_REPORT:persona=xbox_wireless_controller;report_id=1;bytes=0080008000800080ff03000000000000;
```

## Artifacts

- `target/virtual-input-bridge-witness/xbox_virtual_bridge_20260530T223443Z`
- `target/virtual-input-bridge-witness/xbox_virtual_bridge_20260530T223443Z/summary.json`
- `target/virtual-input-bridge-witness/xbox_virtual_bridge_20260530T223443Z/scenario_results.json`
- `target/virtual-input-bridge-witness/xbox_virtual_bridge_20260530T223443Z/serial_transcript.txt`
- `target/virtual-input-bridge-witness/xbox_virtual_bridge_20260530T223443Z/gamepad-witness/gamepad_witness_20260530T223444Z.jsonl`

Additional target-only Generic virtual replay regression artifact:

- `target/virtual-input-bridge-witness/generic_virtual_bridge_20260530T223807Z`

## Conclusion

The refined Flight Pack Xbox mapping is host-visible on macOS Chrome when driven
by diagnostic virtual normalized-input replay. This closes the no-physical-input
Xbox live-bridge gap for the mapped controls tested here:

- stick X/Y -> Chrome A0/A1
- RJ12 rudder -> Chrome A2
- left toe brake -> Chrome B6
- right toe brake -> Chrome B7

## Limitations

- This is virtual normalized-input evidence, not physical USB movement evidence.
- It does not replace the real USB HID parser/input witnesses already checked
  into the repo.
- It does not prove Xbox console compatibility or proprietary Xbox Wireless.
- It does not prove Windows, Android, iOS, Linux, native game/app, broad browser,
  reconnect, BLE bond persistence, or final Flight Pack calibration quality.
- The Generic virtual browser rerun in this chunk was diagnostic only: target
  mapping/report/bridge publication passed, but Chrome still exposed the prior
  standard/Xbox-shaped Gamepad API slot during that automated pass.
