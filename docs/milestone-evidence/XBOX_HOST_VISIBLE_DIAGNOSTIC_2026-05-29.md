# Xbox Host-Visible Standard-Layout Diagnostic - 2026-05-29

Status: partial diagnostic evidence. This proves USB2BLE's Xbox-compatible BLE
persona is host-visible in macOS Chrome as a connected `mapping="standard"`
Gamepad API device for deterministic Xbox report scenarios. It does not prove a
literal Xbox-like browser `id`, full standard button-layout agreement, refined
Xbox Flight Pack host-visible movement, broad Xbox support, Xbox console support,
proprietary Xbox Wireless support, Windows/Android/iOS/Linux support, or BLE
bond behavior.

## Summary

USB2BLE was tested against macOS 12.7.x and Google Chrome with deterministic
Xbox Report ID 1 payloads sent over the active BLE connection. The target ran
the `xbox_compatibility` profile, `tools/check_xbox_ble_profile.py` reported
`30 pass, 0 warn, 0 fail`, and Chrome exposed a connected Gamepad API device.

Chrome reported the browser identity as:

```text
USB2BLE Gamepad (STANDARD GAMEPAD)
```

That string is not a failure by itself: the Gamepad API can choose the displayed
`id`. The stronger compatibility signal is that Chrome reported
`mapping="standard"` and surfaced deterministic Xbox-style controls at standard
positions for the core controls needed by the refined Flight Pack Xbox mapping:

- left stick X/Y: A0/A1
- right stick X/Y: A2/A3
- left trigger: B6
- right trigger: B7
- A/B buttons: B0/B1
- D-pad directions: B12/B13/B14/B15

The run remains partial because several face/shoulder/menu scenarios did not
land on the expected standard button indices. In particular, X/Y/LB/RB/View/Menu
need follow-up before claiming a complete standard Xbox button layout.

Alex observed that macOS Bluetooth initially showed `USB2BLE`, then presented
the connection as `Xbox Wireless Controller` after connecting. That host identity
transition is useful operator context, but this evidence document relies on the
captured serial and browser artifacts below.

## Target Context

- Date/time: 2026-05-29T22:23:06Z
- Commit: `9517db41943c72b7d8018ee54fc3b41fe12a0c6d`
- Serial port: `/dev/cu.usbmodem5B5E0200881`
- Host: MacBook Pro 15-inch 2016 on macOS 12.7.x
- Browser: Google Chrome 148.0.7778.179, local Gamepad witness page
- Active persona: `xbox_wireless_controller`
- Active compatibility variant: `xbox_compatibility`
- Target BLE identity under test: `Xbox Wireless Controller`

## Commands Run

```text
python3 tools/xbox_host_visible_witness.py --port /dev/cu.usbmodem5B5E0200881 --witness-port 8780 --browser-timeout 8
python3 tools/configure_board.py --port /dev/cu.usbmodem5B5E0200881 preset flight-pack-xbox
python3 tools/configure_board.py --port /dev/cu.usbmodem5B5E0200881 start-configured
python3 tools/serial_command.py --port /dev/cu.usbmodem5B5E0200881 --timeout 4 GET_CONFIG_STATUS GET_XBOX_GAMEPAD_MAPPING GET_XBOX_GAMEPAD_REPORT GET_BRIDGE_STATUS
python3 tools/live_bridge_soak.py --port /dev/cu.usbmodem5B5E0200881 --persona xbox --duration-seconds 20 --sample-interval-seconds 2 --browser-witness --witness-port 8781 --assume-ready --out-dir target/xbox-live-bridge-witness
```

## Profile Checker

`tools/check_xbox_ble_profile.py` passed against the source-defined Xbox profile:

```text
30 pass, 0 warn, 0 fail
```

## Browser Result

Fresh deterministic artifact:

```text
browser_capture_file=target/xbox-host-visible-witness/xbox_host_visible_20260529T222306Z/browser_captures.jsonl
browser_id=USB2BLE Gamepad (STANDARD GAMEPAD)
browser_mapping=standard
browser_axes_count=4
browser_buttons_count=18
standard_layout_classification=standard_layout_partial
core_pass=true
required_pass=false
```

## Deterministic Scenario Classification

| Scenario | Expected standard control | Result |
| --- | --- | --- |
| `left_stick_left` | A0 negative | PASS |
| `left_stick_right` | A0 positive | PASS |
| `left_stick_up` | A1 negative | PASS |
| `left_stick_down` | A1 positive | PASS |
| `right_stick_left` | A2 negative | PASS |
| `right_stick_right` | A2 positive | PASS |
| `right_stick_up` | A3 negative | PASS |
| `right_stick_down` | A3 positive | PASS |
| `left_trigger_max` | B6 value 1.0 | PASS |
| `right_trigger_max` | B7 value 1.0 | PASS |
| `hat_up` | B12 | PASS |
| `hat_right` | B15 | PASS |
| `hat_down` | B13 | PASS |
| `hat_left` | B14 | PASS |
| `button_a` | B0 | PASS |
| `button_b` | B1 | PASS |
| `button_x` | B2 | FAIL |
| `button_y` | B3 | FAIL |
| `button_lb` | B4 | FAIL |
| `button_rb` | B5 | FAIL |
| `button_view` | B8 | FAIL |
| `button_menu` | B9 | FAIL |

