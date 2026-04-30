# Browser Gamepad API Witness - 2026-04-30

## Scope

This is a real browser witness for the ESP32-S3 BLE HID Generic Gamepad demo.

It proves that a browser page using `navigator.getGamepads()` can see the
ESP32-S3 as `USB2BLE Gamepad`, receive synthetic self-test report changes, and
receive a live USB-derived publish after `PUBLISH_GENERIC_GAMEPAD_REPORT`.

Synthetic self-test report captures are separated from the live USB-derived
publish capture below.

## Witness Tool

Repo-local witness page and capture server:

```text
tools/gamepad_witness/index.html
tools/gamepad_witness/server.py
```

Server command:

```bash
python3 tools/gamepad_witness/server.py --host 127.0.0.1 --port 8765
```

Server output:

```text
Serving USB2BLE Gamepad Witness at http://127.0.0.1:8765/
Capture file: target/gamepad-witness/gamepad_witness_20260430T185534Z.jsonl
```

The capture file is under `target/` and is intentionally not checked in. The
material witness lines are copied below.

## Target Transcript

Monitor command:

```bash
./scripts/monitor.sh --port /dev/cu.usbmodem5B5E0200881
```

Boot excerpt:

```text
--- USB2BLE FIRMWARE BOOT ---
Name: usb2ble
Version: 0.4.2-ble-hid-demo
Contract Version: 1
Status: BLE HID Demo Path (Generic Gamepad Persona)
Ready for commands.
```

BLE start:

```text
GET_STATUS
START_BLE_GENERIC_GAMEPAD
```

Target response:

```text
STATUS:ble=Idle;profile=none;bonds=false;
I (...) BLE_INIT: Bluetooth MAC: 90:70:69:07:0d:7e
BLE_ACTION:action=start_generic_gamepad;state=Advertising;
```

Connected status before browser witness commands:

```text
STATUS:ble=Connected;profile=none;bonds=false;
```

## Browser Discovery

Browser capture server received this exact Gamepad API connection snapshot:

```json
{"at":"2026-04-30T18:58:50.638Z","axes":[-0.026,-0.03,-1,-0.003,0.001,-0.075,0,0,0,1.286],"buttons":[{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0}],"connected":true,"id":"USB2BLE Gamepad (Vendor: 303a Product: 4001)","index":0,"mapping":"","type":"connected"}
```

This proves that the browser Gamepad API sees the BLE HID device as
`USB2BLE Gamepad (Vendor: 303a Product: 4001)`.

## Synthetic Self-Test Browser Input

Serial commands:

```text
SEND_BLE_SELF_TEST_REPORT
SEND_BLE_SELF_TEST_REPORT
```

Serial responses:

```text
BLE_ACTION:action=send_self_test;state=Connected;persona=generic_gamepad;report_id=1;bytes=010000ff7f00000000000000000000;
BLE_ACTION:action=send_self_test;state=Connected;persona=generic_gamepad;report_id=1;bytes=000008008000000000000000000000;
```

Browser Gamepad API exact captures:

```json
{"at":"2026-04-30T18:58:54.537Z","axes":[1,0,0,0,0,0,0,0,0,-1],"buttons":[{"pressed":true,"touched":true,"value":1},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0}],"connected":true,"id":"USB2BLE Gamepad (Vendor: 303a Product: 4001)","index":0,"mapping":"","type":"change"}
{"at":"2026-04-30T18:58:54.670Z","axes":[-1,0,0,0,0,0,0,0,0,1.286],"buttons":[{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0}],"connected":true,"id":"USB2BLE Gamepad (Vendor: 303a Product: 4001)","index":0,"mapping":"","type":"change"}
```

## Live USB-Derived Browser Input

Serial commands:

```text
PUBLISH_GENERIC_GAMEPAD_REPORT
GET_GENERIC_GAMEPAD_REPORT
```

Serial responses:

```text
BLE_ACTION:action=publish_generic_gamepad;state=Connected;persona=generic_gamepad;report_id=1;bytes=000008b1fc25fc00809fff1f0076f6;
ENCODED_REPORT:persona=generic_gamepad;report_id=1;bytes=000008b1fc25fc00809fff1f0076f6;
```

Browser Gamepad API exact capture after the live publish:

```json
{"at":"2026-04-30T18:59:09.003Z","axes":[-0.026,-0.03,-1,-0.003,0.001,-0.075,0,0,0,1.286],"buttons":[{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0},{"pressed":false,"touched":false,"value":0}],"connected":true,"id":"USB2BLE Gamepad (Vendor: 303a Product: 4001)","index":0,"mapping":"","type":"change"}
```

This proves that the browser Gamepad API can observe the live USB-derived BLE
publish. It does not prove final semantic mapping or calibration quality.

## Proven

- The browser Gamepad API sees the target as `USB2BLE Gamepad`.
- Synthetic BLE self-test reports produce browser-visible axis/button changes.
- `PUBLISH_GENERIC_GAMEPAD_REPORT` publishes a live USB-derived report with
  bytes matching `GET_GENERIC_GAMEPAD_REPORT`.
- The browser witness receives a change snapshot after the live publish.

## Not Proven

- Final game/application compatibility beyond the browser Gamepad API.
- Durable BLE bond persistence; target status still reports `bonds=false`.
- Final T.16000M/TWCS/TFRP mapping and calibration.
- Xbox Wireless-style BLE output.
