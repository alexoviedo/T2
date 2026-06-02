# Generic Report Descriptor Diagnostic - 2026-06-02

Status: diagnostic evidence. This does not prove a complete Generic virtual
browser replay witness and does not change the proven Generic default persona.

## Summary

This run decoded the Generic BLE Gamepad report descriptor and correlated the
decoded report fields with the layered Generic HID delivery artifact.

The Generic descriptor declares the intended six signed 16-bit Generic Desktop
axes:

| Axis | Usage | Byte offset | Bit offset | Logical range |
| --- | --- | ---: | ---: | --- |
| X | `1:48` | 3 | 24 | `-32768..32767` |
| Y | `1:49` | 5 | 40 | `-32768..32767` |
| Z | `1:50` | 7 | 56 | `-32768..32767` |
| Rx | `1:51` | 9 | 72 | `-32768..32767` |
| Ry | `1:52` | 11 | 88 | `-32768..32767` |
| Rz | `1:53` | 13 | 104 | `-32768..32767` |

The encoder writes the expected fields for virtual scenarios. The improved
macOS HID probe also enumerated HID elements for all six usages. The remaining
active failures are therefore classified as category `C`:

`descriptor_and_report_decode_match_but_macos_hid_did_not_emit_events`

No firmware descriptor change was made in this chunk because the evidence does
not show a descriptor/encoder mismatch, and older checked-in Generic evidence
already proves A4/A5 host-visible exposure in a real-input Chrome witness.

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
python3 tools/generic_hid_delivery_diagnosis.py --port /dev/cu.usbmodem5B5E0200881 --chrome-port 8883 --neutral-seconds 1.2 --scenario-seconds 2.0 --post-neutral-seconds 1.2 --sample-ms 75
python3 tools/generic_report_descriptor_diagnosis.py --delivery-run target/generic-hid-delivery-diagnosis/generic_hid_delivery_20260602T192009Z
```

Supporting checks while developing the tool:

```text
python3 -m py_compile tools/generic_report_descriptor_diagnosis.py tools/macos_hid_event_probe.py tools/generic_hid_delivery_diagnosis.py
swiftc tools/macos_hid_event_probe.swift -o /tmp/macos_hid_event_probe_test
python3 -m unittest tools.tests.test_ble_compat_tools
```

## Scenario Correlation

| Scenario | Axis | Decoded baseline -> active | macOS element | macOS HID events | Chrome layer |
| --- | --- | --- | --- | ---: | --- |
| `stick_left` | X | `0 -> -32768` | yes | 1 | witness_sampling |
| `stick_right` | X | `0 -> 32767` | yes | 1 | pass |
| `stick_forward` | Y | `0 -> -32768` | yes | 1 | pass |
| `stick_back` | Y | `0 -> 32767` | yes | 1 | pass |
| `throttle_max` | Z | `-32767 -> 32767` | yes | 1 | pass |
| `throttle_min` | Z | `-32767 -> -32767` | yes | 0 | inconclusive endpoint |
| `rudder_left` | Rx | `0 -> 32767` | yes | 1 | pass |
| `rudder_right` | Rx | `0 -> -32768` | yes | 0 | macOS HID |
| `left_toe_pressed` | Ry | `-32767 -> 32767` | yes | 0 | macOS HID |
| `left_toe_released` | Ry | `-32767 -> -32767` | yes | 0 | inconclusive endpoint |
| `right_toe_pressed` | Rz | `-32767 -> 32767` | yes | 0 | macOS HID |
| `right_toe_released` | Rz | `-32767 -> -32767` | yes | 0 | inconclusive endpoint |

## Root-Cause Classification

Category: `C`

Reason: descriptor and report decode match, but macOS HID did not emit value
callbacks for changed fields in this run.

Rejected categories:

- `A` descriptor declares Ry/Rz incorrectly: rejected because the descriptor
  parser found X/Y/Z/Rx/Ry/Rz usages at the expected offsets.
- `B` encoder writes Ry/Rz to the wrong offset/order: rejected because decoded
  report bytes changed in the intended fields.
- `D` macOS probe filtering misses Ry/Rz elements: rejected because the improved
  probe enumerated HID elements for usages `1:52` and `1:53`.
- `E` Chrome ignores Ry/Rz while macOS HID sees them: rejected for this run
  because macOS HID callbacks were not observed first.

## Artifacts

- `target/generic-hid-delivery-diagnosis/generic_hid_delivery_20260602T192009Z`
- `target/generic-report-descriptor-diagnosis/generic_report_descriptor_20260602T192304Z`
- `target/generic-report-descriptor-diagnosis/generic_report_descriptor_20260602T192304Z/report_layout.json`
- `target/generic-report-descriptor-diagnosis/generic_report_descriptor_20260602T192304Z/scenario_report_decode.json`
- `target/generic-report-descriptor-diagnosis/generic_report_descriptor_20260602T192304Z/hid_event_correlation.json`
- `target/generic-report-descriptor-diagnosis/generic_report_descriptor_20260602T192304Z/diagnosis.md`

## Conclusion

The Generic report descriptor and encoder are internally consistent for the six
axis fields. The current evidence does not justify changing the proven
`generic_default` descriptor. The unresolved issue is host delivery for some
changed Generic axis fields in this virtual replay session: macOS HID elements
exist, but callbacks were not observed for Ry/Rz and one Rx direction.

The next technical step should test a deliberately separate experimental path,
such as a symmetric endpoint or split/alternative Generic axis descriptor
variant, without replacing the proven default until a host-visible witness
supports it.

## Limitations

- This is virtual normalized-input diagnostic evidence, not physical USB
  movement evidence.
- It does not prove complete Generic virtual browser replay.
- It does not replace the already checked-in real USB HID parser/input evidence.
- It does not prove broad browser/host support, BLE bond persistence, automatic
  persona switching, Windows, Android, iOS, Linux, native game/app behavior, or
  final Flight Pack calibration quality.
