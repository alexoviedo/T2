# Flight Pack Mapping Refinement Witness - 2026-05-28

Status: target-side mapping refinement evidence captured from real ESP32-S3
transcripts for the practical RJ12 Flight Pack topology. This proves the
refined Generic/Xbox mapping rules for TWCS throttle, RJ12 rudder, and both
RJ12 toe brakes at the control-plane/report-encoding layer. It does not prove
BLE host input, game/app compatibility, bond persistence, or final
product-quality deadzone/calibration behavior.

## Run Metadata

- Date/time: 2026-05-28 local; artifacts captured as
  `20260529T000506Z`, `20260529T001204Z`, and `20260529T001442Z`.
- Commit SHA before this working-tree change: `76e3be8e28b358fe94b5f19d4b2bfb6e8a7273c4`
- Serial port: `/dev/cu.usbmodem5B5E0200881`
- Hardware topology: ESP32-S3 serial/programming USB to Mac; HooToo SHUTTLE
  HT-UC001 powered hub on ESP32-S3 USB host/OTG; T.16000M stick USB and TWCS
  throttle USB connected through the hub; TFRP pedals connected to TWCS by RJ12.
- Source map observed by target: T.16000M stick `2:0`, TWCS/RJ12 `3:0`.
- Target artifact directories:
  - `target/flight-pack-mapping-witness/flight_pack_mapping_20260529T000506Z`
  - `target/flight-pack-mapping-witness/flight_pack_mapping_20260529T001204Z`
  - `target/flight-pack-mapping-witness/flight_pack_mapping_20260529T001442Z`

## Commands Run

```bash
git status --short
ls /dev/cu.* /dev/tty.* 2>/dev/null | grep -E 'usb|wch|modem|serial'
python3 tools/serial_command.py --port /dev/cu.usbmodem5B5E0200881 --timeout 3 GET_INFO GET_STATUS GET_USB_STATUS LIST_USB_DEVICES
./scripts/validate_no_hardware.sh
./scripts/check_target_build.sh
./scripts/build.sh
./scripts/flash.sh --port /dev/cu.usbmodem5B5E0200881
python3 tools/configure_board.py --port /dev/cu.usbmodem5B5E0200881 preset flight-pack-generic
python3 tools/flight_pack_mapping_witness.py --port /dev/cu.usbmodem5B5E0200881 --out-dir target/flight-pack-mapping-witness
python3 tools/flight_pack_mapping_witness.py --port /dev/cu.usbmodem5B5E0200881 --out-dir target/flight-pack-mapping-witness --steps left_toe_released,left_toe_pressed,right_toe_released,right_toe_pressed
python3 tools/flight_pack_mapping_witness.py --port /dev/cu.usbmodem5B5E0200881 --out-dir target/flight-pack-mapping-witness --steps rudder_left_rj12,rudder_right_rj12
```

The board was flashed before evidence capture. A stale persisted runtime
Generic config was present after flashing, so the updated Flight Pack Generic
runtime config was imported before the mapping witness. This witness does not
claim durable persistence of that newly imported config.

The first full witness run exited nonzero because the helper initially treated
the expected unmapped Xbox throttle target as a mismatch when the target
reported `target=none`. The transcript is still real target data and the helper
was fixed before the focused cleanup runs.

## Device Presence

The target saw the expected practical topology:

```text
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b10a|id=3,vid=044f,pid=b687
```

## Mapping Strategy

Generic Gamepad uses the six available analog axes intentionally:

- T.16000M stick `axis_01_30` -> Generic `x`.
- T.16000M stick `axis_01_31` -> Generic `y`.
- TWCS throttle `axis_01_32` -> Generic `z`, inverted so physical maximum
  throttle moves away from the released/minimum side of the raw axis.
- TFRP/RJ12 rudder `axis_01_36` -> Generic `rx`.
- TFRP/RJ12 left toe brake `axis_01_34` -> Generic `ry`, inverted.
- TFRP/RJ12 right toe brake `axis_01_33` -> Generic `rz`, inverted.

Xbox uses the limited analog targets intentionally:

- T.16000M stick `axis_01_30` -> Xbox `left_x`.
- T.16000M stick `axis_01_31` -> Xbox `left_y`.
- TFRP/RJ12 rudder `axis_01_36` -> Xbox `right_x`.
- TFRP/RJ12 left toe brake `axis_01_34` -> Xbox `left_trigger` with
  `axis_to_trigger`, `source_min=-32768`, `source_max=32767`, `invert=true`.
