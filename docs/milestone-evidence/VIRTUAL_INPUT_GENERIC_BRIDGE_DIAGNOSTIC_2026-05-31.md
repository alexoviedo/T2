# Virtual Input Generic Bridge Diagnostic - 2026-05-31

Status: diagnostic evidence. This does not prove a complete Generic virtual
browser replay witness.

## Summary

The Generic virtual replay evaluator was updated so endpoint/release scenarios
are checked with explicit semantics instead of isolated raw delta checks:

- `throttle_max -> throttle_min` is evaluated as a complementary endpoint pair.
- `left_toe_pressed -> left_toe_released` and
  `right_toe_pressed -> right_toe_released` are evaluated as release
  transitions.
- Raw and semantic results are both recorded.

The rerun used a clean temporary Chrome profile, which is the browser mode that
previously restored Generic Gamepad API exposure. Chrome exposed
`USB2BLE Gamepad (Vendor: 303a Product: 4001)` with empty `mapping`, 10 axes,
and 16 buttons. The target reported BLE connected, virtual input enabled during
the run, and bridge publication increased. The Generic throttle endpoint pair
was host-visible on Chrome A2.

The run still did not pass the complete Generic virtual bridge witness because
Chrome did not produce fresh Gamepad API samples for virtual rudder, toe, or
stick frames after the throttle pair, even though the target mapping/report
responses and bridge counters changed for those scenarios.

## Context

- Date/time: 2026-05-31.
- Commit: `79ed0d004f7dab971341e58f85585facebc8eef9` plus working-tree changes
  described by this evidence.
- Serial port: `/dev/cu.usbmodem5B5E0200881`.
- Host: MacBook Pro 15-inch 2016 on macOS 12.7.x.
- Browser: Google Chrome `148.0.7778.179`, clean temporary profile.
- Active persona: `generic_gamepad`.
- Runtime config: `flight-pack-generic` / `custom_runtime`.
- Input source: diagnostic virtual normalized-input replay.
- Human physical input required: no.
- Human GUI/Bluetooth action during this run: no.

## Commands Run

```text
python3 tools/virtual_input_bridge_witness.py --port /dev/cu.usbmodem5B5E0200881 --persona generic --scenarios all --duration-per-scenario 0.8 --witness-port 8864 --browser-timeout 10 --no-human --assume-bluetooth-connected --auto-arm --no-physical-input --run-prefix generic_virtual_bridge_pass --chrome-mode temp-profile
```

Supporting checks while developing the evaluator:

```text
python3 -m py_compile tools/virtual_input_bridge_witness.py tools/chrome_gamepad_probe.py tools/gamepad_witness/server.py
python3 -m unittest tools.tests.test_ble_compat_tools
```

## Scenario Result

| Scenario | Expected browser control | Semantic result | Notes |
| --- | --- | --- | --- |
| `throttle_max` | A2 / Generic `z` positive | PASS | Chrome sample reached A2 `1.0`. |
| `throttle_min` | A2 / Generic `z` negative | PASS | Chrome sample moved A2 `1.0 -> -1.0`. |
| `rudder_left` | A3 / Generic `rx` positive | FAIL | Target report changed, but no fresh browser sample was captured. |
| `rudder_right` | A3 / Generic `rx` negative | FAIL | Target report changed, but no fresh browser sample was captured. |
| `left_toe_pressed` | A4 / Generic `ry` positive | FAIL | Target report changed, but no fresh browser sample was captured. |
| `left_toe_released` | A4 / Generic `ry` release | FAIL | Target report changed, but browser remained at last captured throttle sample. |
| `right_toe_pressed` | A5 / Generic `rz` positive | FAIL | Target report changed, but no fresh browser sample was captured. |
| `right_toe_released` | A5 / Generic `rz` release | FAIL | Target report changed, but browser remained at last captured throttle sample. |
| `stick_left/right` | A0 / Generic `x` | FAIL | Target report changed, but no fresh browser sample was captured. |
| `stick_forward/back` | A1 / Generic `y` | FAIL | Target report changed, but no fresh browser sample was captured. |

Summary fields from `summary.json`:

```text
virtual_bridge_witness_passed=false
target_ble_connected=true
browser_expected_gamepad_seen=true
browser_stale_capture_count=0
browser_capture_count=52
published_delta=87
matched_expected_count=2
expected_count=12
human_prompted=false
target_errors=[]
```

## Transcript Excerpts

Chrome exposed the expected Generic browser slot:

```text
id=USB2BLE Gamepad (Vendor: 303a Product: 4001)
mapping=
axes_count=10
buttons_count=16
stale=false
expected_match=true
```

The target mapping/report path changed for a virtual rudder frame:

```text
PUBLISH_VIRTUAL_INPUT_FRAME rudder_left
GET_GENERIC_GAMEPAD_MAPPING
...target=rx,value=axis:32767,reason=profile_rule...
GET_GENERIC_GAMEPAD_REPORT
ENCODED_REPORT:persona=generic_gamepad;report_id=1;bytes=000008000000000180ff7f01800180;
GET_BRIDGE_STATUS
BRIDGE_STATUS:enabled=true;persona=generic_gamepad;...published=1345;...last_error=none;
```

The target mapping/report path changed for a virtual toe frame:

```text
PUBLISH_VIRTUAL_INPUT_FRAME left_toe_pressed
GET_GENERIC_GAMEPAD_MAPPING
...target=ry,value=axis:-32768,reason=profile_rule_inverted...
GET_GENERIC_GAMEPAD_REPORT
ENCODED_REPORT:persona=generic_gamepad;report_id=1;bytes=0000080000000001800000ff7f0180;
```

## Artifacts

- `target/generic-virtual-evaluator-diagnosis/generic_virtual_eval_20260531T205048Z`
- `target/virtual-input-bridge-witness/generic_virtual_bridge_pass_20260531T205546Z`
- `target/virtual-input-bridge-witness/generic_virtual_bridge_pass_20260531T205546Z/summary.json`
- `target/virtual-input-bridge-witness/generic_virtual_bridge_pass_20260531T205546Z/scenario_results.json`
- `target/virtual-input-bridge-witness/generic_virtual_bridge_pass_20260531T205546Z/serial_transcript.txt`
- `target/virtual-input-bridge-witness/generic_virtual_bridge_pass_20260531T205546Z/gamepad-witness/gamepad_witness_20260531T205547Z.jsonl`

## Conclusion

The original evaluator issue is fixed: paired endpoint semantics correctly
validate the Generic throttle min/max transition. The remaining blocker is not
physical input, target-side virtual input, mapping, encoding, bridge
publication, or stale Xbox slot filtering. The remaining blocker is narrower:
Chrome/macOS exposed the Generic device and consumed the virtual throttle
transition, but did not surface later virtual Generic report changes for A0,
A1, A3, A4, or A5 in this run.

Do not promote this to a Generic virtual bridge success witness. The next
technical action should isolate whether Chrome/macOS is suppressing later
Generic notifications, whether the witness page needs a lower-level CDP polling
path, or whether Generic BLE notification readiness/subscription state differs
from the earlier real-input Generic evidence.

## Limitations

- This is virtual normalized-input diagnostic evidence, not physical USB
  movement evidence.
- It does not prove complete Generic virtual browser replay.
- It does not replace the already checked-in real USB HID parser/input
  evidence.
- It does not prove broad browser/host support, BLE bond persistence, automatic
  persona switching, Windows, Android, iOS, Linux, native game/app behavior, or
  final Flight Pack calibration quality.
