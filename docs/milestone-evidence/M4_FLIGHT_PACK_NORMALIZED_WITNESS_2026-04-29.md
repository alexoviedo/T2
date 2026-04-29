# M4 Flight Pack Normalized Input Witness

Status: **M4 expanded normalized-input evidence with remaining detach and simultaneous-stream gaps.**

This transcript extends the baseline M4 witness to the THRUSTMASTER T.16000M
FCS FLIGHT PACK through the HooToo powered hub. It proves normalized input for
the TFRP pedals and T.16000 stick together, and for the TWCS throttle when it is
the active downstream HID device on the same hub. It also captures a real
full-pack limitation: the third interrupt stream can fail at interface-claim
time with `ESP_ERR_NOT_SUPPORTED`.

It does not prove detach cleanup, button press transitions, or simultaneous
normalized reports from all three Flight Pack HID interfaces.

## Hardware

- Date: 2026-04-29
- Firmware commit: `f92c958-dirty`
- Target chip: ESP32-S3 rev v0.2, 16 MB flash
- Board/carrier model: TODO exact board model; observed through WCH USB Single Serial adapter
- Serial port: `/dev/cu.usbmodem5B5E0200881`
- Powered hub: HooToo SHUTTLE HT-UC001, observed as `VID=2109`, `PID=2813`
- Flight Pack devices observed:
  - TFRP rudder pedals, observed as `VID=044f`, `PID=b679`
  - T.16000M FCS stick, observed as `VID=044f`, `PID=b10a`
  - TWCS throttle, observed as `VID=044f`, `PID=b687`

## Commands

```bash
RUSTUP_TOOLCHAIN=esp ./scripts/verify_cloud_equivalent.sh
./scripts/flash.sh --port /dev/cu.usbmodem5B5E0200881
```

Verification passed after these M4 extensions:

- throttled target report witness logs to reduce serial pressure
- stage-coded target interrupt-capture warnings
- HID report-ID inference from report payload byte
- unique normalized IDs for repeated unknown vendor usages

Flash output for the final evidence firmware:

```text
Chip type:         esp32s3 (revision v0.2)
Flash size:        16MB
MAC address:       90:70:69:07:0d:7c
App/part. size:    1,374,576/16,384,000 bytes, 8.39%
Flash complete.
```

## Full-Pack Run: Pedals + Stick Normalized, TWCS Attach Limitation

Connection topology:

```text
ESP32-S3 USB host path -> HooToo SHUTTLE HT-UC001 -> TFRP pedals + T.16000 stick + TWCS throttle
```

Key target transcript:

