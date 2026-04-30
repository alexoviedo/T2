# BLE HID Mac Pairing And Input Witness - 2026-04-30

## Scope

This is a real ESP32-S3 target plus Mac host witness for the Generic Gamepad BLE
HID demo path.

It proves that a Mac host can discover/connect to the ESP32-S3 BLE HID device,
that macOS registers it as a BLE gamepad, that a synthetic self-test report is
visible through the host HID stack, and that a live USB-derived Generic Gamepad
report can be published over BLE.

The synthetic self-test lines below are not USB hardware behavior. The live
USB-derived report is explicitly separated in its own section.

## Hardware And Host

- ESP32-S3 serial port: `/dev/cu.usbmodem5B5E0200881`
- Target BLE MAC reported by firmware: `90:70:69:07:0d:7e`
- Mac Bluetooth controller: `78:4F:43:6B:EB:C5`
- Powered hub: `VID=2109, PID=2813`
- Thrustmaster HID devices observed through the hub:
  - `VID=044f, PID=b687`
  - `VID=044f, PID=b10a`

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
App/part. size:    2,035,664/16,384,000 bytes, 12.42%
Flash complete.
```

## Target Advertising And Connection

Boot excerpt:

```text
--- USB2BLE FIRMWARE BOOT ---
Name: usb2ble
Version: 0.4.2-ble-hid-demo
Contract Version: 1
Status: BLE HID Demo Path (Generic Gamepad Persona)
Ready for commands.
```

Serial commands:

```text
GET_STATUS
START_BLE_GENERIC_GAMEPAD
```

Serial response:

```text
STATUS:ble=Idle;profile=none;bonds=false;
I (...) BLE_INIT: Bluetooth MAC: 90:70:69:07:0d:7e
BLE_ACTION:action=start_generic_gamepad;state=Advertising;
```

Raw CoreBluetooth scan saw a nearby HID service advertisement. CoreBluetooth
showed the old cached name `HOTAS_CFG`, but the target connection was confirmed
by the ESP32 serial state and later by macOS system metadata:

```text
central_state=poweredOn
MATCH id=AD0058D3-E3EC-BCCD-0D72-4B5F5FAABA57 rssi=-39 name=HOTAS_CFG services=1812
connecting id=AD0058D3-E3EC-BCCD-0D72-4B5F5FAABA57 rssi=-42 name=HOTAS_CFG services=1812
connected id=AD0058D3-E3EC-BCCD-0D72-4B5F5FAABA57 name=HOTAS_CFG
```

Serial status after the Mac connection:

```text
STATUS:ble=Connected;profile=none;bonds=false;
```

macOS `system_profiler SPBluetoothDataType` after connection:

```text
Connected:
    USB2BLE Gamepad:
        Address: 90:70:69:07:0D:7E
        Vendor ID: 0x303A
        Product ID: 0x4001
        Battery Level: 100%
        Minor Type: Gamepad
        Services: 0x400000 < BLE >
```

macOS `hidutil list` after connection:

```text
0x303a 0x4001 ... Bluetooth Low Energy ... HOTAS_CFG ...
```

The `HOTAS_CFG` product label appears to be a stale macOS/CoreBluetooth HID
cache entry for the same target. The Bluetooth system view reported the current
firmware name `USB2BLE Gamepad`.

## Synthetic Self-Test Input

Serial command:

```text
SEND_BLE_SELF_TEST_REPORT
SEND_BLE_SELF_TEST_REPORT
```

Serial responses:

```text
BLE_ACTION:action=send_self_test;state=Connected;persona=generic_gamepad;report_id=1;bytes=000008008000000000000000000000;
BLE_ACTION:action=send_self_test;state=Connected;persona=generic_gamepad;report_id=1;bytes=010000ff7f00000000000000000000;
```

Mac IOHID monitor output from the same run:

```text
HID_VALUE page=0x0001 usage=0x0030 value=-32768
HID_VALUE page=0x0001 usage=0x0039 value=8
HID_VALUE page=0x0009 usage=0x0001 value=0
HID_VALUE page=0x0001 usage=0x0030 value=32767
HID_VALUE page=0x0001 usage=0x0039 value=0
HID_VALUE page=0x0009 usage=0x0001 value=1
```

This proves that the explicit synthetic report reaches the macOS HID input
stack. It does not prove live USB input behavior.

## Live USB-Derived BLE Publish

Operator instruction:

```text
Hold the T.16000M stick fully to the right.
```

Operator response:

```text
holding
```

A synthetic self-test report was sent immediately before the live publish as a
host-side marker. The following report bytes are from the live
`PUBLISH_GENERIC_GAMEPAD_REPORT` command and matched `GET_GENERIC_GAMEPAD_REPORT`
afterward.

Serial commands:

```text
SEND_BLE_SELF_TEST_REPORT
PUBLISH_GENERIC_GAMEPAD_REPORT
GET_GENERIC_GAMEPAD_REPORT
```

Serial responses:

```text
BLE_ACTION:action=send_self_test;state=Connected;persona=generic_gamepad;report_id=1;bytes=000008008000000000000000000000;
BLE_ACTION:action=publish_generic_gamepad;state=Connected;persona=generic_gamepad;report_id=1;bytes=000008a9fc21fc00809fff1f0076f6;
ENCODED_REPORT:persona=generic_gamepad;report_id=1;bytes=000008a9fc21fc00809fff1f0076f6;
```

Mac IOHID monitor output after the live publish:

```text
HID_VALUE t=5.227 page=0x0001 usage=0x0035 value=0
HID_VALUE t=5.227 page=0x0001 usage=0x0034 value=0
HID_VALUE t=5.227 page=0x0001 usage=0x0033 value=0
HID_VALUE t=5.227 page=0x0001 usage=0x0032 value=0
HID_VALUE t=5.227 page=0x0001 usage=0x0031 value=0
HID_VALUE t=6.096 page=0x0001 usage=0x0035 value=-2442
HID_VALUE t=6.096 page=0x0001 usage=0x0034 value=31
HID_VALUE t=6.096 page=0x0001 usage=0x0033 value=-97
HID_VALUE t=6.096 page=0x0001 usage=0x0032 value=-32768
HID_VALUE t=6.096 page=0x0001 usage=0x0031 value=-991
HID_VALUE t=6.096 page=0x0001 usage=0x0030 value=-855
```

This proves that the current live USB-derived Generic Gamepad report can be
published over BLE and observed by the Mac host HID stack.

## Proven

- The ESP32-S3 firmware boots the BLE HID demo path.
- `START_BLE_GENERIC_GAMEPAD` starts BLE advertising.
- The Mac can discover and connect to the target BLE HID service.
- macOS reports `USB2BLE Gamepad` as a connected BLE gamepad with VID `0x303A`
  and PID `0x4001`.
- `SEND_BLE_SELF_TEST_REPORT` produces host-visible HID input.
- `PUBLISH_GENERIC_GAMEPAD_REPORT` publishes a live USB-derived Generic Gamepad
  report and macOS receives corresponding HID axis values.

## Not Proven

- Durable BLE bond persistence; the firmware status still reported
  `bonds=false`.
- Browser Gamepad API compatibility is covered separately in
  `docs/milestone-evidence/BROWSER_GAMEPAD_API_WITNESS_2026-04-30.md`; final
  game/application compatibility remains open.
- Final semantic mapping/calibration for the HOTAS, throttle, and pedals.
- Xbox Wireless-style BLE output.
