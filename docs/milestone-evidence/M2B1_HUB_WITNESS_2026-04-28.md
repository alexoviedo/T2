# M2B.1 Hub Attach/Detach Identity Witness

Status: **Partial M2B.1 hardware evidence.**

This transcript proves powered-hub attach/detach identity witness for this revision.
It does not complete M2B.1 by itself because direct-attach witness and HID interface discovery are still not checked in for this revision.

## Hardware

- Date: 2026-04-28
- Firmware commit: `cab1fa5-dirty`
- Target chip: ESP32-S3 rev v0.2, 16 MB flash
- Board/carrier model: TODO exact board model; observed through WCH USB Single Serial adapter
- Serial port: `/dev/cu.usbmodem5B5E0200881`
- Powered hub: HooToo SHUTTLE HT-UC001
- Hub observed USB identity: `VID=2109`, `PID=2813`
- Downstream USB HID device: AFTERGLOW PL-3702 Xbox-style wired gamepad
- Downstream observed USB identity: `VID=0e6f`, `PID=0213`
- Topology: ESP32-S3 USB host path -> HooToo SHUTTLE HT-UC001 -> AFTERGLOW PL-3702

## Commands

```bash
RUSTUP_TOOLCHAIN=esp ./scripts/verify_cloud_equivalent.sh
espflash board-info --chip esp32s3 --port /dev/cu.usbmodem5B5E0200881 --non-interactive
./scripts/flash.sh --chip esp32s3 --port /dev/cu.usbmodem5B5E0200881 --monitor --non-interactive
./scripts/monitor.sh --port /dev/cu.usbmodem5B5E0200881
```

## Board Info

```text
Chip type:         esp32s3 (revision v0.2)
Crystal frequency: 40 MHz
Flash size:        16MB
Features:          WiFi, BLE, Embedded Flash
MAC address:       90:70:69:07:0d:7c
```

## Boot Transcript

```text
I (440) app_init: Application information:
I (444) app_init: Project name:     libespidf
I (448) app_init: App version:      cab1fa5-dirty
I (452) app_init: Compile time:     Apr 28 2026 15:25:31
I (457) app_init: ELF file SHA256:  aad559096...
I (462) app_init: ESP-IDF:          v5.5.3
I (534) main_task: Calling app_main()
[TRACE] ENTERED main()
[TRACE] Uart initialized
[TRACE] UsbIngress initialized
[TRACE] Calling usb.init_host()
[TRACE] usb.init_host() returned
[TRACE] Initializing storage
[TRACE] Initializing app
--- USB2BLE FIRMWARE BOOT ---
Name: usb2ble
Version: 0.2.1-m2b1
Contract Version: 1
Status: M2B.1 Code-path (HW Verification Pending)
Ready for commands.
[TRACE] ENTERED MAIN LOOP
```

## Pre-Plug Baseline

Hub disconnected from ESP32-S3 USB host path.

```text
>> GET_USB_STATUS
USB_STATUS:devices=0;interfaces=0;
>> LIST_USB_DEVICES
USB_DEVICES:
```

## Hub Connected At Boot

The hub was powered and connected to the ESP32-S3 host path. A downstream AFTERGLOW PL-3702 gamepad was connected through the hub.

```text
[ATTACH] Device: ID=1, VID=2109, PID=2813
[ATTACH] Device: ID=2, VID=0e6f, PID=0213

>> GET_USB_STATUS
USB_STATUS:devices=2;interfaces=0;
>> LIST_USB_DEVICES
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=0e6f,pid=0213
```

## Detach Sequence

Downstream gamepad was detached first, then the hub upstream cable was detached from the ESP32-S3 host path.

```text
[DETACH] Device: ID=2

>> GET_USB_STATUS
USB_STATUS:devices=1;interfaces=0;
>> LIST_USB_DEVICES
USB_DEVICES:id=1,vid=2109,pid=2813

[DETACH] Device: ID=1

>> GET_USB_STATUS
USB_STATUS:devices=0;interfaces=0;
>> LIST_USB_DEVICES
USB_DEVICES:
```

## Hot-Plug After Clean Zero State

The hub was plugged back into the ESP32-S3 host path after the app had returned to zero devices.

```text
[ATTACH] Device: ID=3, VID=2109, PID=2813

>> GET_USB_STATUS
USB_STATUS:devices=1;interfaces=0;
>> LIST_USB_DEVICES
USB_DEVICES:id=3,vid=2109,pid=2813

[ATTACH] Device: ID=4, VID=0e6f, PID=0213

>> GET_USB_STATUS
USB_STATUS:devices=2;interfaces=0;
>> LIST_USB_DEVICES
USB_DEVICES:id=3,vid=2109,pid=2813|id=4,vid=0e6f,pid=0213
```

## Results

- Hub attach identity witness: **pass** (`2109:2813`)
- Downstream device identity witness through hub: **pass** (`0e6f:0213`)
- Detach bookkeeping returns to zero devices: **pass**
- HID interface discovery: **not proven** (`interfaces=0`)
- Direct-attach witness for this revision: **not captured in this evidence**
- M2B.1 completion status: **not complete**

