# BLE HID Generic Gamepad Advertising Witness - 2026-04-30

## Scope

This is a real ESP32-S3 target witness for booting the BLE HID demo firmware and
starting the Generic Gamepad BLE persona through the serial control plane.

This is **not** a host pairing, connection, or input-publication witness.

## Hardware

- ESP32-S3 serial port: `/dev/cu.usbmodem5B5E0200881`
- BLE MAC reported by target: `90:70:69:07:0d:7e`
- USB hub/device traffic was present during the run:
  - hub: `VID=2109, PID=2813`
  - THRUSTMASTER device: `VID=044f, PID=b687`
  - THRUSTMASTER device: `VID=044f, PID=b10a`

## Build And Flash

Verification before flashing:

```bash
RUSTUP_TOOLCHAIN=esp ./scripts/verify_cloud_equivalent.sh
```

Result:

```text
Target build preflight passed for xtensa-esp32s3-espidf.
```

Flash command:

```bash
./scripts/flash.sh --port /dev/cu.usbmodem5B5E0200881
```

Flash result:

```text
Chip type:         esp32s3 (revision v0.2)
Flash size:        16MB
Features:          WiFi, BLE, Embedded Flash
MAC address:       90:70:69:07:0d:7c
App/part. size:    2,035,376/16,384,000 bytes, 12.42%
Flash complete.
```

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

Initial status command:

```text
GET_STATUS
```

Initial status response:

```text
STATUS:ble=Idle;profile=none;bonds=false;
```

BLE start command:

```text
START_BLE_GENERIC_GAMEPAD
```

BLE start excerpt:

```text
I (...) BLE_INIT: Feature Config, ADV:1, BLE_50:1, DTM:1, SCAN:1, CCA:0, SMP:1, CONNECT:1
I (...) BLE_INIT: Bluetooth MAC: 90:70:69:07:0d:7e
BLE_ACTION:action=start_generic_gamepad;state=Advertising;
```

The final run did not emit the earlier `BTM_BleWriteAdvData, Partial data write
into ADV` warning after the advertising payload was trimmed to prioritize the
device name and gamepad appearance.

Advertising status command:

```text
GET_STATUS
```

Advertising status response:

```text
STATUS:ble=Advertising;profile=none;bonds=false;
```

## Proven

- Firmware image with BLE HID demo code flashes and boots on the ESP32-S3.
- The serial command `START_BLE_GENERIC_GAMEPAD` initializes the BLE controller.
- The target reports the BLE link state as `Advertising`.
- The app still services USB host events while the BLE demo persona is active.

## Not Proven Yet

- A host sees `USB2BLE Gamepad` in Bluetooth settings.
- A host can pair/connect.
- `SEND_BLE_SELF_TEST_REPORT` produces visible host input.
- `PUBLISH_GENERIC_GAMEPAD_REPORT` sends a live USB-derived report over BLE.
