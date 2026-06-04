# Windows Compatibility Witness

Status: Windows hardware/game compatibility plan with one partial diagnostic
attempt and one target USB topology recovery witness recorded. This document is
not itself compatibility evidence.

## Current Windows Evidence

- 2026-06-03: `docs/milestone-evidence/WINDOWS_HARDWARE_BRINGUP_WITNESS_2026-06-03.md`
  records COM port autodetection, firmware flash, target control-plane health,
  hub-only USB topology, target-side Generic/Xbox virtual bridge publication,
  and negative Windows Raw Input/XInput/Chrome Gamepad API visibility for that
  run.
- 2026-06-03: `docs/milestone-evidence/WINDOWS_USB_HOST_TOPOLOGY_WITNESS_2026-06-03.md`
  records recovery of downstream target USB host enumeration for HooToo
  (`2109:2813`), T.16000M (`044f:b10a`), and TWCS/RJ12 (`044f:b687`) on Alex's
  Windows PC after flashing an ESP-IDF v5.5.3 target build. This is target-side
  USB topology evidence only.
- 2026-06-03: `docs/milestone-evidence/WINDOWS_BLE_HOST_VISIBLE_DIAGNOSTIC_2026-06-03.md`
  records a negative Windows host-visible BLE diagnostic after topology
  recovery: Generic default, Generic HOGP-strict, Generic unsigned six-axis, and
  Xbox personas reported target-side advertising intent, but Windows active BLE
  scans, PnP/Raw Input/XInput, and Edge Gamepad API did not expose a USB2BLE
  controller.
- 2026-06-03: `docs/milestone-evidence/WINDOWS_BLE_ADVERTISING_LAB_2026-06-03.md`
  records native Windows BLE advertisement watching plus target GAP lifecycle
  counters. Raw GAP smoke advertising and Generic/Xbox HID persona advertising
  all failed at GAP advertising start status `13`, while Windows captured
  ambient BLE advertisements.
- 2026-06-03: `docs/milestone-evidence/BLE_ADVERTISING_START_DIAGNOSTIC_2026-06-03.md`
  records follow-up raw GAP smoke experiments. Local ESP-IDF bindings identify
  status `13` as `ESP_BT_STATUS_PENDING`; raw payload config and immediate
  start returns succeeded, but async start-complete still reported status `13`
  and Windows did not see USB2BLE advertisements.
- The next Windows hardware chunk should investigate the ESP-IDF/Bluedroid GAP
  advertising-start pending completion before retrying Windows pairing or
  Gamepad API tests.

## Hardware Setup

Use this setup only after no-hardware validation is passing or the remaining
blockers are documented:

1. ESP32-S3 connected to the Windows PC by serial/programming USB.
2. HooToo hub connected to the ESP32-S3 USB host/OTG path.
3. T.16000M stick and TWCS throttle plugged into the HooToo hub.
4. TFRP pedals connected to TWCS by RJ12.

Do not treat a synthetic or virtual-input run as physical HOTAS movement.

## Bluetooth Pairing Identities

- Generic default: `USB2BLE Gamepad`
- Xbox persona: `Xbox Wireless Controller`
- Generic unsigned experiment: `USB2BLE Gamepad U6`

Pair one persona/variant at a time and record any host-side forget, bond clear,
reset, or reboot step. Host Bluetooth cache behavior is part of the witness, not
background noise to hide.

## Test Layers

1. Serial target status: capture `GET_INFO`, `GET_STATUS`, `GET_USB_STATUS`,
   `LIST_USB_DEVICES`, active persona/variant status, bridge counters, and any
   virtual-input status if used.
2. Windows Bluetooth/HID visibility: capture Windows Bluetooth UI state,
   PnP/HID inventory, and Raw Input/HID enumeration where available.
3. API visibility: run `tools/windows_gamepad_probe.py` and distinguish XInput,
   Raw Input/HID, browser Gamepad API, and GameInput status. XInput is expected
   to see Xbox-compatible controllers only; Generic HID may be invisible there.
4. Steam/Input/game target: capture Steam Input controller test, a controller
   calibration screen, or another low-friction target before attempting a heavy
   game.
5. Game/app witness: follow `docs/GAME_COMPATIBILITY_WITNESS.md` and record
   app/game name, version, host OS, persona, variant, screenshots/logs, serial
   bridge deltas, observed controls, and limitations.

## Virtual Replay Path

Virtual normalized-input replay may be used before physical movement to test:

```text
virtual normalized input -> runtime mapping -> persona encoder -> BLE report -> Windows host/API layer
```

The witness must label this as virtual normalized-input evidence. It cannot
prove physical USB movement, HID parser behavior for a new device, calibration
feel, broad host compatibility, or game compatibility.

## Physical Movement

Ask Alex to move HOTAS controls only when the immediate run needs evidence that
cannot be produced by serial state, profile checks, API inventory, or virtual
replay. The prompt should name the exact control and movement, such as
T.16000M stick left/right, TWCS throttle min/max, TFRP rudder left/right, or toe
brake press/release.

## Evidence Rules

- Do not claim Windows compatibility, external/native game compatibility, broad
  host support, BLE bond persistence, physical USB movement, or final Flight
  Pack calibration quality without checked-in evidence.
- Keep generated transcripts and screenshots under `target/`.
- Add reviewed witness summaries under `docs/milestone-evidence/` only after
  the artifacts support the claim.
- Link checked-in witness summaries from `docs/EVIDENCE_INDEX.md` and update
  compatibility matrices only to the level proven by the evidence.
- Preserve `generic_default` unless a separate, evidence-backed migration plan
  exists.

## Ready-To-Run Hardware Prompt

When the Windows environment is ready for immediate hardware testing, ask:

```text
Attach the ESP32-S3 serial/programming USB to this PC. Attach the HooToo hub to
the ESP32-S3 USB host/OTG path. Plug T.16000M and TWCS into the hub, and connect
TFRP pedals to TWCS by RJ12. Then tell me when Windows detects the ESP32-S3
serial port.
```