- TFRP/RJ12 right toe brake `axis_01_33` -> Xbox `right_trigger` with the same
  trigger transform.
- TWCS throttle is intentionally unmapped for Xbox in this practical profile
  because the trigger slots are used for toe brakes.

## Movement Evidence

| Movement | Source control | Observed values | Generic target | Xbox target | Transform/deadzone | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| TWCS throttle min/max | `3:0:044f:b687:axis_01_32` | min `32767`, max `-32768` | `z` | unmapped | Generic `invert=true`; no deadzone | full run |
| TFRP/RJ12 rudder | `3:0:044f:b687:axis_01_36` | centered near `31`, right extreme `-32768`; prior axis-label witness proves left `32767` | `rx` | `right_x` | none | cleanup run plus prior axis-label witness |
| TFRP/RJ12 left toe brake | `3:0:044f:b687:axis_01_34` | released `32767`, pressed `-32768` | `ry` | `left_trigger` | Generic `invert=true`; Xbox `axis_to_trigger invert=true`; no deadzone | toe cleanup run |
| TFRP/RJ12 right toe brake | `3:0:044f:b687:axis_01_33` | released `32767`, pressed `-32768` | `rz` | `right_trigger` | Generic `invert=true`; Xbox `axis_to_trigger invert=true`; no deadzone | toe cleanup run |

The left-rudder cleanup step was captured near center rather than at full travel,
so this document does not use that pass as new left-rudder physical-direction
proof. The physical left/right labels for `axis_01_36` remain grounded in
`docs/milestone-evidence/FLIGHT_PACK_CALIBRATION_WITNESS_2026-05-28.md`.

## Transcript Excerpts

Throttle mapping:

```text
GENERIC_GAMEPAD_MAPPING:...src=3:0:044f:b687:axis_01_32,target=z,value=axis:-32768,reason=profile_rule_inverted...
XBOX_GAMEPAD_MAPPING:...src=3:0:044f:b687:axis_01_32,target=none,value=axis:-32768,reason=profile_unmapped...
```

Rudder mapping:

```text
NORMALIZED_INPUT:...axis_01_36=axis:-32768;...
GENERIC_GAMEPAD_MAPPING:...src=3:0:044f:b687:axis_01_36,target=rx,value=axis:-32768,reason=profile_rule...
XBOX_GAMEPAD_MAPPING:...src=3:0:044f:b687:axis_01_36,target=right_x,value=axis:-32768,reason=profile_rule...
```

Toe brake mapping:

```text
NORMALIZED_INPUT:...axis_01_34=axis:32767;...axis_01_33=axis:32767;...
GENERIC_GAMEPAD_MAPPING:...src=3:0:044f:b687:axis_01_34,target=ry,value=axis:32767,reason=profile_rule_inverted...
GENERIC_GAMEPAD_MAPPING:...src=3:0:044f:b687:axis_01_33,target=rz,value=axis:-32768,reason=profile_rule_inverted...
XBOX_GAMEPAD_MAPPING:...src=3:0:044f:b687:axis_01_34,target=left_trigger,value=axis:-32768,reason=profile_rule_calibrated...
XBOX_GAMEPAD_MAPPING:...src=3:0:044f:b687:axis_01_33,target=right_trigger,value=axis:-32768,reason=profile_rule_calibrated...
```

Encoded reports were captured for each step, including:

```text
ENCODED_REPORT:persona=generic_gamepad;report_id=1;bytes=00000865fc61f9ff7f008001800180;
ENCODED_REPORT:persona=xbox_wireless_controller;report_id=1;bytes=647c60790000ff7f0000000000000000;
```

## Limitations

- This is target-side serial/control-plane evidence. It does not prove BLE host
  input, browser Gamepad API behavior, or game/app compatibility.
- The Generic runtime mapping was imported before the witness because stale NVS
  config still held an older four-axis preset. Durable persistence of the new
  mapping was not tested in this chunk.
- The left-rudder cleanup pass did not capture full left travel; left/right
  physical direction labels still rely on the earlier calibration witness.
- Deadzone quality, calibration curves, persistence of calibrated values, and
  product-ready Flight Pack feel remain unproven.
- TWCS throttle is deliberately unmapped in the Xbox practical profile; this is
  a profile compromise, not broad Xbox HOTAS compatibility.
- Three separate USB Flight Pack devices streaming simultaneously remain
  outside this witness; the practical topology here is TWCS/RJ12 plus stick USB.
