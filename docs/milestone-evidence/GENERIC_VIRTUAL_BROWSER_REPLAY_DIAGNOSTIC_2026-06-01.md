# Generic Virtual Browser Replay Diagnostic - 2026-06-01

Status: diagnostic evidence. This does not prove a complete Generic virtual
browser replay witness.

## Summary

The Generic virtual replay evaluator already handles paired endpoint/release
semantics: `throttle_max -> throttle_min` is treated as an endpoint pair, and
toe release scenarios are treated as release-after-press transitions. A fresh
rerun in clean temporary Chrome profile mode confirmed that evaluator semantics
are no longer the main blocker.

Chrome exposed the Generic BLE device as
`USB2BLE Gamepad (Vendor: 303a Product: 4001)` with empty `mapping`, 10 axes,
and 16 buttons. The page was visible and focused, the target reported BLE
connected, virtual normalized input was active, and the bridge published report
changes. However, Chrome only surfaced the first non-neutral Generic axis pair
seen by the fresh browser profile:

- throttle-first run: A2 / Generic `z` passed; A0/A1/A3/A4/A5 did not produce
  fresh browser samples afterward.
- rudder-first run: A3 / Generic `rx` passed; A0/A1/A2/A4/A5 did not produce
  fresh browser samples afterward.

This narrows the blocker to Chrome/macOS Generic Gamepad API update behavior
for this virtual replay sequence, not endpoint evaluator semantics, target-side
virtual input generation, mapping/report encoding, bridge publication, stale
Xbox slot filtering, or physical control movement.

## Context

- Date/time: 2026-06-01.
- Base commit: `e30880c91bb85d528da65fb896eada0cab7963f0`.
- Serial port: `/dev/cu.usbmodem5B5E0200881`.
- Host: MacBook Pro 15-inch 2016 on macOS 12.7.5.
- Browser: Google Chrome `148.0.7778.179`, clean temporary profile.
- Active persona: `generic_gamepad`.
- Runtime config: `flight-pack-generic` / `custom_runtime`.
- Input source: diagnostic virtual normalized-input replay.
- Human physical input required: no.
- Human GUI/Bluetooth action during these reruns: no.

## Tooling Changes

The browser witness now records per-sample browser state:

- `document_visibility`
- `document_has_focus`
- `user_activation_has_been_active`
- `user_activation_is_active`

Temporary Chrome profile launches also disable background timer and renderer
throttling for witness reliability.

## Commands Run

```text
python3 tools/virtual_input_bridge_witness.py --port /dev/cu.usbmodem5B5E0200881 --persona generic --scenarios all --duration-per-scenario 1.0 --witness-port 8871 --browser-timeout 14 --no-human --assume-bluetooth-connected --auto-arm --no-physical-input --run-prefix generic_virtual_bridge_pass --chrome-mode temp-profile

python3 tools/virtual_input_bridge_witness.py --port /dev/cu.usbmodem5B5E0200881 --persona generic --scenarios neutral,rudder_left,rudder_right,left_toe_pressed,left_toe_released,right_toe_pressed,right_toe_released,stick_left,stick_right,stick_forward,stick_back,throttle_max,throttle_min --duration-per-scenario 1.0 --witness-port 8872 --browser-timeout 14 --no-human --assume-bluetooth-connected --auto-arm --no-physical-input --run-prefix generic_virtual_bridge_rudder_first --chrome-mode temp-profile
```

## Scenario Results

### Throttle-First Run

Artifact directory:
`target/virtual-input-bridge-witness/generic_virtual_bridge_pass_20260601T163427Z`

| Scenario group | Expected browser control | Result |
| --- | --- | --- |
| `throttle_max`, `throttle_min` | A2 / Generic `z` | PASS, endpoint pair observed. |
| `rudder_left`, `rudder_right` | A3 / Generic `rx` | FAIL, target report changed but Chrome produced no fresh browser sample. |
| `left_toe_pressed`, `left_toe_released` | A4 / Generic `ry` | FAIL, target report changed but Chrome produced no fresh browser sample. |
| `right_toe_pressed`, `right_toe_released` | A5 / Generic `rz` | FAIL, target report changed but Chrome produced no fresh browser sample. |
| `stick_left/right/forward/back` | A0/A1 / Generic `x/y` | FAIL, target report changed but Chrome produced no fresh browser sample. |

