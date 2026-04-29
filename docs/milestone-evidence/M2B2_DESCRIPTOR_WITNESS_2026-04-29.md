# M2B.2 HID Report Descriptor and Input Report Capture Witness

Status: **M2B.2 hardware evidence for one real HID interface.**

This transcript proves that `GET_USB_DESCRIPTOR <device>:<interface>` can return
real HID report descriptor bytes captured from hardware through the powered hub.
It also includes the follow-up report-capture build where
`GET_LAST_USB_REPORT <device>:<interface>` returns a real 64-byte input report
from the same hardware path.

Scope note: this is raw report capture evidence for the THRUSTMASTER T.16000 FCS
HOTAS (`044f:b10a`) through the HooToo hub. It does not prove HID semantic
parsing, normalization, BLE publishing, or report capture for every Flight Pack
component.

## Hardware

- Date: 2026-04-29
- Firmware commit: `cab1fa5-dirty`
- Target chip: ESP32-S3 rev v0.2, 16 MB flash
- Board/carrier model: TODO exact board model; observed through WCH USB Single Serial adapter
- Serial port: `/dev/cu.usbmodem5B5E0200881`
- Powered hub: HooToo SHUTTLE HT-UC001, observed as `VID=2109`, `PID=2813`
- HID device: THRUSTMASTER T.16000 FCS HOTAS, observed as `VID=044f`, `PID=b10a`
- Topology: ESP32-S3 USB host path -> HooToo SHUTTLE HT-UC001 -> THRUSTMASTER T.16000 FCS HOTAS

## Commands

```bash
RUSTUP_TOOLCHAIN=esp ./scripts/verify_cloud_equivalent.sh
./scripts/flash.sh --port /dev/cu.usbmodem5B5E0200881
```

## Negative Finding

An initial descriptor-capture attempt left a control transfer in flight when the
descriptor read did not complete, and ESP-IDF asserted on device close:

```text
[USB_DESCRIPTOR_WARN] Device: ID=2, IFACE=0, STATUS=unavailable
assert failed: usbh_dev_close usbh.c:1058 (dev_obj->dynamic.num_ctrl_xfers_inflight == 0)
```

That build was rejected. The corrected build services both the USB host library
and client event pumps while waiting for the one-shot control transfer, and uses
endpoint zero for the control transfer.

## Boot Baseline

Hub disconnected from ESP32-S3 USB host path.

```text
--- USB2BLE FIRMWARE BOOT ---
Name: usb2ble
Version: 0.2.1-m2b1
Contract Version: 1
Status: M2B.1 Code-path (HW Verification Pending)
Ready for commands.
[TRACE] ENTERED MAIN LOOP

>> GET_USB_STATUS
USB_STATUS:devices=0;interfaces=0;
>> LIST_USB_DEVICES
USB_DEVICES:
```

## Descriptor Capture Run

This earlier run captured the descriptor path before interrupt input-report
capture was implemented.

```text
[USB_IFACE] Device: ID=3, IFACE=0, CLASS=09, SUBCLASS=00, PROTOCOL=00
[ATTACH] Device: ID=3, VID=2109, PID=2813
[USB_IFACE] Device: ID=4, IFACE=0, CLASS=03, SUBCLASS=00, PROTOCOL=00
[USB_DESCRIPTOR] Device: ID=4, IFACE=0, BYTES=134
[ATTACH] Device: ID=4, VID=044f, PID=b10a
[INTERFACE] Device: ID=4, IFACE=0, CLASS=03, SUBCLASS=00, PROTOCOL=00
[DESCRIPTOR] Device: ID=4, IFACE=0, BYTES=134

>> GET_USB_STATUS
USB_STATUS:devices=2;interfaces=1;
>> LIST_USB_DEVICES
USB_DEVICES:id=3,vid=2109,pid=2813|id=4,vid=044f,pid=b10a
>> GET_USB_DESCRIPTOR 4:0
USB_DESCRIPTOR:05010904a101050919012910150025013500450175019510810205010939150025073500463b01651475049501814281010930150026ff3f350046ff3f6500750e950181027502950181010931750e9501810275029501810109350936150026ff00350046ff0065007508950281027508953781010600ff27ffff0000090175089504b1a2c0
>> GET_LAST_USB_REPORT 4:0
ERROR:NotFound

[DETACH] Device: ID=4
[DETACH] Device: ID=3

>> GET_USB_STATUS
USB_STATUS:devices=0;interfaces=0;
>> LIST_USB_DEVICES
USB_DEVICES:
```

