# ASAP Demo Rehearsal Witness - 2026-05-08

Status: **accepted target + Mac host evidence for the operator-friendly
Generic Gamepad demo rehearsal helper.**

## Scope

This witness proves the current ASAP demo can be rehearsed through one helper
command and can produce serial plus browser Gamepad API evidence for a real
T.16000M stick movement:

```text
T.16000M stick -> ESP32-S3 USB host -> flight_pack_demo mapping
-> Generic Gamepad BLE HID -> Mac -> browser Gamepad API
```

This does not claim Xbox BLE emulation, final calibration, universal HOTAS
support, or broad game compatibility. Synthetic self-test reports in the wake
sequence are BLE/browser transport evidence only.

## Command

```bash
python3 tools/asap_demo_rehearsal.py --port /dev/cu.usbmodem5B5E0200881
```

The third rehearsal run completed successfully:

```text
target/asap-demo-rehearsal/demo_rehearsal_20260508T210151Z/
```

Generated run artifacts are under `target/` and are not checked in:

```text
target/asap-demo-rehearsal/demo_rehearsal_20260508T210151Z/serial_transcript.txt
target/asap-demo-rehearsal/demo_rehearsal_20260508T210151Z/summary.json
target/asap-demo-rehearsal/demo_rehearsal_20260508T210151Z/gamepad-witness/gamepad_witness_20260508T210151Z.jsonl
```

The material witness lines are copied below.

## Preflight

The ESP32-S3 was running the hosted release image flashed earlier in the demo
session. The powered hub, TWCS throttle, and T.16000M stick were present, and
BLE was already connected to the Mac:

```text
>> GET_STATUS
STATUS:ble=Connected;profile=none;bonds=false;
>> GET_USB_STATUS
USB_STATUS:devices=3;interfaces=2;
>> LIST_USB_DEVICES
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b687|id=3,vid=044f,pid=b10a
>> START_BLE_GENERIC_GAMEPAD
BLE_ACTION:action=start_generic_gamepad;state=Connected;
>> GET_STATUS
STATUS:ble=Connected;profile=none;bonds=false;
```

## Browser Wake

The helper sent an explicit BLE wake sequence before physical input capture.
The self-test report is synthetic transport evidence, not real USB input:

```text
>> SEND_BLE_SELF_TEST_REPORT
BLE_ACTION:action=send_self_test;state=Connected;persona=generic_gamepad;report_id=1;bytes=010000ff7f00000000000000000000;
>> PUBLISH_GENERIC_GAMEPAD_REPORT
BLE_ACTION:action=publish_generic_gamepad;state=Connected;persona=generic_gamepad;report_id=1;bytes=000008b9fc29fa00801f00008077f7;
>> SEND_BLE_SELF_TEST_REPORT
BLE_ACTION:action=send_self_test;state=Connected;persona=generic_gamepad;report_id=1;bytes=000008008000000000000000000000;
>> PUBLISH_GENERIC_GAMEPAD_REPORT
BLE_ACTION:action=publish_generic_gamepad;state=Connected;persona=generic_gamepad;report_id=1;bytes=000008b9fc29fa00801f00008077f7;
>> GET_STATUS
STATUS:ble=Connected;profile=none;bonds=false;
```

## Physical Stick Movement

The operator held the T.16000M stick fully right. The target captured a live
USB report, decoded normalized input, selected the `flight_pack_demo` profile,
and published the USB-derived Generic Gamepad report over BLE.

```text
>> GET_LAST_USB_REPORT 3:0
USB_REPORT:00000f983f58227400070000000b01ffffffffffffffffffffff00000000f17f1080f041c10f534be555f15556506917ed1b3d5800006a765883de46ffffff00
>> GET_NORMALIZED_INPUT 3:0
NORMALIZED_INPUT:controls=21;button_1=button:0;button_2=button:0;button_3=button:0;button_4=button:0;button_5=button:0;button_6=button:0;button_7=button:0;button_8=button:0;button_9=button:0;button_10=button:0;button_11=button:0;button_12=button:0;button_13=button:0;button_14=button:0;button_15=button:0;button_16=button:0;hat_01_39=hat:15;axis_01_30=axis:32346;axis_01_31=axis:2409;axis_01_35=axis:-2956;axis_01_36=axis:-32768;
>> GET_GENERIC_GAMEPAD_MAPPING
GENERIC_GAMEPAD_MAPPING:profile=flight_pack_demo;persona=generic_gamepad;entries=88;mappings=<long mapping line>;
src=3:0:044f:b10a:axis_01_30,target=x,value=axis:32214,reason=profile_rule
>> GET_GENERIC_GAMEPAD_REPORT
ENCODED_REPORT:persona=generic_gamepad;report_id=1;bytes=000008ff7fb90800801f00008074f4;
>> PUBLISH_GENERIC_GAMEPAD_REPORT
BLE_ACTION:action=publish_generic_gamepad;state=Connected;persona=generic_gamepad;report_id=1;bytes=000008227fd90800801f00008074f4;
```

The full mapping response is a single long serial line. Only the selected
stick-X profile-rule entry is copied above.

## Browser Witness

The browser witness saw the Mac Gamepad API expose the BLE HID device:

```json
{"at":"2026-05-08T21:03:45.854Z","axes":[0.978,0.123,-1,0.001,-1,-0.098,0,0,0,1.286],"connected":true,"id":"USB2BLE Gamepad (Vendor: 303a Product: 4001)","type":"connected"}
```

After the live USB-derived publish, the browser captured stick-right movement
on Gamepad axis `0`:

```json
{"at":"2026-05-08T21:05:49.775Z","axes":[0.993,0.069,-1,0.001,-1,-0.09,0,0,0,1.286],"connected":true,"id":"USB2BLE Gamepad (Vendor: 303a Product: 4001)","type":"change"}
```

## Helper Checks

The helper's summary reported every check passing:

```text
PASS usb_has_hub
PASS usb_has_twcs
PASS usb_has_t16000m
PASS usb_has_two_hid_interfaces
PASS ble_connected
PASS stick_x_fully_right
PASS flight_pack_profile
PASS stick_x_maps_to_gamepad_x
PASS publish_connected
PASS browser_saw_usb2ble_gamepad
PASS browser_saw_stick_right
```

## Proven

- The demo can be rehearsed with one operator-friendly helper command.
- The helper records a timestamped serial transcript and summary under
  `target/asap-demo-rehearsal/`.
- The helper can start or reuse the browser witness and find the generated
  Gamepad API capture.
- The target enumerated the HooToo hub, TWCS throttle, and T.16000M stick.
- The target selected `flight_pack_demo` for the known T.16000M + TWCS
  topology.
- Real T.16000M stick movement changed normalized input
  `axis_01_30=axis:32346`.
- The selected profile mapped that source to Generic Gamepad `x`.
- The live USB-derived Generic Gamepad report was published over BLE while
  connected.
- The browser Gamepad API saw `USB2BLE Gamepad` and captured the stick-right
  movement.

## Not Proven

- Xbox Wireless-style BLE output.
- Game/application compatibility beyond the browser Gamepad API witness.
- Durable BLE bond persistence; target status still reports `bonds=false`.
- Final calibration/deadzones for all Flight Pack axes.
- Final TWCS and TFRP semantic mapping.