Core Flight Pack-relevant controls passed: right stick X maps to browser A2,
left trigger maps to B6, and right trigger maps to B7. Those are the host-visible
positions needed for the refined Xbox rudder and toe-brake mapping, but this
run did not include physical Flight Pack movement through the live bridge.

## Transcript Excerpts

Target connected as Xbox persona:

```text
STATUS:ble=Connected;profile=none;persona=xbox_wireless_controller;bonds=false;
BLE_ADVERTISING_INFO:persona=xbox_wireless_controller;state=Connected;variant=xbox_compatibility;device_name=Xbox Wireless Controller;appearance=0x03c4;advertised_uuids=1812;security=bond;bonds=false;
```

Deterministic reports published over the connected BLE path:

```text
PUBLISH_XBOX_TEST_REPORT right_stick_right
BLE_ACTION:action=publish_xbox_test_report;state=Connected;persona=xbox_wireless_controller;report_id=1;bytes=00800080ffff00800000000000000000;
PUBLISH_XBOX_TEST_REPORT left_trigger_max
BLE_ACTION:action=publish_xbox_test_report;state=Connected;persona=xbox_wireless_controller;report_id=1;bytes=0080008000800080ff03000000000000;
PUBLISH_XBOX_TEST_REPORT right_trigger_max
BLE_ACTION:action=publish_xbox_test_report;state=Connected;persona=xbox_wireless_controller;report_id=1;bytes=00800080008000800000ff0300000000;
```

Refined Xbox runtime config was imported and target-side mapping diagnostics
showed the intended Flight Pack mapping:

```text
CONFIG_STATUS:valid=true;source=runtime;persona=xbox_wireless_controller;profile=custom_runtime;mappings=18;import_active=false;last_error=none;
XBOX_GAMEPAD_MAPPING:profile=custom_runtime;persona=xbox_wireless_controller;...axis_01_36,target=right_x...axis_01_34,target=left_trigger...axis_01_33,target=right_trigger...
```

The short refined Xbox live-bridge attempt published cleanly, but did not
capture browser input events:

```text
START_BRIDGE
BRIDGE_STATUS:enabled=true;persona=xbox_wireless_controller;rate_hz=50;published=0;last_error=none;
...
BRIDGE_STATUS:enabled=true;persona=xbox_wireless_controller;rate_hz=50;published=16;skipped_duplicate=15;last_error=none;
Browser input events: 0
```

## Artifacts

- `target/xbox-host-visible-witness/xbox_host_visible_20260529T222306Z`
- `target/xbox-host-visible-witness/xbox_host_visible_20260529T222306Z/summary.json`
- `target/xbox-host-visible-witness/xbox_host_visible_20260529T222306Z/scenario_results.json`
- `target/xbox-host-visible-witness/xbox_host_visible_20260529T222306Z/serial_transcript.txt`
- `target/xbox-host-visible-witness/xbox_host_visible_20260529T222306Z/browser_captures.jsonl`
- `target/xbox-host-visible-witness/xbox_host_visible_20260529T222306Z/xbox_profile_check.json`
- `target/xbox-live-bridge-witness/xbox_soak_20260529T221939Z`

## Conclusion

This is useful host-visible evidence, but it remains diagnostic rather than a
full Xbox standard-layout success. The correct claim is:

> macOS Chrome exposes USB2BLE's Xbox-compatible BLE persona as a connected
> `mapping="standard"` Gamepad API device, and deterministic Xbox reports move
> the expected standard stick, trigger, D-pad, A, and B controls.

The correct follow-up is to investigate the standard button-index mismatch and
then rerun a focused refined Xbox Flight Pack live-bridge witness for rudder and
toe brakes.

## Limitations

- The browser identity was `USB2BLE Gamepad (STANDARD GAMEPAD)`, not a literal
  Xbox-like browser `id`.
- X/Y/LB/RB/View/Menu did not match the expected standard button indices in this
  diagnostic.
- The refined Xbox live bridge published target reports, but browser input events
  were not captured during that short run; host-visible refined Flight Pack
  movement remains unproven.
- Reconnect behavior was not tested.
- No Xbox console, proprietary Xbox Wireless, Windows, Android, iOS, Linux,
  native game, external browser game, or broad browser support is proven.
- BLE bond and reconnect behavior are not proven.
