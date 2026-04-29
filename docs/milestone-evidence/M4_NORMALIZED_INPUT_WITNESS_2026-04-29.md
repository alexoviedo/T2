# M4 Normalized Input Witness

Status: **M4 baseline normalized-input hardware evidence for one real HID interface.**

This transcript proves that the ESP32-S3 target can decode a real HID input
report and expose a normalized control frame for the THRUSTMASTER T.16000 FCS
stick interface through the HooToo powered hub. It does not prove operator
movement deltas, detach cleanup, BLE publishing, or normalized coverage for all
three simultaneous Flight Pack USB devices.

## Hardware

- Date: 2026-04-29
- Firmware commit: `f92c958-dirty`
- Target chip: ESP32-S3 rev v0.2, 16 MB flash
- Board/carrier model: TODO exact board model; observed through WCH USB Single Serial adapter
- Serial port: `/dev/cu.usbmodem5B5E0200881`
- Powered hub: HooToo SHUTTLE HT-UC001, observed as `VID=2109`, `PID=2813`
- HID device observed in this run: THRUSTMASTER T.16000 FCS / T.16000M FCS stick interface, observed as `VID=044f`, `PID=b10a`
- Topology: ESP32-S3 USB host path -> HooToo SHUTTLE HT-UC001 -> THRUSTMASTER T.16000 FCS stick interface

## Commands

```bash
RUSTUP_TOOLCHAIN=esp ./scripts/verify_cloud_equivalent.sh
./scripts/flash.sh --port /dev/cu.usbmodem5B5E0200881
```

## Verification

`RUSTUP_TOOLCHAIN=esp ./scripts/verify_cloud_equivalent.sh` passed:

- `cargo fmt --all -- --check`
- `cargo clippy --workspace --all-targets --locked -- -D warnings`
- `cargo build --workspace --locked`
- `cargo test --workspace --locked`
- `bash -n scripts/build.sh scripts/check_target_build.sh scripts/fix_esp_env.sh scripts/flash.sh scripts/monitor.sh scripts/verify_cloud_equivalent.sh`
- `./scripts/check_target_build.sh`

Flash output:

```text
Chip type:         esp32s3 (revision v0.2)
Flash size:        16MB
MAC address:       90:70:69:07:0d:7c
App/part. size:    1,369,632/16,384,000 bytes, 8.36%
Flash complete.
```

## Hardware Normalized-Input Run

The serial capture below is filtered only to keep repeated report spam concise;
command responses and the shown device/report lines are target output from the
same run.

```text
--- M4 NORMALIZED INPUT WITNESS START ---
[TRACE] ENTERED main()
[TRACE] Uart initialized
[TRACE] UsbIngress initialized
[TRACE] Calling usb.init_host()
[TRACE] usb.init_host() returned
[TRACE] Initializing storage
[TRACE] Initializing app
Name: usb2ble
Version: 0.4.0-m4
Contract Version: 1
Status: M4 Code-path (Normalized Input Witness)
Ready for commands.
[TRACE] ENTERED MAIN LOOP
[ATTACH] Device: ID=1, VID=2109, PID=2813
>> GET_INFO
>> GET_USB_STATUS
>> LIST_USB_DEVICES
INFO:version=1;name=usb2ble;persona=none;
USB_STATUS:devices=1;interfaces=0;
USB_DEVICES:id=1,vid=2109,pid=2813
[ATTACH] Device: ID=2, VID=044f, PID=b10a
[INTERFACE] Device: ID=2, IFACE=0, CLASS=03, SUBCLASS=00, PROTOCOL=00
[DESCRIPTOR] Device: ID=2, IFACE=0, BYTES=134
[REPORT] Device: ID=2, IFACE=0, REPORT_ID=0, BYTES=64
[REPORT] Device: ID=2, IFACE=0, REPORT_ID=0, BYTES=64
[REPORT] Device: ID=2, IFACE=0, REPORT_ID=0, BYTES=64
[REPORT] Device: ID=2, IFACE=0, REPORT_ID=0, BYTES=64
# observed_descriptor_keys=[(2, 0)]
# observed_report_keys=[(2, 0)]
>> GET_HID_SUMMARY 2:0
>> GET_LAST_USB_REPORT 2:0
>> GET_NORMALIZED_INPUT 2:0
HID_SUMMARY:axes=4;buttons=16;hats=1;report_ids=0;axis_usages=01:30,01:31,01:35,01:36;button_usages=1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16;hat_usages=01:39;
[REPORT] Device: ID=2, IFACE=0, REPORT_ID=0, BYTES=64
USB_REPORT:00000f721f311f7400070000000b01ffffffffffffffffffffff00000000f17f1080f041c10f534be555f15556506917ed1b3d5800006a765883de46ffffff00
[REPORT] Device: ID=2, IFACE=0, REPORT_ID=0, BYTES=64
NORMALIZED_INPUT:controls=21;button_1=button:0;button_2=button:0;button_3=button:0;button_4=button:0;button_5=button:0;button_6=button:0;button_7=button:0;button_8=button:0;button_9=button:0;button_10=button:0;button_11=button:0;button_12=button:0;button_13=button:0;button_14=button:0;button_15=button:0;button_16=button:0;hat_01_39=hat:15;axis_01_30=axis:-567;axis_01_31=axis:-827;axis_01_35=axis:-2956;axis_01_36=axis:-32768;
[REPORT] Device: ID=2, IFACE=0, REPORT_ID=0, BYTES=64
[REPORT] Device: ID=2, IFACE=0, REPORT_ID=0, BYTES=64
# report_lines_seen=24
--- M4 NORMALIZED INPUT WITNESS END ---
```

## Results

- Target booted with firmware version `0.4.0-m4`: **pass**
- HooToo powered hub enumerated as `2109:2813`: **pass**
- T.16000 stick HID interface enumerated as `044f:b10a`, interface `0`: **pass**
- Target captured a 134-byte HID report descriptor: **pass**
- Target captured 64-byte input reports: **pass**
- `GET_HID_SUMMARY 2:0` returned 4 axes, 16 buttons, 1 hat, report ID 0: **pass**
- `GET_NORMALIZED_INPUT 2:0` returned 21 normalized controls from the latest real input report: **pass**
- Operator movement/press delta witness: **not captured**
- Normalized detach cleanup witness: **not captured**
- Normalized coverage for TWCS throttle and TFRP pedals in the three-device Flight Pack: **not captured in this run**
