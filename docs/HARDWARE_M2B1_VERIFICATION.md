# M2B.1 Hardware Verification Playbook (ESP32-S3)

Status: **Required for milestone evidence. Not yet captured in this repository revision.**

## Target scope
Verify M2B.1 code-path behavior on real hardware only:
- USB attach detection
- USB detach detection
- VID/PID identity witness
- HID interface discovery bookkeeping visibility via existing control-plane status/list commands

Out of scope for this playbook:
- HID semantic parsing
- descriptor/report control-plane fulfillment (`GET_USB_DESCRIPTOR`, `GET_LAST_USB_REPORT`)
- normalization, mapping, BLE publishing

## Hardware
- Board model: **ESP32-S3-DevKitC-1** (or equivalent ESP32-S3 board with USB-host wiring known-good)
- HID device type: **one known-good USB HID input device** (keyboard, mouse, or gamepad)
- Power/connection path: board powered stably; HID device attached to ESP32-S3 USB host path (direct, no hub for this check)

## Commands

### Build
```bash
./scripts/build.sh
```

### Flash
```bash
espflash flash target/xtensa-esp32s3-espidf/debug/usb2ble-fw --monitor
```

### Monitor (alternative wrapper)
```bash
./scripts/monitor.sh
```

## Verification procedure
1. Boot board and open monitor.
2. Send `GET_USB_STATUS`.
3. Plug HID device into host path.
4. Send `GET_USB_STATUS`.
5. Send `LIST_USB_DEVICES`.
6. Unplug HID device.
7. Send `GET_USB_STATUS`.
8. Send `LIST_USB_DEVICES`.

## Transcript template (paste filled real output back into repo)

```text
Board: <exact board model>
Firmware commit: <git sha>
HID device: <vendor/product/model if known>
Connection path: <direct cable/adapter details>

--- Boot ---
<paste exact boot output>

--- Pre-plug ---
>> GET_USB_STATUS
<< <actual output>
>> LIST_USB_DEVICES
<< <actual output>

--- Post-plug ---
>> GET_USB_STATUS
<< <actual output>
>> LIST_USB_DEVICES
<< <actual output>

--- Post-unplug ---
>> GET_USB_STATUS
<< <actual output>
>> LIST_USB_DEVICES
<< <actual output>
```

## Acceptance notes
- Do not replace this template with expected output.
- Only real captured output qualifies as milestone evidence.
- M2B.1 must remain marked as pending hardware verification until transcript is checked in.