Summary:

```text
browser_id=USB2BLE Gamepad (Vendor: 303a Product: 4001)
browser_mapping=
axes_count=10
buttons_count=16
document_has_focus=true
document_visibility=visible
browser_stale_capture_count=0
published_delta=82
matched_expected_count=2
expected_count=12
virtual_bridge_witness_passed=false
human_prompted=false
```

### Rudder-First Run

Artifact directory:
`target/virtual-input-bridge-witness/generic_virtual_bridge_rudder_first_20260601T163720Z`

| Scenario group | Expected browser control | Result |
| --- | --- | --- |
| `rudder_left`, `rudder_right` | A3 / Generic `rx` | PASS, first non-neutral axis pair observed. |
| `left_toe_pressed`, `left_toe_released` | A4 / Generic `ry` | FAIL, target report changed but Chrome produced no fresh browser sample. |
| `right_toe_pressed`, `right_toe_released` | A5 / Generic `rz` | FAIL, target report changed but Chrome produced no fresh browser sample. |
| `stick_left/right/forward/back` | A0/A1 / Generic `x/y` | FAIL, target report changed but Chrome produced no fresh browser sample. |
| `throttle_max`, `throttle_min` | A2 / Generic `z` | FAIL in this order, target report changed but Chrome produced no fresh browser sample. |

Summary:

```text
browser_id=USB2BLE Gamepad (Vendor: 303a Product: 4001)
browser_mapping=
axes_count=10
buttons_count=16
document_has_focus=true
document_visibility=visible
browser_stale_capture_count=0
published_delta=81
matched_expected_count=2
expected_count=12
virtual_bridge_witness_passed=false
human_prompted=false
```

## Target-Side Excerpts

Rudder frame target mapping/report changed and bridge published:

```text
PUBLISH_VIRTUAL_INPUT_FRAME rudder_left
GET_GENERIC_GAMEPAD_MAPPING
...target=rx,value=axis:32767,reason=profile_rule...
GET_GENERIC_GAMEPAD_REPORT
ENCODED_REPORT:persona=generic_gamepad;report_id=1;bytes=000008000000000180ff7f01800180;
GET_BRIDGE_STATUS
BRIDGE_STATUS:enabled=true;persona=generic_gamepad;...published=1562;...last_error=none;
```

Toe frame target mapping/report changed and bridge published:

```text
PUBLISH_VIRTUAL_INPUT_FRAME left_toe_pressed
GET_GENERIC_GAMEPAD_MAPPING
...target=ry,value=axis:-32768,reason=profile_rule_inverted...
GET_GENERIC_GAMEPAD_REPORT
ENCODED_REPORT:persona=generic_gamepad;report_id=1;bytes=0000080000000001800000ff7f0180;
GET_BRIDGE_STATUS
BRIDGE_STATUS:enabled=true;persona=generic_gamepad;...last_error=none;
```

## Artifacts

- `target/generic-virtual-evaluator-diagnosis/generic_virtual_eval_20260601T163105Z`
- `target/virtual-input-bridge-witness/generic_virtual_bridge_pass_20260601T163123Z`
- `target/virtual-input-bridge-witness/generic_virtual_bridge_pass_20260601T163427Z`
- `target/virtual-input-bridge-witness/generic_virtual_bridge_rudder_first_20260601T163720Z`

## Conclusion

Do not promote Generic virtual browser replay to a success witness yet. The
clean temporary Chrome profile exposes the Generic device and can surface a
first non-neutral Generic axis pair, but it does not reliably surface a full
sequence of virtual Generic report changes.

The next technical action should test one of these paths:

- one fresh browser session per Generic scenario pair, to determine whether
  every axis can be observed independently;
- a lower-level Chrome DevTools Protocol polling path;
- a Generic BLE notification/subscription diagnostic that can confirm whether
  notifications after the first observed axis pair are reaching the host stack.

## Limitations

- This is virtual normalized-input diagnostic evidence, not physical USB
  movement evidence.
- It does not prove complete Generic virtual browser replay.
- It does not replace the already checked-in real USB HID parser/input
  evidence.
- It does not prove broad browser/host support, BLE bond persistence,
  automatic persona switching, Windows, Android, iOS, Linux, native game/app
  behavior, or final Flight Pack calibration quality.
