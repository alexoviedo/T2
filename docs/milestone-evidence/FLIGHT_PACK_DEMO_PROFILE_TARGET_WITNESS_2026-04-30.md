# Flight Pack Demo Profile Target Witness - 2026-04-30

Status: **accepted target hardware evidence for `flight_pack_demo` profile selection.**

This witness proves that the flashed ESP32-S3 target selects the curated
`flight_pack_demo` profile when the HooToo hub enumerates both the TWCS throttle
and the T.16000M stick.

## Hardware Context

- ESP32-S3 serial port: `/dev/cu.usbmodem5B5E0200881`
- Powered hub: `2109:2813`
- TWCS throttle: `044f:b687`, device `2`, interface `0`
- T.16000M stick: `044f:b10a`, device `3`, interface `0`
- Firmware version path: `0.4.2-ble-hid-demo`

## Commands

```bash
python3 tools/serial_command.py \
  --port /dev/cu.usbmodem5B5E0200881 \
  GET_USB_STATUS \
  LIST_USB_DEVICES \
  GET_GENERIC_GAMEPAD_MAPPING \
  GET_GENERIC_GAMEPAD_REPORT
```

## Transcript

```text
>> GET_USB_STATUS
USB_STATUS:devices=3;interfaces=2;
>> LIST_USB_DEVICES
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b687|id=3,vid=044f,pid=b10a
>> GET_GENERIC_GAMEPAD_MAPPING
GENERIC_GAMEPAD_MAPPING:profile=flight_pack_demo;persona=generic_gamepad;entries=88;mappings=<omitted>;
src=3:0:044f:b10a:axis_01_30,target=x,value=axis:-611,reason=profile_rule
src=3:0:044f:b10a:axis_01_31,target=y,value=axis:-927,reason=profile_rule
src=2:0:044f:b687:axis_01_32,target=z,value=axis:32767,reason=profile_rule
src=2:0:044f:b687:axis_01_36,target=rx,value=axis:31,reason=profile_rule
src=3:0:044f:b10a:axis_01_36,target=ry,value=axis:-32768,reason=profile_rule
src=3:0:044f:b10a:axis_01_35,target=rz,value=axis:-643,reason=profile_rule
>> GET_GENERIC_GAMEPAD_REPORT
ENCODED_REPORT:persona=generic_gamepad;report_id=1;bytes=0000089dfd61fcff7f1f0000807dfd;
```

The full `GET_GENERIC_GAMEPAD_MAPPING` line was intentionally not pasted here
because it contains all `88` entries on one long serial line. The selected
entries above are exact entries extracted from that response.

## Interpretation

- The target enumerated the HooToo hub, TWCS, and T.16000M stick: **pass**.
- `GET_GENERIC_GAMEPAD_MAPPING` selected `profile=flight_pack_demo`: **pass**.
- T.16000M stick axes mapped to `x`, `y`, `ry`, and `rz` by explicit profile
  rules: **pass**.
- TWCS axes mapped to `z` and `rx` by explicit profile rules: **pass**.
- `GET_GENERIC_GAMEPAD_REPORT` encoded a Generic Gamepad report from the same
  selected mapping path: **pass**.

## Remaining Demo Work

- Publish this curated report over BLE and capture host-visible input.
- Add calibration/deadzone metadata after the demo path is stable.
- Replace provisional TFRP/TWCS axis assignments with named semantic controls
  once the exact RJ12 report fields are fully labeled.
