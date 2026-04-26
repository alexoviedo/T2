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

### 1) Target build preflight (required before flash)
```bash
./scripts/check_target_build.sh
```

Equivalent direct command:
```bash
cargo +esp build -Z build-std=std,panic_abort --locked --package usb2ble-fw --target xtensa-esp32s3-espidf
```

If the `esp` toolchain is not installed locally, run `./scripts/check_target_build.sh` first and follow its warning output. In CI, the `esp` toolchain is installed by the Xtensa toolchain action.

### 2) Build wrapper (optional convenience)
```bash
./scripts/build.sh
```

### 3) Flash
```bash
espflash flash target/xtensa-esp32s3-espidf/debug/usb2ble-fw --monitor
```

### 4) Monitor (alternative wrapper)
```bash
./scripts/monitor.sh
```

## Verification procedure
1. Run target build preflight (`./scripts/check_target_build.sh`).
2. Boot board and open monitor.
3. Send `GET_USB_STATUS`.
4. Plug HID device into host path.
5. Send `GET_USB_STATUS`.
6. Send `LIST_USB_DEVICES`.
7. Unplug HID device.
8. Send `GET_USB_STATUS`.
9. Send `LIST_USB_DEVICES`.

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
