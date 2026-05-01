# Generic Gamepad Mapping Delta Attempt - 2026-04-30

Status: **attempted, not accepted as milestone evidence.**

This run tried to capture operator movement deltas for the TWCS throttle through
the powered USB hub. Both the mapping-level watch and a lower-level raw
`GET_LAST_USB_REPORT` watch returned identical samples, so this does **not**
prove operator movement capture.

## Hardware Context

- ESP32-S3 serial port: `/dev/cu.usbmodem5B5E0200881`
- Powered hub attached to ESP32-S3
- TWCS throttle present as `044f:b687`, device `2`, interface `0`
- T.16000M stick present as `044f:b10a`, device `3`, interface `0`

## Mapping Watch Attempt

Command:

```bash
python3 tools/mapping_delta_witness.py \
  --port /dev/cu.usbmodem5B5E0200881 \
  --label twcs_throttle_sweep \
  --watch-seconds 15 \
  --sample-interval 0.15
```

Operator instruction used:

```text
TWCS throttle lever only, back and forward repeatedly, for the full 15 seconds.
```

Observed output:

```text
Capturing baseline GET_GENERIC_GAMEPAD_MAPPING...
Baseline entries: 88

Move exactly one control during the watch window.
Press Enter to start the watch window...
Watching for 15.0s...

Mapped target deltas:
  none
Unmapped/source-only deltas:
  none

Saved raw witness: target/mapping-delta-witness/mapping_delta_20260430T210247Z_twcs_throttle_sweep.json
```

Result: no mapped or unmapped normalized/mapping deltas were captured.

## Raw Report Watch Attempt

To separate mapping behavior from raw USB capture behavior, a lower-level raw
report watcher was added and run against the TWCS interface.

Command:

```bash
python3 tools/usb_report_delta_witness.py \
  --port /dev/cu.usbmodem5B5E0200881 \
  --source 2:0 \
  --label twcs_throttle_sweep_raw \
  --watch-seconds 15 \
  --sample-interval 0.15
```

Observed output:

```text
Capturing baseline GET_LAST_USB_REPORT 2:0...
Baseline bytes: 64

Move exactly one control during the watch window.
Press Enter to start the watch window...
Watching for 15.0s...

Raw USB report byte deltas:
  none

Saved raw witness: target/usb-report-delta-witness/usb_report_delta_20260430T210529Z_twcs_throttle_sweep_raw.json
```

Exact raw report returned for every sample:

```text
USB_REPORT:01fe0100020002ff03ff031202ff03ffff080000eb3fd43f9f0d0242c8419f152010d61acacae8d629298b8a8485a0502d2da0510abc02cd5bab26eb00008002
```

Result: no raw byte deltas were captured.

## Interpretation

- This is not evidence that TWCS operator movement is mapped correctly.
- This is not evidence that mapping is broken.
- The latest run shows that no raw report change was observed during the
  timed window, so the next hardware test should start with
  `tools/usb_report_delta_witness.py` and prove raw byte movement first.

## Next Test

Use one very obvious physical control and keep the operator timing simple:

```bash
python3 tools/usb_report_delta_witness.py \
  --port /dev/cu.usbmodem5B5E0200881 \
  --source 2:0 \
  --label twcs_button_or_hat_raw \
  --watch-seconds 20 \
  --sample-interval 0.20
```

After raw byte deltas are captured, immediately repeat with:

```bash
python3 tools/mapping_delta_witness.py \
  --port /dev/cu.usbmodem5B5E0200881 \
  --label twcs_button_or_hat_mapping \
  --watch-seconds 20 \
  --sample-interval 0.20
```

Only the second run can count as `GET_GENERIC_GAMEPAD_MAPPING` operator delta
evidence, and only if it captures a changed mapped or source-only entry.
