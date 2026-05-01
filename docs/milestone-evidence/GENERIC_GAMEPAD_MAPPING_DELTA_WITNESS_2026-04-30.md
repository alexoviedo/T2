# Generic Gamepad Mapping Delta Witness - 2026-04-30

Status: **accepted hardware evidence for one T.16000M operator movement path.**

This witness proves that, after refreshing a stale USB host session with an
ESP32-S3 reset, operator movement on the T.16000M stick produced both raw USB
report byte deltas and `GET_GENERIC_GAMEPAD_MAPPING` deltas for mapped Generic
Gamepad targets.

It does not prove TWCS throttle, TFRP pedals, button press, or full calibrated
semantic mapping coverage.

## Hardware Context

- ESP32-S3 serial port: `/dev/cu.usbmodem5B5E0200881`
- Powered hub: `2109:2813`
- TWCS throttle: `044f:b687`, device `2`, interface `0`
- T.16000M stick: `044f:b10a`, device `3`, interface `0`
- Firmware version from current demo path: `0.4.2-ble-hid-demo`

After earlier stale-report attempts, the board was reset with:

```bash
espflash reset --port /dev/cu.usbmodem5B5E0200881
```

Post-reset identity:

```text
>> GET_USB_STATUS
USB_STATUS:devices=3;interfaces=2;
>> LIST_USB_DEVICES
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b687|id=3,vid=044f,pid=b10a
```

## Raw USB Delta Precheck

Command:

```bash
python3 tools/usb_report_delta_witness.py \
  --port /dev/cu.usbmodem5B5E0200881 \
  --source 3:0 \
  --label t16000_stick_x_raw_after_reset \
  --watch-seconds 25 \
  --sample-interval 0.10
```

Operator instruction:

```text
T.16000M stick left-right-left-right continuously for 25 seconds.
```

Observed output:

```text
Raw USB report byte deltas:
  byte[0]: 0 -> 8
  byte[3]: 219 -> 158
  byte[4]: 61 -> 31
  byte[5]: 246 -> 54
  byte[6]: 24 -> 26
  byte[7]: 122 -> 123

Saved raw witness: target/usb-report-delta-witness/usb_report_delta_20260430T211144Z_t16000_stick_x_raw_after_reset.json
```

The saved JSON recorded `228` per-sample raw byte changes.

## Mapping Delta Witness

Command:

```bash
python3 tools/mapping_delta_witness.py \
  --port /dev/cu.usbmodem5B5E0200881 \
  --label t16000_stick_x_mapping_after_reset \
  --watch-seconds 25 \
  --sample-interval 0.10
```

Operator instruction:

```text
T.16000M stick left-right-left-right continuously for the full 25 seconds.
```

Observed output:

```text
Mapped target deltas:
  3:0:044f:b10a:axis_01_30 -> x: axis:-635 -> axis:-639 (preferred_axis)
  3:0:044f:b10a:axis_01_31 -> y: axis:-999 -> axis:-995 (preferred_axis)
  3:0:044f:b10a:axis_01_35 -> rz: axis:-1928 -> axis:-1671 (preferred_axis)
Unmapped/source-only deltas:
  2:0:044f:b687:usage_ff00_21_23 -> none: unknown:236 -> unknown:237 (unsupported_control)
  2:0:044f:b687:usage_ff00_21_25 -> none: unknown:208 -> unknown:206 (unsupported_control)
  2:0:044f:b687:usage_ff00_21_27 -> none: unknown:157 -> unknown:156 (unsupported_control)
  2:0:044f:b687:usage_ff00_21_29 -> none: unknown:30 -> unknown:29 (unsupported_control)
  2:0:044f:b687:usage_ff00_21_31 -> none: unknown:207 -> unknown:205 (unsupported_control)
  2:0:044f:b687:usage_ff00_21_33 -> none: unknown:160 -> unknown:159 (unsupported_control)
  2:0:044f:b687:usage_ff00_21_35 -> none: unknown:110 -> unknown:112 (unsupported_control)
  2:0:044f:b687:usage_ff00_21_37 -> none: unknown:215 -> unknown:217 (unsupported_control)

Saved raw witness: target/mapping-delta-witness/mapping_delta_20260430T211224Z_t16000_stick_x_mapping_after_reset.json
```

The saved JSON recorded `96` per-sample mapping changes. Across the captured
mapping samples, selected T.16000M mapped axis ranges were:

```text
3:0:044f:b10a:axis_01_30 -> x:  min=-651,  max=8785
3:0:044f:b10a:axis_01_31 -> y:  min=-3639, max=-899
3:0:044f:b10a:axis_01_35 -> rz: min=-2699, max=-1157
3:0:044f:b10a:axis_01_36 -> z:  min=-32768, max=-32768
```

## Interpretation

- `GET_LAST_USB_REPORT 3:0` changed during operator movement: **pass**.
- `GET_GENERIC_GAMEPAD_MAPPING` changed during operator movement: **pass**.
- Mapped Generic Gamepad target `x` changed from source
  `3:0:044f:b10a:axis_01_30`: **pass**.
- Additional mapped T.16000M axes also changed, which is expected with real
  hand movement but means this is not an isolated single-axis calibration
  witness.
- TWCS vendor-specific source-only values changed during the same period,
  likely from live throttle report noise/updates; they are not presented as
  intentional operator input.
- Earlier no-delta attempts before reset are documented separately in
  `GENERIC_GAMEPAD_MAPPING_DELTA_ATTEMPT_2026-04-30.md` and are not counted as
  successful movement evidence.

## Remaining Gaps

- Clean button-press delta witness.
- Clean TWCS throttle movement witness.
- TFRP pedal movement witness in RJ12 and/or separate USB topology.
- Detach cleanup witness after the current BLE/demo changes.
- Explicit profile/calibration so physical Flight Pack controls map to intended
  Generic Gamepad semantics consistently.