```text
--- M4 FINAL COMPONENT COVERAGE CAPTURE START ---
Name: usb2ble
Version: 0.4.0-m4
Status: M4 Code-path (Normalized Input Witness)
[ATTACH] Device: ID=1, VID=2109, PID=2813
[ATTACH] Device: ID=2, VID=044f, PID=b679
[INTERFACE] Device: ID=2, IFACE=0, CLASS=03, SUBCLASS=00, PROTOCOL=00
[DESCRIPTOR] Device: ID=2, IFACE=0, BYTES=46
[REPORT] Device: ID=2, IFACE=0, REPORT_ID=0, BYTES=43 # 044f:b679
HID_SUMMARY:axes=3;buttons=0;hats=0;report_ids=0;axis_usages=01:30,01:31,01:32;button_usages=;hat_usages=;
[ATTACH] Device: ID=3, VID=044f, PID=b10a
[INTERFACE] Device: ID=3, IFACE=0, CLASS=03, SUBCLASS=00, PROTOCOL=00
[DESCRIPTOR] Device: ID=3, IFACE=0, BYTES=134
[REPORT] Device: ID=3, IFACE=0, REPORT_ID=0, BYTES=64 # 044f:b10a
HID_SUMMARY:axes=4;buttons=16;hats=1;report_ids=0;axis_usages=01:30,01:31,01:35,01:36;button_usages=1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16;hat_usages=01:39;
[USB_REPORT_WARN] Device: ID=4, IFACE=0, STATUS=unavailable, STAGE=1, ERR=262, EP=81, MPS=64, INTERVAL=5
[ATTACH] Device: ID=4, VID=044f, PID=b687
[INTERFACE] Device: ID=4, IFACE=0, CLASS=03, SUBCLASS=00, PROTOCOL=00
[DESCRIPTOR] Device: ID=4, IFACE=0, BYTES=118
HID_SUMMARY:axes=8;buttons=14;hats=1;report_ids=1,0;axis_usages=01:30,01:31,01:35,01:33,01:34,01:36,01:37,01:32;button_usages=1,2,3,4,5,6,7,8,9,10,11,12,13,14;hat_usages=01:39;
USB_STATUS:devices=4;interfaces=3;
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b679|id=3,vid=044f,pid=b10a|id=4,vid=044f,pid=b687
USB_REPORT:ff03ff03cf00e02c6515aa1b044fff00000175015005600550056005500550047506500475042504250000
NORMALIZED_INPUT:controls=40;axis_01_30=axis:32767;axis_01_31=axis:32767;axis_01_32=axis:-8874;usage_ff00_20_3=unknown:186;...
USB_REPORT:00000f561ffa1e7400070000000b01ffffffffffffffffffffff00000000f17f1080f041c10f534be555f15556506917ed1b3d5800006a765883de46ffffff00
NORMALIZED_INPUT:controls=21;button_1=button:0;button_2=button:0;button_3=button:0;button_4=button:0;button_5=button:0;button_6=button:0;button_7=button:0;button_8=button:0;button_9=button:0;button_10=button:0;button_11=button:0;button_12=button:0;button_13=button:0;button_14=button:0;button_15=button:0;button_16=button:0;hat_01_39=hat:15;axis_01_30=axis:-679;axis_01_31=axis:-1047;axis_01_35=axis:-2956;axis_01_36=axis:-32768;
USB_REPORT:00000000fd03c35efb58a75f044fff00000175015005600550056005500550047506500475042504250000
NORMALIZED_INPUT:controls=40;axis_01_30=axis:-32768;axis_01_31=axis:-32768;axis_01_32=axis:32638;usage_ff00_20_3=unknown:193;...
USB_REPORT:ff039c022e028744022f251b044fff00000175015005600550056005500550047506500475042504250000
NORMALIZED_INPUT:controls=40;axis_01_30=axis:32767;axis_01_31=axis:10025;axis_01_32=axis:2978;usage_ff00_20_3=unknown:135;...
# devices={1: '2109:2813', 2: '044f:b679', 3: '044f:b10a', 4: '044f:b687'}
# descriptors=[(2, 0, 46), (3, 0, 134), (4, 0, 118)]
# report_keys=[(2, 0), (3, 0)]
--- M4 FINAL COMPONENT COVERAGE CAPTURE END ---
```

Result:

- TFRP pedals attached, descriptor parsed, raw reports captured, and normalized axes changed: **pass**
- T.16000 stick attached, descriptor parsed, raw reports captured, and normalized controls returned: **pass**
- TWCS throttle attached and descriptor parsed in full-pack run: **pass**
- TWCS raw/normalized reports in this full-pack order: **not captured**
- TWCS full-pack interrupt capture failure: `STAGE=1`, `ERR=262` (`ESP_ERR_NOT_SUPPORTED`) while claiming interface endpoint `0x81`

## TWCS-Only Run: Normalized Input

Connection topology:

```text
ESP32-S3 USB host path -> HooToo SHUTTLE HT-UC001 -> TWCS throttle
```

Key target transcript:

```text
--- M4 FINAL TWCS NORMALIZED CAPTURE START ---
Name: usb2ble
Version: 0.4.0-m4
Status: M4 Code-path (Normalized Input Witness)
[ATTACH] Device: ID=1, VID=2109, PID=2813
[ATTACH] Device: ID=2, VID=044f, PID=b687
[INTERFACE] Device: ID=2, IFACE=0, CLASS=03, SUBCLASS=00, PROTOCOL=00
[DESCRIPTOR] Device: ID=2, IFACE=0, BYTES=118
[REPORT] Device: ID=2, IFACE=0, REPORT_ID=0, BYTES=64 # 044f:b687
USB_STATUS:devices=2;interfaces=1;
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b687
HID_SUMMARY:axes=8;buttons=14;hats=1;report_ids=1,0;axis_usages=01:30,01:31,01:35,01:33,01:34,01:36,01:37,01:32;button_usages=1,2,3,4,5,6,7,8,9,10,11,12,13,14;hat_usages=01:39;
USB_REPORT:01000200020002ff03ff03000299031e75080000e33fbf3f4018f7420b2dc6294d43a227cacae8d629298b8a2020a0a02d2da0a00abc02cdcab026ef00008002
NORMALIZED_INPUT:controls=67;axis_01_30=axis:31;axis_01_31=axis:31;axis_01_35=axis:31;axis_01_33=axis:32767;axis_01_34=axis:32767;axis_01_36=axis:31;axis_01_37=axis:26232;axis_01_32=axis:-2786;hat_01_39=hat:8;button_1=button:0;button_2=button:0;button_3=button:0;button_4=button:0;button_5=button:0;button_6=button:0;button_7=button:0;button_8=button:0;button_9=button:0;button_10=button:0;button_11=button:0;button_12=button:0;button_13=button:0;button_14=button:0;usage_ff00_21_23=unknown:226;usage_ff00_21_24=unknown:63;...
# devices={1: '2109:2813', 2: '044f:b687'}
# descriptors=[(2, 0, 118)]
# report_keys=[(2, 0)]
--- M4 FINAL TWCS NORMALIZED CAPTURE END ---
```

Result:

- TWCS attached through the HooToo hub: **pass**
- TWCS report descriptor parsed: **pass**
- TWCS raw 64-byte input reports captured: **pass**
- TWCS normalized frame returned with 8 axes, 1 hat, 14 buttons, and unique vendor-usage IDs: **pass**

## Detach Cleanup Attempt

A live monitor captured pre-detach TWCS state, but no physical detach event was
observed before the monitor timed out:

```text
--- M4 DETACH CLEANUP LIVE MONITOR START ---
Name: usb2ble
Version: 0.4.0-m4
Status: M4 Code-path (Normalized Input Witness)
[ATTACH] Device: ID=1, VID=2109, PID=2813
[ATTACH] Device: ID=2, VID=044f, PID=b687
USB_STATUS:devices=2;interfaces=1;
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b687
HID_SUMMARY:axes=8;buttons=14;hats=1;report_ids=1,0;axis_usages=01:30,01:31,01:35,01:33,01:34,01:36,01:37,01:32;button_usages=1,2,3,4,5,6,7,8,9,10,11,12,13,14;hat_usages=01:39;
USB_REPORT:01000200020002ff03ff03000299039076080000e83fc03f3f18ea421a2d062a44430c28cacae8d629298b8a2020a0a02d2da0a00abc02cd15ca26c300008002
NORMALIZED_INPUT:controls=67;axis_01_30=axis:31;axis_01_31=axis:31;axis_01_35=axis:31;axis_01_33=axis:32767;axis_01_34=axis:32767;axis_01_36=axis:31;axis_01_37=axis:26232;axis_01_32=axis:-2416;hat_01_39=hat:8;button_1=button:0;...
# detached_id=None
--- M4 DETACH CLEANUP LIVE MONITOR END ---
```

Result:

- Pre-detach state exists for TWCS: **pass**
- Actual detach event and post-detach cleanup state: **not captured**

## Results

- Pedals normalized through powered hub: **pass**
- Stick normalized through powered hub: **pass**
- TWCS normalized through powered hub when isolated: **pass**
- Full-pack attach and descriptor coverage for all three devices: **pass**
- Full-pack simultaneous raw/normalized streaming from all three devices: **not captured**
- Button press transition witness: **not captured**
- Detach cleanup witness: **not captured**