## Input Report Capture Run

Report-capture build flashed after `RUSTUP_TOOLCHAIN=esp
./scripts/verify_cloud_equivalent.sh` passed, including the ESP32-S3 target
preflight.

```text
Chip type:         esp32s3 (revision v0.2)
Flash size:        16MB
MAC address:       90:70:69:07:0d:7c
App/part. size:    1,316,448/16,384,000 bytes, 8.03%
Flash complete.
```

Serial capture after reboot with the HooToo hub and THRUSTMASTER T.16000 FCS
HOTAS attached:

```text
--- USB2BLE FIRMWARE BOOT ---
Name: usb2ble
Version: 0.2.2-m2b2
Contract Version: 1
Status: M2B.2 Code-path (Descriptor/Report Witness)
Ready for commands.
[TRACE] ENTERED MAIN LOOP
[USB_IFACE] Device: ID=1, IFACE=0, CLASS=09, SUBCLASS=00, PROTOCOL=00
[ATTACH] Device: ID=1, VID=2109, PID=2813
[USB_IFACE] Device: ID=2, IFACE=0, CLASS=03, SUBCLASS=00, PROTOCOL=00
[USB_DESCRIPTOR] Device: ID=2, IFACE=0, BYTES=134
[ATTACH] Device: ID=2, VID=044f, PID=b10a
[INTERFACE] Device: ID=2, IFACE=0, CLASS=03, SUBCLASS=00, PROTOCOL=00
[DESCRIPTOR] Device: ID=2, IFACE=0, BYTES=134
>> GET_USB_STATUS
>> LIST_USB_DEVICES
>> GET_LAST_USB_REPORT 2:0
[USB_REPORT] Device: ID=2, IFACE=0, BYTES=64
[REPORT] Device: ID=2, IFACE=0, REPORT_ID=0, BYTES=64
USB_STATUS:devices=2;interfaces=1;
[USB_REPORT] Device: ID=2, IFACE=0, BYTES=64
[REPORT] Device: ID=2, IFACE=0, REPORT_ID=0, BYTES=64
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b10a
[USB_REPORT] Device: ID=2, IFACE=0, BYTES=64
[REPORT] Device: ID=2, IFACE=0, REPORT_ID=0, BYTES=64
[USB_REPORT] Device: ID=2, IFACE=0, BYTES=64
[REPORT] Device: ID=2, IFACE=0, REPORT_ID=0, BYTES=64
USB_REPORT:00000f711f2c1f7600070000000b01ffffffffffffffffffffff00000000f17f1080f041c10f534be555f15556506917ed1b3d5800006a765883de46ffffff00
[USB_REPORT] Device: ID=2, IFACE=0, BYTES=64
[REPORT] Device: ID=2, IFACE=0, REPORT_ID=0, BYTES=64
```

## Results

- HID report descriptor capture through hub: **pass** (`134` bytes from `044f:b10a`, interface `0`)
- Control-plane `GET_USB_DESCRIPTOR 4:0`: **pass** (hex payload returned)
- Detach bookkeeping returns to zero devices/interfaces: **pass**
- Live interrupt input-report capture through hub: **pass** (`64` bytes from `044f:b10a`, interface `0`)
- Control-plane `GET_LAST_USB_REPORT 2:0`: **pass** (`USB_REPORT:<128 hex chars>`)
- HID semantic parsing: **not implemented**
- Flight Pack three-device report coverage: **not captured in this witness**
