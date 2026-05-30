# Xbox Standard-Layout Diagnostic - 2026-05-29

Status: partial host-visible diagnostic evidence. This proves USB2BLE's
Xbox-compatible BLE persona is visible to macOS Chrome as a connected
`mapping="standard"` Gamepad API device, and deterministic Xbox reports drive
the expected standard positions for sticks, triggers, D-pad, A/B/X/Y, LB/RB,
View, and Menu. It does not prove a complete standard Xbox layout because Chrome
did not expose left/right stick-press buttons at B10/B11.

## Summary

USB2BLE was tested on macOS 12.7.x with Google Chrome against deterministic
Xbox Report ID 1 payloads published over the active BLE connection. After
diagnosing the earlier button-order mismatch, the Xbox encoder was adjusted so
logical X/Y/LB/RB/View/Menu controls use the raw button bits that Chrome maps to
the browser-standard positions for this Xbox-like VID/PID.

Chrome reported:

```text
browser_id=Xbox Wireless Controller (STANDARD GAMEPAD)
browser_mapping=standard
browser_axes_count=4
browser_buttons_count=18
standard_layout_classification=standard_layout_partial
matched_count=22
required_count=24
```

The remaining misses are left/right stick press. Additional diagnostic scenarios
showed that Chrome/macOS did not expose the raw bits currently used for those
logical controls as browser B10/B11. One extra raw control, `button_paddle_1`,
appeared at B16 and is not claimed as standard Xbox compatibility.

## Context

- Date/time: 2026-05-29T23:27:52Z
- Commit: `18658338012a73991e325b4220a260e0cfcb1ffe` plus working-tree changes
  described by this evidence
- Serial port: `/dev/cu.usbmodem5B5E0200881`
- Host: MacBook Pro 15-inch 2016 on macOS 12.7.x
- Browser: Google Chrome 148.0.7778.179, local Gamepad witness page
- Active persona: `xbox_wireless_controller`
- Active compatibility variant: `xbox_compatibility`
- Target BLE identity under test: `Xbox Wireless Controller`
- Xbox profile checker: `30 pass, 0 warn, 0 fail`

## Commands Run

```text
python3 tools/xbox_standard_layout_diagnose.py --artifact-dir target/xbox-host-visible-witness/xbox_host_visible_20260529T222306Z
python3 tools/xbox_host_visible_witness.py --port /dev/cu.usbmodem5B5E0200881 --witness-port 8780 --browser-timeout 8 --diagnose-layout --discover-layout --scenarios all --no-live-bridge
./scripts/check_target_build.sh
./scripts/build.sh
./scripts/flash.sh --port /dev/cu.usbmodem5B5E0200881
python3 tools/xbox_host_visible_witness.py --port /dev/cu.usbmodem5B5E0200881 --witness-port 8780 --browser-timeout 8 --diagnose-layout --discover-layout --scenarios all --no-live-bridge
python3 tools/configure_board.py --port /dev/cu.usbmodem5B5E0200881 preset flight-pack-xbox
python3 tools/configure_board.py --port /dev/cu.usbmodem5B5E0200881 start-configured
python3 tools/live_bridge_soak.py --port /dev/cu.usbmodem5B5E0200881 --persona xbox --duration-seconds 20 --sample-interval-seconds 2 --browser-witness --witness-port 8781 --assume-ready --out-dir target/xbox-refined-live-witness
```

## Deterministic Standard-Layout Result

| Scenario | Expected standard control | Observed browser change | Result |
| --- | --- | --- | --- |
| `left_stick_left` | A0 left stick X | A0 `0.0 -> -1.0` | PASS |
| `left_stick_right` | A0 left stick X | A0 `0.0 -> 1.0` | PASS |
| `left_stick_up` | A1 left stick Y | A1 `0.0 -> -1.0` | PASS |
| `left_stick_down` | A1 left stick Y | A1 `0.0 -> 1.0` | PASS |
| `right_stick_left` | A2 right stick X | A2 `0.0 -> -1.0` | PASS |
| `right_stick_right` | A2 right stick X | A2 `0.0 -> 1.0` | PASS |
| `right_stick_up` | A3 right stick Y | A3 `0.0 -> -1.0` | PASS |
| `right_stick_down` | A3 right stick Y | A3 `0.0 -> 1.0` | PASS |
| `left_trigger_max` | B6 left trigger | B6 `0.0 -> 1.0` | PASS |
| `right_trigger_max` | B7 right trigger | B7 `0.0 -> 1.0` | PASS |
| `hat_up` | B12 D-pad up | B12 `0.0 -> 1.0` | PASS |
| `hat_right` | B15 D-pad right | B15 `0.0 -> 1.0` | PASS |
| `hat_down` | B13 D-pad down | B13 `0.0 -> 1.0` | PASS |
| `hat_left` | B14 D-pad left | B14 `0.0 -> 1.0` | PASS |
| `button_a` | B0 A | B0 `0.0 -> 1.0` | PASS |
| `button_b` | B1 B | B1 `0.0 -> 1.0` | PASS |
| `button_x` | B2 X | B2 `0.0 -> 1.0` | PASS |
| `button_y` | B3 Y | B3 `0.0 -> 1.0` | PASS |
| `button_lb` | B4 LB | B4 `0.0 -> 1.0` | PASS |
| `button_rb` | B5 RB | B5 `0.0 -> 1.0` | PASS |
| `button_view` | B8 View/Back | B8 `0.0 -> 1.0` | PASS |
| `button_menu` | B9 Menu/Start | B9 `0.0 -> 1.0` | PASS |
| `button_left_stick_press` | B10 left stick press | none | MISS |
| `button_right_stick_press` | B11 right stick press | none | MISS |

