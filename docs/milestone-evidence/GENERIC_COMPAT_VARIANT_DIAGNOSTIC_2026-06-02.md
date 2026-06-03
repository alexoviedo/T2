# Generic Compatibility Variant Diagnostic - 2026-06-02

Status: diagnostic evidence. This does not promote
`generic_unsigned_6axis`, does not change the `generic_default` persona, and
does not prove a complete Generic virtual browser replay.

## Summary

This run recovered ESP32-S3 flash/serial access, flashed the current firmware
image, verified the experimental `generic_unsigned_6axis` variant on target,
and ran a default-vs-variant layered HID delivery A/B test using virtual
normalized-input replay only.

The unsigned variant was correctly present on target:

- Variant: `generic_unsigned_6axis`
- Identity: `USB2BLE Gamepad U6`
- VID/PID: `303a:4002`
- Report ID: `1`
- Report map length: `79`
- Axes: `X/Y/Z/Rx/Ry/Rz`
- Axis offsets: `X` byte 3, `Y` byte 5, `Z` byte 7, `Rx` byte 9, `Ry` byte 11, `Rz` byte 13
- Logical range: unsigned `0..65535`
- Neutral value: `32768`

The A/B result did not show an improvement over `generic_default`. The unsigned
variant still failed to produce macOS HID callback delivery for the later
refined Flight Pack axes (`Ry/Rz`) in this run, and Chrome did not improve.
`generic_default` therefore remains the evidence-backed default.

## Context

- Date/time: 2026-06-02 local time.
- Commit: `2abc6ca99a4e5cc4e7238b1af93643f27c7c69d1`.
- Board: ESP32-S3.
- Selected serial/control port for diagnostics: `/dev/cu.usbmodem5B5E0200881`.
- Recovery/flash port that worked: `/dev/cu.wchusbserial5B5E0200881`.
- Host: MacBook Pro 15-inch 2016, macOS 12.7.x.
- Browser mode: clean temporary Chrome profile per diagnostic run.
- Input source: firmware-level virtual normalized-input replay.
- Human physical control movement required: no.
- Human board recovery action required: no.

## Board Recovery

The board initially did not answer serial control commands and normal flashing
stalled after ESP32-S3 chip detection. Terminal-only recovery succeeded:

1. Discovered `/dev/cu.usbmodem5B5E0200881` and `/dev/cu.wchusbserial5B5E0200881`.
2. Verified no project process was holding the relevant serial ports.
3. `espflash board-info` succeeded on `/dev/cu.wchusbserial5B5E0200881`.
4. `./scripts/build.sh` succeeded.
5. `./scripts/flash.sh --port /dev/cu.wchusbserial5B5E0200881` stalled after chip detection.
6. Direct low-baud/no-stub flashing also stalled.
7. `espflash save-image` produced an app image, then `espflash write-bin 0x10000` successfully wrote that app image.
8. After reset, both serial ports answered `GET_INFO`, `GET_STATUS`, `LIST_BLE_COMPAT_VARIANTS`, and `GET_BLE_COMPAT_PROFILE`.

## Descriptor Comparison

| Variant | Identity | Logical range | Axis offsets | Report ID | Result |
| --- | --- | --- | --- | ---: | --- |
| `generic_default` | `USB2BLE Gamepad`, `303a:4001` | signed `-32768..32767` | X3/Y5/Z7/Rx9/Ry11/Rz13 | 1 | unchanged |
| `generic_unsigned_6axis` | `USB2BLE Gamepad U6`, `303a:4002` | unsigned `0..65535` | X3/Y5/Z7/Rx9/Ry11/Rz13 | 1 | target verified, experimental |

The experiment isolated logical range as the main descriptor difference while
keeping axis usages and offsets stable.

## A/B Scenario Summary

| Scenario | Expected axis | Default result | Unsigned result |
| --- | --- | --- | --- |
| `stick_left` | A0 / X | pass | pass |
| `stick_right` | A0 / X | pass | pass |
| `stick_forward` | A1 / Y | pass | pass |
| `stick_back` | A1 / Y | pass | pass |
| `throttle_max` | A2 / Z | pass | macOS HID saw change, Chrome did not |
| `throttle_min` | A2 / Z | inconclusive endpoint | inconclusive endpoint |
| `rudder_left` | A3 / Rx | pass | pass |
| `rudder_right` | A3 / Rx | macOS HID callback missing | macOS HID callback missing |
| `left_toe_pressed` | A4 / Ry | macOS HID callback missing | macOS HID callback missing |
| `left_toe_released` | A4 / Ry | inconclusive endpoint | inconclusive endpoint |
| `right_toe_pressed` | A5 / Rz | macOS HID callback missing | macOS HID callback missing |
| `right_toe_released` | A5 / Rz | inconclusive endpoint | inconclusive endpoint |

Counters:

- `generic_default`: 6 pass, 3 macOS HID failures, 3 inconclusive endpoint/release scenarios.
- `generic_unsigned_6axis`: 5 pass, 3 macOS HID failures, 1 Chrome Gamepad failure after macOS HID delivery, 3 inconclusive endpoint/release scenarios.

## Conclusion

`generic_unsigned_6axis` is a useful negative A/B result: changing the Generic
six-axis logical range from signed to unsigned did not resolve the current
macOS HID callback delivery gap for `Ry/Rz` in virtual replay, and did not
improve Chrome Gamepad API behavior on this host.

The variant should remain experimental and non-default. The next compatibility
experiment should test a different descriptor shape, such as a compact
four-axis-plus-trigger-style variant or a split-collection variant, instead of
continuing to tune signed-vs-unsigned six-axis ranges.

## Artifacts

- Board recovery: `target/generic-compat-variant-witness/board_recovery_20260603T000822Z`
- A/B root: `target/generic-compat-variant-witness/generic_variant_ab_20260603T001735Z`
- Default layered run: `target/generic-compat-variant-witness/generic_variant_ab_20260603T001735Z/generic_hid_delivery_generic_default_20260603T001753Z`
- Unsigned layered run: `target/generic-compat-variant-witness/generic_variant_ab_20260603T001735Z/generic_hid_delivery_generic_unsigned_6axis_20260603T002044Z`
- Descriptor outputs: `target/generic-compat-variant-witness/generic_variant_ab_20260603T001735Z/descriptor`

## Limitations

- This is virtual normalized-input diagnostic evidence, not physical USB
  movement evidence.
- It does not prove complete Generic virtual browser replay.
- It does not replace the earlier real USB/HID input and Generic host-visible
  evidence.
- It does not prove broad browser/host support, BLE bond persistence,
  Windows, Android, iOS, Linux, native game/app behavior, automatic persona
  switching, or final Flight Pack calibration quality.
