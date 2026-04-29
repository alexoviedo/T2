# M2B.2 HID Report Descriptor Capture Witness

Status: **Partial M2B.2 hardware evidence.**

This transcript proves that `GET_USB_DESCRIPTOR <device>:<interface>` can return
real HID report descriptor bytes captured from hardware through the powered hub.
It does not complete M2B.2 because `GET_LAST_USB_REPORT` still returns
`ERROR:NotFound`; live interrupt-report capture remains pending.

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
./scripts/flash.sh --chip esp32s3 --port /dev/cu.usbmodem5B5E0200881 --monitor --non-interactive
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

## Results

- HID report descriptor capture through hub: **pass** (`134` bytes from `044f:b10a`, interface `0`)
- Control-plane `GET_USB_DESCRIPTOR 4:0`: **pass** (hex payload returned)
- Detach bookkeeping returns to zero devices/interfaces: **pass**
- Last input report capture: **not implemented** (`GET_LAST_USB_REPORT 4:0` returned `ERROR:NotFound`)
- M2B.2 completion status: **not complete**