## Transcript Excerpts

Target connected as the Xbox persona:

```text
STATUS:ble=Connected;profile=none;persona=xbox_wireless_controller;bonds=false;
BLE_ADVERTISING_INFO:persona=xbox_wireless_controller;state=Connected;variant=xbox_compatibility;device_name=Xbox Wireless Controller;appearance=0x03c4;advertised_uuids=1812;security=bond;bonds=false;
```

Corrected logical button reports:

```text
PUBLISH_XBOX_TEST_REPORT button_x
BLE_ACTION:action=publish_xbox_test_report;state=Connected;persona=xbox_wireless_controller;report_id=1;bytes=00800080008000800000000000080000;
PUBLISH_XBOX_TEST_REPORT button_lb
BLE_ACTION:action=publish_xbox_test_report;state=Connected;persona=xbox_wireless_controller;report_id=1;bytes=00800080008000800000000000400000;
PUBLISH_XBOX_TEST_REPORT button_view
BLE_ACTION:action=publish_xbox_test_report;state=Connected;persona=xbox_wireless_controller;report_id=1;bytes=00800080008000800000000000000400;
```

Refined Flight Pack Xbox live-bridge attempt:

```text
CONFIG_STATUS:valid=true;source=runtime;persona=xbox_wireless_controller;profile=custom_runtime;mappings=18;import_active=false;last_error=none;
START_BRIDGE
BRIDGE_STATUS:enabled=true;persona=xbox_wireless_controller;rate_hz=50;published=0;last_error=none;
...
BRIDGE_STATUS:enabled=true;persona=xbox_wireless_controller;rate_hz=50;published=16;skipped_duplicate=15;last_error=none;
```

That short live-bridge run published target reports cleanly, but browser input
events were not captured, so refined Flight Pack Xbox host-visible movement
remains unproven.

## Artifacts

- `target/xbox-standard-layout-diagnosis/xbox_standard_layout_20260529T231516Z`
- `target/xbox-host-visible-witness/xbox_host_visible_20260529T232020Z`
- `target/xbox-host-visible-witness/xbox_host_visible_20260529T232752Z`
- `target/xbox-host-visible-witness/xbox_host_visible_20260529T232752Z/summary.json`
- `target/xbox-host-visible-witness/xbox_host_visible_20260529T232752Z/scenario_results.json`
- `target/xbox-host-visible-witness/xbox_host_visible_20260529T232752Z/layout_diagnosis.json`
- `target/xbox-host-visible-witness/xbox_host_visible_20260529T232752Z/serial_transcript.txt`
- `target/xbox-host-visible-witness/xbox_host_visible_20260529T232752Z/browser_captures.jsonl`
- `target/xbox-refined-live-witness/xbox_soak_20260529T233018Z`

## Conclusion

The corrected claim is:

> macOS Chrome exposes USB2BLE's Xbox-compatible BLE persona as
> `mapping="standard"` and deterministic Xbox reports drive the expected
> standard sticks, triggers, D-pad, A/B/X/Y, LB/RB, View, and Menu positions.

This remains a diagnostic, not a broad Xbox compatibility claim, because stick
presses did not surface at B10/B11 and refined Flight Pack Xbox live movement is
not yet host-visible.

## Limitations

- Left/right stick press did not appear as browser B10/B11 in this host run.
- `button_paddle_1` appeared as browser B16 but is not claimed as a standard
  control.
- Refined Flight Pack Xbox live bridge published target reports, but browser
  movement was not captured in the short no-physical-input run.
- Reconnect behavior was not tested.
- No Xbox console, proprietary Xbox Wireless, Windows, Android, iOS, Linux,
  native game, external browser game, or broad browser support is proven.
- BLE bond and reconnect behavior are not proven.
