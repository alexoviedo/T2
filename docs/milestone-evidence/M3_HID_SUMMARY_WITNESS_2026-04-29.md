# M3 HID Descriptor Summary Witness

Status: **M3 parser and summary hardware evidence for one real HID interface.**

This transcript proves that the hardware-captured THRUSTMASTER T.16000 FCS
HOTAS report descriptor can be parsed into a capability summary on both host and
ESP32-S3 target code paths. It does not prove full HID input decoding or
normalization; those remain M4 scope.

## Hardware

- Date: 2026-04-29
- Firmware commit: `cab1fa5-dirty`
- Target chip: ESP32-S3 rev v0.2, 16 MB flash
- Board/carrier model: TODO exact board model; observed through WCH USB Single Serial adapter
- Serial port: `/dev/cu.usbmodem5B5E0200881`
- Powered hub: HooToo SHUTTLE HT-UC001, observed as `VID=2109`, `PID=2813`
- HID device: THRUSTMASTER T.16000 FCS HOTAS, observed as `VID=044f`, `PID=b10a`
- Topology: ESP32-S3 USB host path -> HooToo SHUTTLE HT-UC001 -> THRUSTMASTER T.16000 FCS HOTAS

## Host Fixture

Committed fixture:

```text
crates/usb2ble-hid/fixtures/thrustmaster_t16000_fcs_044f_b10a_report_descriptor.hex
```

Host parser tests prove the descriptor fixture parses to:

- Report IDs: `0`
- Buttons: `16`
- Hats: `1` (`01:39`)
- Axes: `4` (`01:30`, `01:31`, `01:35`, `01:36`)
- Input fields: `21`

## Commands

```bash
RUSTUP_TOOLCHAIN=esp ./scripts/verify_cloud_equivalent.sh
./scripts/flash.sh --port /dev/cu.usbmodem5B5E0200881
```

## Hardware Summary Run

```text
Chip type:         esp32s3 (revision v0.2)
Flash size:        16MB
MAC address:       90:70:69:07:0d:7c
App/part. size:    1,346,208/16,384,000 bytes, 8.22%
Flash complete.
```

Serial capture after reboot with the HooToo hub and THRUSTMASTER T.16000 FCS
HOTAS attached:

```text
--- USB2BLE FIRMWARE BOOT ---
Name: usb2ble
Version: 0.3.0-m3
Contract Version: 1
Status: M3 Code-path (HID Summary Witness)
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
>> GET_HID_SUMMARY 2:0
>> GET_LAST_USB_REPORT 2:0
[USB_REPORT] Device: ID=2, IFACE=0, BYTES=64
[REPORT] Device: ID=2, IFACE=0, REPORT_ID=0, BYTES=64
USB_STATUS:devices=2;interfaces=1;
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b10a
HID_SUMMARY:axes=4;buttons=16;hats=1;report_ids=0;axis_usages=01:30,01:31,01:35,01:36;button_usages=1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16;hat_usages=01:39;
USB_REPORT:00000f711f2a1f7600070000000b01ffffffffffffffffffffff00000000f17f1080f041c10f534be555f15556506917ed1b3d5800006a765883de46ffffff00
```

## Results

- Host parser fixture: **pass**
- Target `GET_HID_SUMMARY 2:0`: **pass**
- Host/target capability summary parity for `044f:b10a`: **pass**
- Full target IR dump: **not implemented**
- HID report decoding and normalized live controls: **not implemented**
