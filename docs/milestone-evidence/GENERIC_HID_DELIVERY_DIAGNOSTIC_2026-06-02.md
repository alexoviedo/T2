# Generic HID Delivery Diagnostic - 2026-06-02

Status: diagnostic evidence. This does not prove a complete Generic virtual
browser replay witness.

## Summary

This run added a lower-level macOS HID event probe and a timestamp-aware Chrome
Gamepad probe to isolate where Generic virtual normalized-input replay stops
surfacing.

The target-side path stayed healthy: virtual input was enabled, the refined
Generic runtime mapping changed for active scenarios, encoded Generic reports
changed where expected, and bridge `published` counters increased for every
scenario. A clean temporary Chrome profile exposed `USB2BLE Gamepad (Vendor:
303a Product: 4001)` with empty `mapping`, 10 axes, and 16 buttons.

The new macOS HID probe showed that macOS received HID events for Generic usages
48, 49, 50, and 51, but not for usages 52 or 53 during the toe-axis scenarios.
Chrome updated when macOS delivered HID events for several axes. The remaining
active failures are therefore narrowed below Chrome for the toe axes and one
rudder direction, with one stick-left transition classified as witness sampling
because Chrome already held the active A0 value when the active window began.

## Context

- Date/time: 2026-06-02.
- Commit: `35ab7d7e3ae9029cee05ae5b43da58deb04cf614` plus working-tree tooling
  changes described by this evidence.
- Serial port: `/dev/cu.usbmodem5B5E0200881`.
- Host: MacBook Pro 15-inch 2016, macOS 12.7.5.
- Browser: Google Chrome 148.0.7778.216, clean temporary profile.
- Active persona: `generic_gamepad`.
- Runtime config: `flight-pack-generic` / `custom_runtime`.
- Input source: diagnostic virtual normalized-input replay.
- Human physical input required: no.
- Human GUI/Bluetooth action during this run: no.

## Commands Run

```text
python3 tools/generic_hid_delivery_diagnosis.py --port /dev/cu.usbmodem5B5E0200881 --chrome-port 8882 --neutral-seconds 1.2 --scenario-seconds 2.0 --post-neutral-seconds 1.2 --sample-ms 75
```

Supporting checks while developing the probes:

```text
python3 -m py_compile tools/chrome_gamepad_probe.py tools/macos_hid_event_probe.py tools/generic_hid_delivery_diagnosis.py
swiftc tools/macos_hid_event_probe.swift -o /tmp/macos_hid_event_probe_test
python3 -m unittest tools.tests.test_ble_compat_tools
```

## Scenario Classification

| Scenario | Target mapping/report | Bridge delta | macOS HID | Chrome | Classification |
| --- | --- | ---: | --- | --- | --- |
| `stick_left` | changed | 5 | event seen | held A0 `-1.0`, no timestamp edge in window | witness_sampling |
| `stick_right` | changed | 4 | event seen | A0 changed to `1.0` | pass |
| `stick_forward` | changed | 5 | event seen | A1 changed to `-1.0` | pass |
| `stick_back` | changed | 4 | event seen | A1 changed to `1.0` | pass |
| `throttle_max` | changed | 5 | event seen | A2 changed to `1.0` | pass |
| `throttle_min` | baseline endpoint | 4 | no event expected from neutral baseline | A2 already at `-1.0` | inconclusive |
| `rudder_left` | changed | 5 | event seen | A3 changed to `1.0` | pass |
| `rudder_right` | changed | 4 | no event seen | no samples | macos_hid |
| `left_toe_pressed` | changed | 4 | no event seen | no samples | macos_hid |
| `left_toe_released` | baseline endpoint | 4 | no event expected from neutral baseline | no samples | inconclusive |
| `right_toe_pressed` | changed | 4 | no event seen | no samples | macos_hid |
| `right_toe_released` | baseline endpoint | 4 | no event expected from neutral baseline | no samples | inconclusive |

Summary fields from `summary.json`:

```text
scenario_count=12
pass_count=5
failure_layers={"inconclusive":3,"macos_hid":3,"pass":5,"witness_sampling":1}
hid_probe_available=true
```

## Probe Results

Chrome probe summary:

```text
chrome_mode=temp-profile
connected_gamepad_observations=765
id=USB2BLE Gamepad (Vendor: 303a Product: 4001)
mapping=
axes_lengths=[10]
buttons_lengths=[16]
changed_axis_indices=[0,1,2,3]
```

macOS HID probe summary:

```text
swift_compile_ok=true
device_count=1
products=["USB2BLE Gamepad"]
vendor_product_ids=["303a:4001"]
transport=Bluetooth Low Energy
event_count=12
changed_usages=["1:48","1:49","1:50","1:51"]
```

The absence of HID events for usages 52 and 53 during the virtual toe-axis
scenarios is the strongest clue from this run. Chrome is not the first failing
layer for those scenarios because the lower-level macOS HID callback did not see
the value changes either.

## Artifacts

- `target/generic-hid-delivery-diagnosis/generic_hid_delivery_20260602T185902Z`
- `target/generic-hid-delivery-diagnosis/generic_hid_delivery_20260602T185902Z/summary.json`
- `target/generic-hid-delivery-diagnosis/generic_hid_delivery_20260602T185902Z/scenario_results.json`
- `target/generic-hid-delivery-diagnosis/generic_hid_delivery_20260602T185902Z/serial_transcript.txt`
- `target/generic-hid-delivery-diagnosis/generic_hid_delivery_20260602T185902Z/chrome/chrome_gamepad_probe_20260602T185915Z/chrome_gamepad_probe.jsonl`
- `target/generic-hid-delivery-diagnosis/generic_hid_delivery_20260602T185902Z/macos_hid/macos_hid_event_probe_20260602T185915Z/macos_hid_events.jsonl`

## Conclusion

The remaining Generic virtual browser replay blocker is no longer a vague Chrome
sampling problem. For this run:

- target mapping, encoded reports, BLE connection, and bridge publication were
  healthy;
- macOS HID events were observed for X/Y/Z/Rx usages;
- Chrome updated when macOS HID events and browser samples aligned;
- Ry/Rz toe-axis scenarios and one negative Rx direction did not produce macOS
  HID callback events despite target report and bridge deltas.

Do not promote this to a Generic virtual bridge success witness. The next
technical action should inspect Generic HID report descriptor/report delivery
semantics for the later axes, especially usages 52/53 and signed minimum
endpoint behavior, then rerun this layered diagnostic.

## Limitations

- This is virtual normalized-input diagnostic evidence, not physical USB
  movement evidence.
- It does not prove complete Generic virtual browser replay.
- It does not replace the already checked-in real USB HID parser/input evidence.
- It does not prove broad browser/host support, BLE bond persistence, automatic
  persona switching, Windows, Android, iOS, Linux, native game/app behavior, or
  final Flight Pack calibration quality.
