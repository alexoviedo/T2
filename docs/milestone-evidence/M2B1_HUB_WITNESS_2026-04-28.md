# M2B.1 Hub Attach/Detach Identity and HID Interface Witness

Status: **Partial M2B.1 hardware evidence.**

This transcript proves powered-hub attach/detach identity witness for this revision.
It also captures interface-class witness output showing that the AFTERGLOW PL-3702
enumerates with vendor-specific interfaces, not HID class interfaces.
It then captures a separate USB keyboard through the same powered hub proving
HID class interface discovery and app bookkeeping (`interfaces=2`) on real
hardware.
It also captures a THRUSTMASTER T.16000 FCS HOTAS through the same powered hub
proving HID class interface discovery and app bookkeeping (`interfaces=1`) for
a flight-control device.

It does not complete M2B.1 by itself because direct-attach witness is blocked by
the currently available cabling/port geometry.

## Hardware

- Date: 2026-04-28
- Firmware commit: `cab1fa5-dirty`
- Target chip: ESP32-S3 rev v0.2, 16 MB flash
- Board/carrier model: TODO exact board model; observed through WCH USB Single Serial adapter
- Serial port: `/dev/cu.usbmodem5B5E0200881`
- Powered hub: HooToo SHUTTLE HT-UC001
- Hub observed USB identity: `VID=2109`, `PID=2813`
- Downstream USB device: AFTERGLOW PL-3702 Xbox-style wired gamepad
- Downstream observed USB identity: `VID=0e6f`, `PID=0213`
- Downstream observed interface classes: `ff:5d:01`, `ff:5d:03`, `ff:5d:02`, `ff:fd:13`
- HID-class USB device: USB keyboard, exact model not captured
- HID-class USB device observed identity: `VID=30fa`, `PID=2031`
- HID-class USB device observed interfaces: `03:01:01`, `03:00:02`
- HID-class HOTAS device: THRUSTMASTER T.16000 FCS HOTAS
- HID-class HOTAS observed identity: `VID=044f`, `PID=b10a`
- HID-class HOTAS observed interface: `03:00:00`
- Topology: ESP32-S3 USB host path -> HooToo SHUTTLE HT-UC001 -> AFTERGLOW PL-3702
- HID topology: ESP32-S3 USB host path -> HooToo SHUTTLE HT-UC001 -> USB keyboard
- HOTAS topology: ESP32-S3 USB host path -> HooToo SHUTTLE HT-UC001 -> THRUSTMASTER T.16000 FCS HOTAS
- Direct topology: not captured; available physical connectors did not allow direct USB device-to-ESP32-S3 host-path attachment.

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

## Instrumented Hub-Only Interface-Class Run

The firmware was reflashed with target witness lines that print each interface
descriptor's class/subclass/protocol before HID filtering. The HooToo hub and
AFTERGLOW controller were connected through the hub; direct attachment was not
physically possible with the available connectors.

```text
>> GET_USB_STATUS
USB_STATUS:devices=0;interfaces=0;
>> LIST_USB_DEVICES
USB_DEVICES:

[USB_IFACE] Device: ID=3, IFACE=0, CLASS=09, SUBCLASS=00, PROTOCOL=00
[ATTACH] Device: ID=3, VID=2109, PID=2813

[USB_IFACE] Device: ID=4, IFACE=0, CLASS=ff, SUBCLASS=5d, PROTOCOL=01
[USB_IFACE] Device: ID=4, IFACE=1, CLASS=ff, SUBCLASS=5d, PROTOCOL=03
[USB_IFACE] Device: ID=4, IFACE=2, CLASS=ff, SUBCLASS=5d, PROTOCOL=02
[USB_IFACE] Device: ID=4, IFACE=3, CLASS=ff, SUBCLASS=fd, PROTOCOL=13
[ATTACH] Device: ID=4, VID=0e6f, PID=0213

>> GET_USB_STATUS
USB_STATUS:devices=2;interfaces=0;
>> LIST_USB_DEVICES
USB_DEVICES:id=3,vid=2109,pid=2813|id=4,vid=0e6f,pid=0213

[DETACH] Device: ID=3
[DETACH] Device: ID=4

>> GET_USB_STATUS
USB_STATUS:devices=0;interfaces=0;
>> LIST_USB_DEVICES
USB_DEVICES:
```

## Hub-Attached USB Keyboard HID-Class Run

The powered HooToo hub was connected to the ESP32-S3 host path with a USB
keyboard connected downstream. This run proves that HID-class interface
discovery reaches the app-level bookkeeping surface through the hub topology.

```text
I (570) main_task: Calling app_main()
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
[USB_IFACE] Device: ID=1, IFACE=0, CLASS=09, SUBCLASS=00, PROTOCOL=00
[ATTACH] Device: ID=1, VID=2109, PID=2813
W (4100) HCD DWC: Low-speed, extra delay will be applied in ISR
[USB_IFACE] Device: ID=2, IFACE=0, CLASS=03, SUBCLASS=01, PROTOCOL=01
[USB_IFACE] Device: ID=2, IFACE=1, CLASS=03, SUBCLASS=00, PROTOCOL=02
[ATTACH] Device: ID=2, VID=30fa, PID=2031
[INTERFACE] Device: ID=2, IFACE=0, CLASS=03, SUBCLASS=01, PROTOCOL=01
[INTERFACE] Device: ID=2, IFACE=1, CLASS=03, SUBCLASS=00, PROTOCOL=02

>> GET_USB_STATUS
USB_STATUS:devices=2;interfaces=2;
>> LIST_USB_DEVICES
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=30fa,pid=2031

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

## Hub-Attached THRUSTMASTER T.16000 FCS HOTAS HID-Class Run

The powered HooToo hub was connected to the ESP32-S3 host path with a
THRUSTMASTER T.16000 FCS HOTAS connected downstream. This run proves
HID-class interface discovery reaches the app-level bookkeeping surface for
the HOTAS through the hub topology.

```text
I (570) main_task: Calling app_main()
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
[USB_IFACE] Device: ID=1, IFACE=0, CLASS=09, SUBCLASS=00, PROTOCOL=00
[ATTACH] Device: ID=1, VID=2109, PID=2813
[USB_IFACE] Device: ID=2, IFACE=0, CLASS=03, SUBCLASS=00, PROTOCOL=00
[ATTACH] Device: ID=2, VID=044f, PID=b10a
[INTERFACE] Device: ID=2, IFACE=0, CLASS=03, SUBCLASS=00, PROTOCOL=00

>> GET_USB_STATUS
USB_STATUS:devices=2;interfaces=1;
>> LIST_USB_DEVICES
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b10a

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

## Results

- Hub attach identity witness: **pass** (`2109:2813`)
- Downstream device identity witness through hub: **pass** (`0e6f:0213`)
- Hub interface-class witness: **pass** (`CLASS=09`, hub)
- Downstream interface-class witness: **pass** (`CLASS=ff`, vendor-specific interfaces)
- HID-class keyboard identity witness through hub: **pass** (`30fa:2031`)
- HID interface discovery through hub: **pass** (`interfaces=2`; `CLASS=03`)
- HID-class HOTAS identity witness through hub: **pass** (`044f:b10a`)
- HOTAS HID interface discovery through hub: **pass** (`interfaces=1`; `CLASS=03`)
- Detach bookkeeping returns to zero devices: **pass**
- AFTERGLOW HID-class discovery: **not satisfied by this controller** (`interfaces=0`; no `CLASS=03` interface observed)
- Direct-attach witness for this revision: **not captured**; blocked by available physical cabling/port geometry
- M2B.1 completion status: **not complete**
