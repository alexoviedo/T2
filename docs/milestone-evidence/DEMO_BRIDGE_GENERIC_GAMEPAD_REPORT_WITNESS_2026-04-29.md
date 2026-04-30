# Demo Bridge Generic Gamepad Report Witness

Status: **real target smoke witness for USB state to encoded Generic Gamepad report.**

This is not BLE publication evidence. It proves that the flashed ESP32-S3
firmware can take current live USB HID report state, run the app-level
normalization/merge/mapping/persona-encoding path, and return BLE-ready Generic
Gamepad report bytes over the serial control plane.

## Hardware

- Date: 2026-04-29
- Firmware version: `0.4.1-demo-bridge`
- Target chip: ESP32-S3 rev v0.2, 16 MB flash
- Board/carrier model: TODO exact board model; observed through WCH USB Single Serial adapter
- Serial port: `/dev/cu.usbmodem5B5E0200881`
- Powered hub: HooToo SHUTTLE HT-UC001, observed as `VID=2109`, `PID=2813`
- Flight Pack topology:

```text
TFRP pedals -> RJ12 -> TWCS throttle
ESP32-S3 USB host path -> HooToo SHUTTLE HT-UC001 -> TWCS throttle USB + T.16000M stick USB
```

## Commands

```bash
RUSTUP_TOOLCHAIN=esp ./scripts/verify_cloud_equivalent.sh
./scripts/flash.sh --port /dev/cu.usbmodem5B5E0200881
```

Verifier result:

```text
Target build preflight passed for xtensa-esp32s3-espidf.
```

Flash result:

```text
Chip type:         esp32s3 (revision v0.2)
Flash size:        16MB
MAC address:       90:70:69:07:0d:7c
App/part. size:    1,469,760/16,384,000 bytes, 8.97%
Flash complete.
```

## Target Transcript

```text
--- DEMO BRIDGE SMOKE START ---
[REPORT] Device: ID=3, IFACE=0, REPORT_ID=0, BYTES=64
[REPORT] Device: ID=2, IFACE=0, REPORT_ID=0, BYTES=64
>> GET_INFO
>> GET_STATUS
>> GET_USB_STATUS
>> LIST_USB_DEVICES
>> GET_GENERIC_GAMEPAD_REPORT
INFO:version=1;name=usb2ble;persona=none;
STATUS:ble=Idle;profile=none;bonds=false;
USB_STATUS:devices=3;interfaces=2;
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b687|id=3,vid=044f,pid=b10a
ENCODED_REPORT:persona=generic_gamepad;report_id=1;bytes=000008f9fc69fb00809fff1f0073f3;
--- DEMO BRIDGE SMOKE END ---
```

## Result

- RJ12 two-USB Flight Pack topology produced live report traffic from both HID sources: **pass**
- `GET_GENERIC_GAMEPAD_REPORT` returned a Generic Gamepad encoded report: **pass**
- BLE advertising/connect/publish: **not tested**
- Host-visible BLE gamepad input: **not tested**
