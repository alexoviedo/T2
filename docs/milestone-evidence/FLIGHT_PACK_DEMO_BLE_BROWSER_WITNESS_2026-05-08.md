# Flight Pack Demo BLE Browser Witness - 2026-05-08

Status: **accepted target + Mac host evidence for one live `flight_pack_demo`
USB input published over BLE and observed by the browser Gamepad API.**

## Scope

This witness proves a real end-to-end demo path for the current Generic Gamepad
persona:

```text
T.16000M stick USB input -> ESP32-S3 USB host -> flight_pack_demo mapping
-> Generic Gamepad report -> BLE HID publish -> macOS HID -> browser Gamepad API
```

This is not Xbox BLE emulation. It is the Generic Gamepad demo path that keeps
the future Xbox persona work isolated behind the persona/report boundary.

## Hardware Context

- ESP32-S3 serial port: `/dev/cu.usbmodem5B5E0200881`
- Powered hub: `2109:2813`
- TWCS throttle: `044f:b687`, device `2`, interface `0`
- T.16000M stick: `044f:b10a`, device `3`, interface `0`
- BLE HID host: this Mac
- BLE HID product: `USB2BLE Gamepad`

After the Mac reboot, the local browser witness server was restarted:

```text
Serving USB2BLE Gamepad Witness at http://127.0.0.1:8765/
Capture file: target/gamepad-witness/gamepad_witness_20260508T200915Z.jsonl
```

The capture file is under `target/` and is intentionally not checked in. The
material witness lines are copied below.

## Target Recovery And Connection

After reboot recovery, the target saw the hub plus both demo devices:

```text
>> GET_STATUS
STATUS:ble=Idle;profile=none;bonds=false;
>> GET_USB_STATUS
USB_STATUS:devices=3;interfaces=2;
>> LIST_USB_DEVICES
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b687|id=3,vid=044f,pid=b10a
```

BLE was restarted and the Mac host reconnected:

```text
>> START_BLE_GENERIC_GAMEPAD
BLE_ACTION:action=start_generic_gamepad;state=Advertising;
>> GET_STATUS
STATUS:ble=Connected;profile=none;bonds=false;
```

macOS also exposed the BLE HID device through IOHID:

```text
0x303a   0x4001    0xffffffffd35800ad 1         5     0x100014c2a Bluetooth Low Energy AppleUserHIDEventService      USB2BLE Gamepad                    AppleUserHIDEventDriver (null)
0x303a   0x4001    0xd35800ad          1         5     0x100014c25 Bluetooth Low Energy IOHIDResource                 USB2BLE Gamepad                    (null)                    (null)
```

## Browser Discovery

With the browser page armed, publishing input reports caused the Gamepad API to
surface the BLE HID gamepad:

```json
{"at":"2026-05-08T20:12:00.305Z","axes":[-1,0,0,0,0,0,0,0,0,0],"buttons":[{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0}],"connected":true,"id":"USB2BLE Gamepad (Vendor: 303a Product: 4001)","index":0,"mapping":"","type":"connected"}
```

## Physical Stick Movement

The operator held the T.16000M stick fully right. The target reported the raw
USB report, normalized stick values, selected `flight_pack_demo` mapping, and
BLE publish.

```text
>> GET_LAST_USB_REPORT 3:0
USB_REPORT:00000fff3fd11f7400070000000b01ffffffffffffffffffffff00000000f17f1080f041c10f534be555f15556506917ed1b3d5800006a765883de46ffffff00
>> GET_NORMALIZED_INPUT 3:0
NORMALIZED_INPUT:controls=21;button_1=button:0;button_2=button:0;button_3=button:0;button_4=button:0;button_5=button:0;button_6=button:0;button_7=button:0;button_8=button:0;button_9=button:0;button_10=button:0;button_11=button:0;button_12=button:0;button_13=button:0;button_14=button:0;button_15=button:0;button_16=button:0;hat_01_39=hat:15;axis_01_30=axis:32767;axis_01_31=axis:-307;axis_01_35=axis:-2956;axis_01_36=axis:-32768;
>> GET_GENERIC_GAMEPAD_MAPPING
GENERIC_GAMEPAD_MAPPING:profile=flight_pack_demo;persona=generic_gamepad;entries=88;mappings=<omitted>;
src=3:0:044f:b10a:axis_01_30,target=x,value=axis:32767,reason=profile_rule
src=3:0:044f:b10a:axis_01_31,target=y,value=axis:-275,reason=profile_rule
src=2:0:044f:b687:axis_01_32,target=z,value=axis:-10952,reason=profile_rule
src=2:0:044f:b687:axis_01_36,target=rx,value=axis:31,reason=profile_rule
src=3:0:044f:b10a:axis_01_36,target=ry,value=axis:-32768,reason=profile_rule
src=3:0:044f:b10a:axis_01_35,target=rz,value=axis:-2956,reason=profile_rule
>> GET_GENERIC_GAMEPAD_REPORT
ENCODED_REPORT:persona=generic_gamepad;report_id=1;bytes=000008ff7fe10038d51f00008074f4;
>> PUBLISH_GENERIC_GAMEPAD_REPORT
BLE_ACTION:action=publish_generic_gamepad;state=Connected;persona=generic_gamepad;report_id=1;bytes=000008ff7fb90138d51f00008074f4;
```

The full mapping response contains all `88` entries on one long serial line.
Only the selected profile-rule entries are copied above.

The browser Gamepad API then captured axis `0` at `1`, matching the fully-right
Generic Gamepad X axis state:

```json
{"at":"2026-05-08T20:13:07.724Z","axes":[1,0.013,-0.334,0.001,-1,-0.09,0,0,0,1.286],"buttons":[{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0}],"connected":true,"id":"USB2BLE Gamepad (Vendor: 303a Product: 4001)","index":0,"mapping":"","type":"change"}
```

## Proven

- The flashed ESP32-S3 enumerated the HooToo hub, TWCS, and T.16000M stick.
- The target selected `profile=flight_pack_demo` for the known TWCS +
  T.16000M topology.
- Real T.16000M stick movement changed normalized USB input
  `axis_01_30=axis:32767`.
- The selected profile mapped that source to Generic Gamepad `x`.
- `PUBLISH_GENERIC_GAMEPAD_REPORT` sent the live USB-derived report over BLE.
- macOS exposed the target as `USB2BLE Gamepad`.
- The browser Gamepad API captured the live movement as axis `0 = 1`.

## Not Proven

- Xbox Wireless-style BLE output.
- Game/application compatibility beyond the browser Gamepad API witness.
- Durable BLE bond persistence; target status still reports `bonds=false`.
- Final calibration/deadzones for all Flight Pack axes.
- Clean host-visible TWCS throttle and TFRP pedal semantic witnesses in this
  specific post-reboot run.
