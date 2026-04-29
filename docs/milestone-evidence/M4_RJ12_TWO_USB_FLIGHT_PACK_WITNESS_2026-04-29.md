# M4 RJ12 Two-USB Flight Pack Witness

Status: **M4 hardware evidence for the practical Flight Pack topology.**

This transcript covers the THRUSTMASTER T.16000M FCS FLIGHT PACK connected in
the reduced-USB topology:

```text
TFRP pedals -> RJ12 -> TWCS throttle
ESP32-S3 USB host path -> HooToo SHUTTLE HT-UC001 -> TWCS throttle USB + T.16000M stick USB
```

It proves that the current firmware can capture and normalize live input from
the stick and the TWCS throttle while the pedals are connected through the TWCS
RJ12 port. It also repeats the current limitation of the three-separate-USB
topology: the third HID interrupt stream can fail with `ESP_ERR_NOT_SUPPORTED`.

It does not prove exact semantic axis labels for the RJ12 pedals, button-press
transitions, or detach cleanup.

## Hardware

- Date: 2026-04-29
- Firmware commit: `f92c958-dirty`
- Firmware version: `0.4.0-m4`
- Target chip: ESP32-S3 rev v0.2, 16 MB flash
- Board/carrier model: TODO exact board model; observed through WCH USB Single Serial adapter
- Serial port: `/dev/cu.usbmodem5B5E0200881`
- Powered hub: HooToo SHUTTLE HT-UC001, observed as `VID=2109`, `PID=2813`
- Flight Pack devices:
  - T.16000M FCS stick, observed as `VID=044f`, `PID=b10a`
  - TWCS throttle, observed as `VID=044f`, `PID=b687`
  - TFRP rudder pedals connected to the TWCS by RJ12 for the accepted topology

## Three-Separate-USB Topology Check

Connection topology:

```text
ESP32-S3 USB host path -> HooToo SHUTTLE HT-UC001 -> TWCS USB + TFRP USB + T.16000M stick USB
```

Key target transcript:

```text
--- THREE USB FULL PACK INPUT CAPTURE START ---
Name: usb2ble
Version: 0.4.0-m4
Status: M4 Code-path (Normalized Input Witness)
USB_STATUS:devices=4;interfaces=3;
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b687|id=3,vid=044f,pid=b679|id=4,vid=044f,pid=b10a
HID_SUMMARY:axes=8;buttons=14;hats=1;report_ids=1,0;axis_usages=01:30,01:31,01:35,01:33,01:34,01:36,01:37,01:32;button_usages=1,2,3,4,5,6,7,8,9,10,11,12,13,14;hat_usages=01:39;
HID_SUMMARY:axes=3;buttons=0;hats=0;report_ids=0;axis_usages=01:30,01:31,01:32;button_usages=;hat_usages=;
HID_SUMMARY:axes=4;buttons=16;hats=1;report_ids=0;axis_usages=01:30,01:31,01:35,01:36;button_usages=1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16;hat_usages=01:39;
[USB_REPORT_WARN] Device: ID=4, IFACE=0, STATUS=unavailable, STAGE=1, ERR=262, EP=81, MPS=64, INTERVAL=2
# devices={1: '2109:2813', 2: '044f:b687', 3: '044f:b679', 4: '044f:b10a'}
# descriptors=[(2, 0, 118), (3, 0, 46), (4, 0, 134)]
# report_keys=[(2, 0), (3, 0)]
--- THREE USB FULL PACK INPUT CAPTURE END ---
```

Result:

- All three Flight Pack USB devices attached and their descriptors parsed: **pass**
- TWCS and TFRP report streams were captured in this run: **pass**
- T.16000M stick failed as the third interrupt stream with `ERR=262`: **not captured**
- Three-separate-USB simultaneous Flight Pack streaming: **not proven**

## RJ12 Two-USB Topology Check

Connection topology:

```text
TFRP pedals -> RJ12 -> TWCS throttle
ESP32-S3 USB host path -> HooToo SHUTTLE HT-UC001 -> TWCS throttle USB + T.16000M stick USB
```

Key target transcript from the combined movement run:

```text
--- RJ12 TWO USB FLIGHT PACK CAPTURE START ---
Name: usb2ble
Version: 0.4.0-m4
Status: M4 Code-path (Normalized Input Witness)
USB_STATUS:devices=3;interfaces=2;
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b687|id=3,vid=044f,pid=b10a
HID_SUMMARY:axes=8;buttons=14;hats=1;report_ids=1,0;axis_usages=01:30,01:31,01:35,01:33,01:34,01:36,01:37,01:32;button_usages=1,2,3,4,5,6,7,8,9,10,11,12,13,14;hat_usages=01:39;
HID_SUMMARY:axes=4;buttons=16;hats=1;report_ids=0;axis_usages=01:30,01:31,01:35,01:36;button_usages=1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16;hat_usages=01:39;
NORMALIZED_INPUT:controls=67;axis_01_30=axis:-33;axis_01_31=axis:31;axis_01_35=axis:31;axis_01_33=axis:32767;axis_01_34=axis:32767;axis_01_36=axis:31;axis_01_37=axis:20723;axis_01_32=axis:-32768;hat_01_39=hat:8;button_1=button:0;...
NORMALIZED_INPUT:controls=67;axis_01_30=axis:31;axis_01_31=axis:31;axis_01_35=axis:-32768;axis_01_33=axis:32767;axis_01_34=axis:32767;axis_01_36=axis:31;axis_01_37=axis:27257;axis_01_32=axis:32767;hat_01_39=hat:8;button_1=button:0;...
NORMALIZED_INPUT:controls=21;button_1=button:0;button_2=button:0;button_3=button:0;button_4=button:0;button_5=button:0;button_6=button:0;button_7=button:0;button_8=button:0;button_9=button:0;button_10=button:0;button_11=button:0;button_12=button:0;button_13=button:0;button_14=button:0;button_15=button:0;button_16=button:0;hat_01_39=hat:15;axis_01_30=axis:-1471;axis_01_31=axis:-32768;axis_01_35=axis:-4498;axis_01_36=axis:-32768;
# devices={1: '2109:2813', 2: '044f:b687', 3: '044f:b10a'}
# descriptors=[(2, 0, 118), (3, 0, 134)]
# report_keys=[(2, 0), (3, 0)]
--- RJ12 TWO USB FLIGHT PACK CAPTURE END ---
```

