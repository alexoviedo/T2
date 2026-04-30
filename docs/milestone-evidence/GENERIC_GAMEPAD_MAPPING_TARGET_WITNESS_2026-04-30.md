# Generic Gamepad Mapping Target Witness - 2026-04-30

## Scope

This is real ESP32-S3 target smoke evidence for `GET_GENERIC_GAMEPAD_MAPPING`.

It proves that the flashed firmware can return Generic Gamepad auto-mapping
diagnostics from live USB-derived normalized input state. It does not prove an
operator movement/delta witness or final semantic calibration.

## Build And Flash

Target build preflight:

```bash
RUSTUP_TOOLCHAIN=esp ./scripts/check_target_build.sh
```

Result:

```text
Target build preflight passed for xtensa-esp32s3-espidf.
```

Flash command:

```bash
RUSTUP_TOOLCHAIN=esp ./scripts/flash.sh --port /dev/cu.usbmodem5B5E0200881
```

Flash excerpt:

```text
Chip type:         esp32s3 (revision v0.2)
Flash size:        16MB
MAC address:       90:70:69:07:0d:7c
App/part. size:    2,042,544/16,384,000 bytes, 12.47%
Flash complete.
```

## Target Transcript

Monitor command:

```bash
./scripts/monitor.sh --port /dev/cu.usbmodem5B5E0200881
```

Boot excerpt:

```text
--- USB2BLE FIRMWARE BOOT ---
Name: usb2ble
Version: 0.4.2-ble-hid-demo
Contract Version: 1
Status: BLE HID Demo Path (Generic Gamepad Persona)
Ready for commands.
```

Live USB attach/report excerpt:

```text
[ATTACH] Device: ID=1, VID=2109, PID=2813
[ATTACH] Device: ID=2, VID=044f, PID=b687
[INTERFACE] Device: ID=2, IFACE=0, CLASS=03, SUBCLASS=00, PROTOCOL=00
[DESCRIPTOR] Device: ID=2, IFACE=0, BYTES=118
[REPORT] Device: ID=2, IFACE=0, REPORT_ID=0, BYTES=64
[ATTACH] Device: ID=3, VID=044f, PID=b10a
[INTERFACE] Device: ID=3, IFACE=0, CLASS=03, SUBCLASS=00, PROTOCOL=00
[DESCRIPTOR] Device: ID=3, IFACE=0, BYTES=134
[REPORT] Device: ID=3, IFACE=0, REPORT_ID=0, BYTES=64
```

Serial commands:

```text
GET_USB_STATUS
LIST_USB_DEVICES
GET_GENERIC_GAMEPAD_REPORT
GET_GENERIC_GAMEPAD_MAPPING
```

Serial responses:

```text
USB_STATUS:devices=3;interfaces=2;
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b687|id=3,vid=044f,pid=b10a
ENCODED_REPORT:persona=generic_gamepad;report_id=1;bytes=000008c1fc21fc00809fff1f0076f6;
GENERIC_GAMEPAD_MAPPING:profile=generic_auto;persona=generic_gamepad;entries=88;mappings=<88 entries>;
```

Selected exact mapping entries from the target response:

```text
src=3:0:044f:b10a:button_1,target=button_1,value=button:0,reason=button
src=3:0:044f:b10a:button_16,target=button_16,value=button:0,reason=button
src=3:0:044f:b10a:hat_01_39,target=hat,value=hat:15,reason=first_hat
src=2:0:044f:b687:hat_01_39,target=none,value=hat:8,reason=target_already_used
src=3:0:044f:b10a:axis_01_30,target=x,value=axis:-831,reason=preferred_axis
src=3:0:044f:b10a:axis_01_31,target=y,value=axis:-987,reason=preferred_axis
src=3:0:044f:b10a:axis_01_35,target=rz,value=axis:-2442,reason=preferred_axis
src=3:0:044f:b10a:axis_01_36,target=z,value=axis:-32768,reason=next_free_axis
src=2:0:044f:b687:axis_01_30,target=rx,value=axis:-97,reason=next_free_axis
src=2:0:044f:b687:axis_01_31,target=ry,value=axis:31,reason=next_free_axis
src=2:0:044f:b687:axis_01_35,target=none,value=axis:31,reason=axis_slots_full
src=2:0:044f:b687:usage_ff00_21_23,target=none,value=unknown:235,reason=unsupported_control
src=2:0:044f:b687:usage_ff00_21_66,target=none,value=unknown:2,reason=unsupported_control
```

## Proven

- The flashed ESP32-S3 firmware accepts `GET_GENERIC_GAMEPAD_MAPPING`.
- The response is generated from live normalized input state for TWCS
  `044f:b687` and T.16000M stick `044f:b10a`.
- The target response explains mapped controls, duplicate target skips, full
  axis-slot skips, and unsupported vendor usages.

## Not Proven

- Operator movement/delta evidence for `GET_GENERIC_GAMEPAD_MAPPING`.
- TFRP pedals in this exact target mapping diagnostic run.
- Final semantic mapping/calibration for the Flight Pack.
- Xbox Wireless-style BLE output.
