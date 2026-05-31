# Generic Chrome Gamepad Exposure Diagnostic - 2026-05-31

Status: diagnostic evidence. This narrows the current Generic virtual browser
replay blocker to Chrome profile/session Gamepad API state. It does not prove a
complete Generic virtual bridge witness.

## Summary

Earlier checked-in evidence proves that Chrome on this Mac can expose USB2BLE's
Generic BLE Gamepad as `USB2BLE Gamepad (Vendor: 303a Product: 4001)` with an
empty Gamepad API `mapping`, 10 axes, and 16 buttons. The current post-persona
switching run had a narrower failure: macOS HID and the target both saw the
Generic BLE device as connected, and the target bridge published virtual
Generic reports, but the existing Chrome profile returned no Gamepad API
entries.

A direct raw Chrome probe confirmed that the existing Chrome profile/session
returned no gamepads. The same connected target, tested with a clean temporary
Chrome profile, exposed the expected Generic gamepad identity and shape. This
supports the conclusion that the blocker is stale/poisoned Chrome profile or
session state, not Generic target advertising, target-side virtual input,
mapping, BLE publish, or macOS HID visibility.

## Context

- Date/time: 2026-05-31.
- Commit: current post-`v0.1.0-alpha` working tree.
- Serial port: `/dev/cu.usbmodem5B5E0200881`.
- Host: MacBook Pro 15-inch 2016 on macOS 12.7.x.
- Browser: Google Chrome `148.0.7778.179`.
- Persona: `generic_gamepad`.
- Input source: diagnostic virtual normalized-input replay.
- Human physical input required: no.
- Human GUI action during this diagnostic: none.

## Comparison

| Evidence path | Browser result |
| --- | --- |
| Earlier refined Generic axis exposure | 2,415 browser samples; 10 axes; Generic `z/rx/ry/rz` visible as A2/A3/A4/A5 |
| Earlier refined Generic 300-second soak | Browser connected start/end; 10 axes; bridge published for 300 seconds |
| Earlier self-hosted Sky Run smoke | `USB2BLE Gamepad (Vendor: 303a Product: 4001)` consumed by the browser game |
| Current failed strict Generic virtual run | Target connected and published, but Chrome witness captured zero samples |
| Direct probe, existing Chrome profile | 115 raw samples, zero connected gamepads |
| Direct probe, temporary Chrome profile | 99 raw samples, 47 with `USB2BLE Gamepad (Vendor: 303a Product: 4001)`, empty mapping, 10 axes, 16 buttons |

## Commands Run

```text
python3 tools/chrome_gamepad_probe.py --port 8850 --out-dir target/generic-chrome-exposure-diagnosis/generic_chrome_exposure_20260531T201950Z/existing_profile --duration 12 --sample-ms 100 --session-label generic-existing-profile --chrome-mode existing-profile --auto-gesture

python3 tools/chrome_gamepad_probe.py --port 8851 --out-dir target/generic-chrome-exposure-diagnosis/generic_chrome_exposure_20260531T201950Z/temp_profile --duration 12 --sample-ms 100 --session-label generic-temp-profile --chrome-mode temp-profile --auto-gesture

python3 tools/virtual_input_bridge_witness.py --port /dev/cu.usbmodem5B5E0200881 --persona generic --scenarios all --duration-per-scenario 0.75 --witness-port 8852 --browser-timeout 20 --no-human --assume-bluetooth-connected --auto-arm --no-physical-input --run-prefix generic_virtual_bridge_fixed --chrome-mode temp-profile
```

The target was also queried with:

```text
GET_INFO
GET_STATUS
GET_BLE_ADVERTISING_INFO
GET_BLE_COMPAT_PROFILE
GET_BRIDGE_STATUS
GET_VIRTUAL_INPUT_STATUS
GET_GENERIC_GAMEPAD_REPORT
```

## Diagnostic Results

The existing Chrome profile returned no Gamepad API entries:

```text
sample_count=115
samples_with_gamepads=0
gamepads=[null,null,null,null]
document_has_focus=true
has_get_gamepads=true
```

The temporary Chrome profile exposed the expected Generic device:

```text
id=USB2BLE Gamepad (Vendor: 303a Product: 4001)
mapping=
axes_count=10
buttons_count=16
generic_gamepad_seen=true
samples_with_gamepads=47
```

The temp-profile virtual bridge rerun saw the Generic browser slot and target
publication:

```text
browser_expected_gamepad_seen=true
browser_stale_capture_count=0
published_delta=68
```

It was not promoted to a full Generic virtual bridge witness because the
scenario evaluator did not match every requested virtual endpoint in that run.
That is a witness/evaluation follow-up, not evidence that Chrome cannot expose
the Generic device in a clean profile.

## Artifacts

- `target/generic-chrome-exposure-diagnosis/generic_chrome_exposure_20260531T201950Z`
- `target/generic-chrome-exposure-diagnosis/generic_chrome_exposure_20260531T201950Z/existing_profile/chrome_gamepad_probe_20260531T202013Z`
- `target/generic-chrome-exposure-diagnosis/generic_chrome_exposure_20260531T201950Z/temp_profile/chrome_gamepad_probe_20260531T202046Z`
- `target/virtual-input-bridge-witness/generic_virtual_bridge_fixed_20260531T202257Z`

## Conclusion

The Generic Chrome exposure blocker is best explained by stale existing Chrome
profile/session Gamepad API state after persona switching. A clean temporary
Chrome profile restores the previously proven Generic browser identity and
shape without any physical control movement.

Generic virtual browser replay remains not fully proven by this diagnostic.
The next step is to make the virtual bridge witness use clean-profile browser
mode for post-switch Generic runs and refine scenario evaluation so continuous
samples are aligned with each virtual frame before adding a success witness.

## Limitations

- This is virtual normalized-input diagnostic evidence, not physical USB
  movement evidence.
- It does not prove complete Generic virtual bridge replay.
- It does not prove automatic persona switching, reconnect robustness, BLE bond
  persistence, or broad host/browser support.
- It does not prove Windows, Android, iOS, Linux, native game/app, final Flight
  Pack calibration, or physical USB movement behavior.
