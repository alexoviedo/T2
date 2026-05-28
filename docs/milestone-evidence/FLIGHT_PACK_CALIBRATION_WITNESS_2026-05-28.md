# Flight Pack Calibration Witness - 2026-05-28

Status: partial calibration and axis-label evidence captured from real target transcripts.
This proves high-confidence target-side labels for the practical RJ12 Flight Pack
topology, but it does not prove final deadzone/calibration semantics or any
game/app compatibility.

## Run Metadata

- Date/time: 2026-05-28 23:23:57Z full pass; 2026-05-28 23:35:09Z throttle rerun
- Commit SHA: `bb4d3c20094ae08d98f76ee2d657276d11f1167a`
- Serial port: `/dev/cu.usbmodem5B5E0200881`
- Hardware topology: ESP32-S3 serial/programming USB to Mac; HooToo SHUTTLE
  HT-UC001 powered hub on ESP32-S3 USB host/OTG; T.16000M stick USB and TWCS
  throttle USB connected through the hub; TFRP pedals connected to TWCS by RJ12.
- Source map observed by target: T.16000M stick `2:0`, TWCS/RJ12 `3:0`.
- Target artifact directories:
  - `target/flight-pack-calibration/flight_pack_calibration_20260528T232357Z`
  - `target/flight-pack-calibration/flight_pack_calibration_20260528T233509Z`

## Commands Run

```bash
git status --short
ls /dev/cu.* /dev/tty.* 2>/dev/null | grep -E 'usb|wch|modem|serial'
python3 tools/serial_command.py --port /dev/cu.usbmodem5B5E0200881 --timeout 3 GET_INFO GET_STATUS GET_USB_STATUS LIST_USB_DEVICES
./scripts/validate_no_hardware.sh
python3 -m py_compile tools/flight_pack_calibration_witness.py
./scripts/check_target_build.sh
python3 tools/flight_pack_calibration_witness.py --port /dev/cu.usbmodem5B5E0200881 --out-dir target/flight-pack-calibration
python3 tools/flight_pack_calibration_witness.py --port /dev/cu.usbmodem5B5E0200881 --out-dir target/flight-pack-calibration --steps throttle_min,throttle_max
```

The first full pass included one operator mistake: the TWCS throttle-minimum
step was physically held at maximum. The throttle pair was rerun cleanly in the
second artifact directory, and the evidence below uses the rerun for throttle
claims.

## Device Presence

The target saw the expected practical topology:

```text
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b10a|id=3,vid=044f,pid=b687
```

This corresponds to the HooToo hub, T.16000M stick, and TWCS/RJ12 source.

## Movement Evidence

| Movement | Source | Primary Control | Observed Values | Generic Target | Xbox Target | Confidence |
| --- | --- | --- | --- | --- | --- | --- |
| T.16000M stick left/right | `2:0` | `axis_01_30` | left `-32768`, right `32478` | `x` | `left_x` | high for right, medium for left |
| T.16000M stick forward/back | `2:0` | `axis_01_31` | forward `-32768`, back `32767` | `y` | `left_y` | medium |
| T.16000M twist | `2:0` | `axis_01_35` | left `-32768`, right `32767` | `none` | `right_y` | high for right, medium/noisy for left |
| T.16000M trigger | `2:0` | `button_1` | released `0`, pressed `1` | `none` | `a` | observed, but first-pass delta inference was noisy |
| TWCS throttle min/max | `3:0` | `axis_01_32` | min `32767`, max `-32768` | `z` | `right_trigger` | high, rerun |
| TFRP/RJ12 rudder left/right | `3:0` | `axis_01_36` | left `32767`, right `-32768` | `rx` | `right_x` | high |
| TFRP/RJ12 left toe brake | `3:0` | `axis_01_34` | released `32767`, pressed `-32768` | `none` | `none` | high |
| TFRP/RJ12 right toe brake | `3:0` | `axis_01_33` | released `32767`, pressed `-32768` | `none` | `none` | high |

## RJ12 Pedal Axis-Label Findings

- RJ12 rudder is `3:0:044f:b687:axis_01_36`; full left is positive, full right
  is negative. The current mappings send it to Generic `rx` and Xbox
  `right_x`.
- RJ12 left toe brake is `3:0:044f:b687:axis_01_34`; released is positive,
  pressed is negative. It is currently unmapped for Generic and Xbox.
- RJ12 right toe brake is `3:0:044f:b687:axis_01_33`; released is positive,
  pressed is negative. It is currently unmapped for Generic and Xbox.

## Transcript Excerpts

Throttle rerun:

```text
NORMALIZED_INPUT:...axis_01_32=axis:32767;...
NORMALIZED_INPUT:...axis_01_32=axis:-32768;...
```

RJ12 rudder:

```text
NORMALIZED_INPUT:...axis_01_36=axis:32767;...
NORMALIZED_INPUT:...axis_01_36=axis:-32768;...
```

RJ12 toe brakes:

```text
NORMALIZED_INPUT:...axis_01_34=axis:-32768;...
NORMALIZED_INPUT:...axis_01_33=axis:-32768;...
```

## Limitations

- This is target-side control-plane evidence only; it does not prove BLE host
  input, browser Gamepad API input, or game/app compatibility.
- The first full pass contains a known reversed throttle-minimum operator step;
  throttle claims rely on the clean two-step rerun.
- The witness tool now treats first samples as reference samples and fixes
  normalized-input prefix parsing. Firmware behavior was not changed in this
  chunk.
- Stick and trigger movements are useful supporting evidence, but the first-pass
  delta analysis was affected by physical recentering/cross-axis movement.
- Deadzone, calibration curves, persistence of calibrated values, and
  product-ready Flight Pack profile quality remain unproven.
- Three separate USB Flight Pack devices streaming simultaneously remain
  outside this witness; the practical topology here is TWCS/RJ12 plus stick USB.
