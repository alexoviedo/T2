# M2B.1 Hardware Verification Playbook (ESP32-S3)

Status: **Required for milestone evidence. Not yet captured in this repository revision.**

Current checked-in partial evidence:
- Hub attach/detach identity and interface-class witness: `docs/milestone-evidence/M2B1_HUB_WITNESS_2026-04-28.md`
- HID interface discovery through the powered hub: `docs/milestone-evidence/M2B1_HUB_WITNESS_2026-04-28.md` (USB keyboard, THRUSTMASTER T.16000 FCS HOTAS, and THRUSTMASTER T.16000M FCS FLIGHT PACK)
- Direct-attach witness: blocked with current cabling/port geometry
- AFTERGLOW PL-3702 note: this controller reports vendor-specific `CLASS=ff` interfaces, not HID `CLASS=03`

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
- HID device type: **one known-good USB HID input device** (keyboard, mouse, or gamepad that reports USB interface class `03`)
- Powered hub: **exact model required** for hub-attached witness
- Power/connection path: board powered stably; HID device attached first directly to the ESP32-S3 USB host path, then through the powered hub

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
./scripts/flash.sh --monitor
```

### 4) Monitor (alternative wrapper)
```bash
./scripts/monitor.sh
```

## Verification procedure
1. Run target build preflight (`./scripts/check_target_build.sh`).
2. Boot board and open monitor.
3. Send `GET_USB_STATUS`.
4. Send `LIST_USB_DEVICES`.
5. Plug HID device directly into host path, if the available cabling supports it.
6. Send `GET_USB_STATUS`.
7. Send `LIST_USB_DEVICES`.
8. Unplug HID device.
9. Send `GET_USB_STATUS`.
10. Send `LIST_USB_DEVICES`.
11. Repeat the same pre-plug, post-plug, and post-unplug sequence through the powered hub.
12. If direct attach is physically blocked, record that as a blocker instead of using a synthetic direct transcript.

## Transcript template (paste filled real output back into repo)

```text
Board: <exact board model>
Firmware commit: <git sha>
ESP-IDF baseline: v5.5.3
Powered hub: <exact model, power supply, and upstream/downstream cabling>
HID device: <vendor/product/model if known>
Direct connection path: <direct cable/adapter details>
Hub connection path: <hub/cable/port details>

--- Boot ---
<paste exact boot output>

--- Direct pre-plug ---
>> GET_USB_STATUS
<< <actual output>
>> LIST_USB_DEVICES
<< <actual output>

--- Direct post-plug ---
<paste attach transcript>
>> GET_USB_STATUS
<< <actual output>
>> LIST_USB_DEVICES
<< <actual output>

--- Direct post-unplug ---
<paste detach transcript>
>> GET_USB_STATUS
<< <actual output>
>> LIST_USB_DEVICES
<< <actual output>

--- Hub pre-plug ---
>> GET_USB_STATUS
<< <actual output>
>> LIST_USB_DEVICES
<< <actual output>

--- Hub post-plug ---
<paste attach transcript>
>> GET_USB_STATUS
<< <actual output>
>> LIST_USB_DEVICES
<< <actual output>

--- Hub post-unplug ---
<paste detach transcript>
>> GET_USB_STATUS
<< <actual output>
>> LIST_USB_DEVICES
<< <actual output>
```

## Acceptance notes
- Do not replace this template with expected output.
- Only real captured output qualifies as milestone evidence.
- M2B.1 must remain marked as pending hardware verification until transcript is checked in.