Result:

- TWCS throttle attached through the hub and produced normalized frames: **pass**
- T.16000M stick attached through the hub and produced normalized frames: **pass**
- Two simultaneous HID interrupt streams ran without `USB_REPORT_WARN`: **pass**

## RJ12 Pedals-Only Movement Check

The operator was instructed to leave the stick and TWCS throttle still and move
only the TFRP pedals through the RJ12 connection. The stick normalized frame
stayed essentially fixed while TWCS axes changed, proving that pedal movement is
represented in the TWCS USB report.

Key target transcript:

```text
--- RJ12 PEDALS ONLY CAPTURE START ---
Instruction phase: user moves only TFRP pedals; stick and TWCS throttle stay still.
>> GET_USB_STATUS
>> GET_HID_SUMMARY 2:0
>> GET_HID_SUMMARY 3:0
>> GET_NORMALIZED_INPUT 2:0
>> GET_NORMALIZED_INPUT 3:0
USB_STATUS:devices=3;interfaces=2;
HID_SUMMARY:axes=8;buttons=14;hats=1;report_ids=1,0;axis_usages=01:30,01:31,01:35,01:33,01:34,01:36,01:37,01:32;button_usages=1,2,3,4,5,6,7,8,9,10,11,12,13,14;hat_usages=01:39;
HID_SUMMARY:axes=4;buttons=16;hats=1;report_ids=0;axis_usages=01:30,01:31,01:35,01:36;button_usages=1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16;hat_usages=01:39;
NORMALIZED_INPUT:controls=67;axis_01_30=axis:-97;axis_01_31=axis:31;axis_01_35=axis:31;axis_01_33=axis:32767;axis_01_34=axis:32767;axis_01_36=axis:-29694;axis_01_37=axis:32767;axis_01_32=axis:32767;hat_01_39=hat:8;button_1=button:0;...
NORMALIZED_INPUT:controls=21;button_1=button:0;button_2=button:0;button_3=button:0;button_4=button:0;button_5=button:0;button_6=button:0;button_7=button:0;button_8=button:0;button_9=button:0;button_10=button:0;button_11=button:0;button_12=button:0;button_13=button:0;button_14=button:0;button_15=button:0;button_16=button:0;hat_01_39=hat:15;axis_01_30=axis:-779;axis_01_31=axis:-1171;axis_01_35=axis:-3213;axis_01_36=axis:-32768;
NORMALIZED_INPUT:controls=67;axis_01_30=axis:-97;axis_01_31=axis:31;axis_01_35=axis:31;axis_01_33=axis:32767;axis_01_34=axis:32767;axis_01_36=axis:32767;axis_01_37=axis:32767;axis_01_32=axis:32767;hat_01_39=hat:8;button_1=button:0;...
NORMALIZED_INPUT:controls=67;axis_01_30=axis:-97;axis_01_31=axis:31;axis_01_35=axis:31;axis_01_33=axis:-6503;axis_01_34=axis:32767;axis_01_36=axis:5284;axis_01_37=axis:32767;axis_01_32=axis:32767;hat_01_39=hat:8;button_1=button:0;...
NORMALIZED_INPUT:controls=67;axis_01_30=axis:-97;axis_01_31=axis:31;axis_01_35=axis:31;axis_01_33=axis:32767;axis_01_34=axis:32767;axis_01_36=axis:736;axis_01_37=axis:32767;axis_01_32=axis:32767;hat_01_39=hat:8;button_1=button:0;...
NORMALIZED_INPUT:controls=21;button_1=button:0;button_2=button:0;button_3=button:0;button_4=button:0;button_5=button:0;button_6=button:0;button_7=button:0;button_8=button:0;button_9=button:0;button_10=button:0;button_11=button:0;button_12=button:0;button_13=button:0;button_14=button:0;button_15=button:0;button_16=button:0;hat_01_39=hat:15;axis_01_30=axis:-779;axis_01_31=axis:-1175;axis_01_35=axis:-3213;axis_01_36=axis:-32768;
--- RJ12 PEDALS ONLY CAPTURE END ---
# status_count=10
# normalized_count=19
# warn_count=0
```

Result:

- Pedal movement through RJ12 changed the TWCS normalized report: **pass**
- The clearest observed RJ12 pedal-related field was `axis_01_36`, which moved from `-29694` to `32767`, `5284`, and `736` during the pedals-only phase.
- `axis_01_33` also changed during the pedals-only phase and may correspond to a toe-brake axis, but exact semantic mapping remains **pending**.
- Stick values stayed essentially fixed during the pedals-only phase, so the TWCS changes are not explained by stick movement.

## Results

- Practical Flight Pack topology for current firmware: **use RJ12 pedals into TWCS, plus TWCS USB and stick USB through the HooToo hub**
- RJ12 two-USB simultaneous normalized capture for stick plus TWCS/pedals: **pass**
- Three-separate-USB simultaneous normalized capture for stick plus TWCS plus pedals: **not captured**
- Exact pedal axis labels: **not captured**
- Button press transition witness: **not captured**
- Detach cleanup witness: **not captured**
