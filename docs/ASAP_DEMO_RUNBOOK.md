# ASAP Demo Runbook

Status: **operator-ready path for the current Generic Gamepad demo.**

This runbook favors the smallest honest end-to-end demo:

```text
T.16000M stick -> ESP32-S3 USB host -> flight_pack_demo mapping
-> Generic Gamepad BLE HID -> Mac -> browser Gamepad API
```

It does not claim broad Xbox game/app compatibility, universal HOTAS support,
final calibration, or final TWCS/TFRP semantics. For the Xbox compatibility
path, see `docs/XBOX_BLE_DEMO_RUNBOOK.md`.

## Hardware Setup

- ESP32-S3 connected to the Mac over USB serial.
- HooToo SHUTTLE HT-UC001 powered hub connected to the ESP32-S3 USB host port.
- T.16000M stick USB connected to the hub.
- TWCS throttle USB connected to the hub.
- Optional: TFRP pedals connected to TWCS by RJ12 for later mapping refinement.

Known-good serial port:

```bash
/dev/cu.usbmodem5B5E0200881
```

If that port is missing, discover current ports:

```bash
ls /dev/cu.* | rg 'usb(modem|serial)'
```

## Start The Browser Witness

The fastest path is the rehearsal helper:

```bash
python3 tools/asap_demo_rehearsal.py --port /dev/cu.usbmodem5B5E0200881
```

It starts the browser witness server, opens the page, walks the operator through
arming the browser, waits for `USB2BLE Gamepad` to connect over Bluetooth,
auto-detects the T.16000M source by VID/PID, captures the stick fully right,
publishes the BLE reports, and writes a timestamped transcript under
`target/asap-demo-rehearsal/`. If the browser page already shows the gamepad
connected and does not offer **Arm**, keep the tab focused and continue.

For the real continuous controller path, use live bridge mode:

```bash
python3 tools/asap_demo_rehearsal.py \
  --port /dev/cu.usbmodem5B5E0200881 \
  --live-bridge
```

With `--live-bridge`, the helper starts `START_BRIDGE`, asks the operator to
hold/move the control for a few seconds, polls `GET_BRIDGE_STATUS`, then runs
`STOP_BRIDGE`. Passing evidence requires the bridge to be enabled, BLE to be
connected, and the bridge `published` counter to increase. Browser Gamepad API
evidence remains useful, but it is not a substitute for a real game/app witness.

If source auto-detection ever chooses poorly during debugging, pin the source
explicitly:

```bash
python3 tools/asap_demo_rehearsal.py \
  --port /dev/cu.usbmodem5B5E0200881 \
  --source 3:0
```

The manual flow remains useful when debugging one layer at a time.

In one terminal:

```bash
python3 tools/gamepad_witness/server.py --port 8765
```

Open:

```bash
open http://127.0.0.1:8765/
```

In the browser page, click **Arm**. Keep this tab focused during the BLE wake
and movement steps.

## Bring Up BLE And USB

In another terminal:

```bash
python3 tools/serial_command.py \
  --port /dev/cu.usbmodem5B5E0200881 \
  GET_STATUS \
  GET_USB_STATUS \
  LIST_USB_DEVICES \
  START_BLE_GENERIC_GAMEPAD \
  GET_STATUS
```

Expected shape:

```text
STATUS:ble=Idle;profile=none;persona=none;bonds=false;
USB_STATUS:devices=3;interfaces=2;
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b687|id=3,vid=044f,pid=b10a
BLE_ACTION:action=start_generic_gamepad;state=Advertising;
STATUS:ble=Connected;profile=none;persona=generic_gamepad;bonds=false;
```

If BLE is already connected, `START_BLE_GENERIC_GAMEPAD` may be unnecessary.
The important target state is `ble=Connected`.

## Wake The Browser Gamepad API

If the witness page says **No device** after clicking **Arm**, keep the tab
focused and send:

```bash
python3 tools/serial_command.py \
  --port /dev/cu.usbmodem5B5E0200881 \
  SEND_BLE_SELF_TEST_REPORT \
  PUBLISH_GENERIC_GAMEPAD_REPORT \
  SEND_BLE_SELF_TEST_REPORT \
  PUBLISH_GENERIC_GAMEPAD_REPORT \
  GET_STATUS
```

Expected result in the witness server terminal:

```text
[capture] {"at":"...","connected":true,"id":"USB2BLE Gamepad (Vendor: 303a Product: 4001)",...}
```

This wake sequence includes synthetic self-test reports. Treat those as BLE
transport evidence only, not real USB movement.

## Capture The Physical Stick Demo

Ask the operator:

```text
Move only the T.16000M stick fully right.
Hold it fully right.
Do not touch the TWCS.
Do not press any buttons.
Keep holding until release is called.
```

While the operator holds the stick, run:

```bash
mkdir -p target/flight-pack-witness
python3 tools/serial_command.py \
  --port /dev/cu.usbmodem5B5E0200881 \
  "GET_LAST_USB_REPORT 3:0" \
  "GET_NORMALIZED_INPUT 3:0" \
  GET_GENERIC_GAMEPAD_MAPPING \
  GET_GENERIC_GAMEPAD_REPORT \
  PUBLISH_GENERIC_GAMEPAD_REPORT \
  | tee "target/flight-pack-witness/stick_right_hold_$(date -u +%Y%m%dT%H%M%SZ).txt"
```

Then tell the operator:

```text
Release the stick back to center.
```

Expected target evidence:

```text
axis_01_30=axis:32767
src=3:0:044f:b10a:axis_01_30,target=x,value=axis:32767,reason=profile_rule
BLE_ACTION:action=publish_generic_gamepad;state=Connected;persona=generic_gamepad;report_id=1;bytes=<hex>;
```

Expected browser witness evidence:

```json
{"axes":[1,...],"connected":true,"id":"USB2BLE Gamepad (Vendor: 303a Product: 4001)","type":"change"}
```

## Continuous Live Bridge Manual Flow

Manual publish commands are diagnostics. For real games/apps, start the bridge
after the Generic persona is connected:

```bash
python3 tools/serial_command.py \
  --port /dev/cu.usbmodem5B5E0200881 \
  START_BRIDGE \
  GET_BRIDGE_STATUS
```

Move a control for 5-10 seconds, then poll and stop:

```bash
python3 tools/serial_command.py \
  --port /dev/cu.usbmodem5B5E0200881 \
  GET_BRIDGE_STATUS \
  STOP_BRIDGE \
  GET_BRIDGE_STATUS
```

Expected bridge status shape:

```text
BRIDGE_STATUS:enabled=true;persona=generic_gamepad;rate_hz=50;last_publish_ms=<ms>;published=<n>;skipped_duplicate=<n>;skipped_rate=<n>;skipped_not_connected=<n>;skipped_not_ready=<n>;last_error=none;
```

The `published` count should increase while the control is moved or while the
heartbeat republishes stable state. If BLE disconnects, `skipped_not_connected`
may increase without disabling bridge mode.

See `docs/milestone-evidence/LIVE_BRIDGE_WITNESS_2026-05-10.md` for the first
checked-in Generic live bridge hardware witness.

## Fast Recovery

If only the hub is visible:

```text
USB_STATUS:devices=1;interfaces=0;
```

Press the ESP32-S3 reset button, wait 8 seconds, then rerun:

```bash
python3 tools/serial_command.py \
  --port /dev/cu.usbmodem5B5E0200881 \
  GET_STATUS \
  GET_USB_STATUS \
  LIST_USB_DEVICES
```

If macOS says the BLE device is connected but the browser page says **No
device**, keep the page armed/focused and rerun the BLE wake sequence.

If pairing or reconnect behaves strangely, forget the macOS Bluetooth device
and clear target bonds:

```bash
python3 tools/serial_command.py \
  --port /dev/cu.usbmodem5B5E0200881 \
  FORGET_BLE_BONDS
```

Then reset the ESP32-S3 and restart BLE.

## Demo Claim

After a successful run, the honest claim is:

```text
We have a real ESP32-S3 bridge demo that reads a USB HID flight stick through a
powered hub, maps the live input into a Generic Gamepad report, publishes it as
BLE HID, and shows the movement on the Mac through the browser Gamepad API.
```

The honest gaps are:

- Xbox Wireless Controller BLE output now has a macOS pairing/input witness, but
  broader host/game compatibility still needs separate evidence.
- TWCS/TFRP semantic mapping and calibration still need refinement.
- Browser Gamepad API evidence is not the same as broad game compatibility.
- BLE bond persistence is not complete; current target status reports
  `bonds=false`.
