# Xbox BLE Witness - 2026-05-09

## Summary

Real ESP32-S3 hardware witness captured for the Xbox Wireless Controller BLE
compatibility persona.

This evidence proves:

- the Generic BLE Gamepad start path still reaches a connected persona state;
- the Xbox BLE persona starts and connects on macOS;
- macOS Bluetooth sees `Xbox Wireless Controller` with VID `0x045e` and PID
  `0x0b13`;
- Xbox synthetic self-test reports publish over BLE as 16-byte report ID 1
  payloads;
- the latest USB-derived Xbox report publishes over BLE;
- the browser Gamepad API sees a connected standard gamepad with Xbox VID/PID
  and captures input changes.

This does not prove broad game compatibility across apps/hosts.

## Environment

- Date: 2026-05-09 UTC
- Firmware source revision at run start:
  `65a68df69d5ea33d97b83afe4a88ceb5eb2bfc18`
- Local build state: `65a68df-dirty`
  - dirty changes included this evidence pass: `AGENTS.md`, neutral boot banner,
    and Xbox rehearsal helper detection/prompt fixes.
- Boot app version string: `86894a7-dirty`
- Board serial port: `/dev/cu.usbmodem5B5E0200881`
- Board MAC from flash output: `90:70:69:07:0d:7c`
- Host OS: macOS 12.7.5, build `21H1222`
- Hardware topology observed at boot:
  - HooToo hub: VID `2109`, PID `2813`
  - TWCS throttle: VID `044f`, PID `b687`
  - T.16000M stick: VID `044f`, PID `b10a`

## Saved Artifacts

- Boot capture:
  `target/xbox-hardware-witness/20260509T024451Z/boot_serial.txt`
- Generic smoke transcript:
  `target/xbox-hardware-witness/20260509T024451Z/generic_smoke.txt`
- macOS Bluetooth CLI capture:
  `target/xbox-hardware-witness/20260509T024451Z/macos_bluetooth_xbox.txt`
- Initial Xbox transcript from Idle/Advertising:
  `target/xbox-hardware-witness/xbox_demo_20260509T025119Z/serial_transcript.txt`
- Corrected Xbox helper summary:
  `target/xbox-hardware-witness/xbox_demo_20260509T025303Z/summary.json`
- Browser Gamepad API JSONL:
  `target/xbox-hardware-witness/xbox_demo_20260509T025303Z/gamepad-witness/gamepad_witness_20260509T025304Z.jsonl`

## Boot Evidence

```text
--- USB2BLE FIRMWARE BOOT ---
Name: usb2ble
Version: 0.4.2-ble-hid-demo
Contract Version: 1
Status: BLE HID Demo Path (Selectable Generic/Xbox Personas)
Ready for commands.
```

## Generic Regression Smoke

```text
>> GET_STATUS
STATUS:ble=Idle;profile=none;persona=none;bonds=false;
>> START_BLE_GENERIC_GAMEPAD
BLE_ACTION:action=start_generic_gamepad;state=Advertising;
>> GET_STATUS
STATUS:ble=Connected;profile=none;persona=generic_gamepad;bonds=false;
```

## macOS Bluetooth Evidence

```text
Connected:
    Xbox Wireless Controller:
        Address: 90:70:69:07:0D:7E
        Vendor ID: 0x045E
        Product ID: 0x0B13
        Battery Level: 100%
        Services: 0x400000 < BLE >
```

## Xbox Serial Evidence

Initial Xbox run from idle:

```text
>> GET_STATUS
STATUS:ble=Idle;profile=none;persona=none;bonds=false;
>> START_BLE_XBOX_CONTROLLER
BLE_ACTION:action=start_xbox_controller;state=Advertising;
>> GET_STATUS
STATUS:ble=Connected;profile=none;persona=xbox_wireless_controller;bonds=false;
```

Self-test reports:

```text
>> SEND_XBOX_SELF_TEST_REPORT
BLE_ACTION:action=send_xbox_self_test;state=Connected;persona=xbox_wireless_controller;report_id=1;bytes=feffff7fff7fff7f0000000000010000;
>> SEND_XBOX_SELF_TEST_REPORT
BLE_ACTION:action=send_xbox_self_test;state=Connected;persona=xbox_wireless_controller;report_id=1;bytes=0000ff7fff7fff7f0000000000000000;
```

Live USB-derived Xbox report:

```text
>> GET_XBOX_GAMEPAD_REPORT
ENCODED_REPORT:persona=xbox_wireless_controller;report_id=1;bytes=707c947a00007778ff01ff0300000000;
>> PUBLISH_XBOX_GAMEPAD_REPORT
BLE_ACTION:action=publish_xbox_gamepad;state=Connected;persona=xbox_wireless_controller;report_id=1;bytes=707c947a00007778ff01ff0300000000;
```

## Browser Gamepad API Evidence

The browser Gamepad API labeled the device as `USB2BLE Gamepad`, likely due host
or browser naming/caching behavior, but it exposed the Xbox BLE identity VID/PID
and standard mapping:

```json
{"connected":true,"id":"USB2BLE Gamepad (STANDARD GAMEPAD Vendor: 045e Product: 0b13)","mapping":"standard","type":"connected"}
```

Input changes were captured:

```json
{"axes":[0.004,0.93,-0.004,0],"connected":true,"id":"USB2BLE Gamepad (STANDARD GAMEPAD Vendor: 045e Product: 0b13)","mapping":"standard","type":"change"}
```

## Pass / Fail Table

| Check | Result |
| --- | --- |
| Generic start smoke remains connected | PASS |
| Xbox start returns BLE action | PASS |
| macOS sees `Xbox Wireless Controller` | PASS |
| macOS reports VID `0x045e`, PID `0x0b13` | PASS |
| `GET_STATUS` after pairing includes `ble=Connected` and `persona=xbox_wireless_controller` | PASS |
| Two Xbox self-test reports publish as 16-byte report ID 1 payloads | PASS |
| USB-derived Xbox report encodes as 16 bytes | PASS |
| USB-derived Xbox report publishes while connected | PASS |
| Browser Gamepad API sees Xbox VID/PID and input changes | PASS |
| Browser/device display name consistently says `Xbox Wireless Controller` | PARTIAL - macOS Bluetooth does; browser Gamepad API reported `USB2BLE Gamepad` with Xbox VID/PID |
| Broad game/app compatibility | NOT CLAIMED |

## Conclusion

Xbox Wireless Controller model 1914 / Series X|S BLE compatibility has real
ESP32-S3 + macOS pairing, BLE publish, and browser Gamepad API input witness
evidence.

Remaining limitations:

- browser Gamepad API display name may be stale/cached or synthesized despite
  the Xbox VID/PID being present;
- broader app/game compatibility still needs separate evidence;
- this evidence covers macOS 12.7.5 only.
