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
- 2026-06-03: `docs/milestone-evidence/MINIMAL_BLE_ADVERTISING_ISOLATION_2026-06-03.md`
  records a standalone ESP32-S3 BLE advertiser that avoids USB2BLE app, USB
  host, HIDD, personas, mapping, and bridge code. It reproduced the same async
  advertising-start status `13` after raw config success and immediate start
  return `0`; Windows did not see `BLE_SMOKE`.
- 2026-06-03: `docs/milestone-evidence/FIRMWARE_PROVENANCE_BLE_ADVERTISING_DIAGNOSTIC_2026-06-03.md`
  records a firmware provenance A/B on this same board and Windows watcher.
  Published `v0.1.0-alpha` firmware advertised `USB2BLE Gamepad` after
  `START_BLE_GENERIC_GAMEPAD`, while public Pages/current and Windows-local
  current firmware did not advertise for the tested raw-smoke or Generic paths.
- 2026-06-03: `docs/milestone-evidence/BLE_ADVERTISING_REGRESSION_FIX_WITNESS_2026-06-03.md`
  records source-built alpha and bisect evidence for the post-alpha advertising
  regression, then verifies fixed current firmware advertisements for raw
  smoke, Generic default, and Xbox persona modes with the native Windows BLE
  watcher.
- 2026-06-04: `docs/milestone-evidence/WINDOWS_BLUETOOTH_PAIRING_DIAGNOSTIC_2026-06-04.md`
  and `docs/milestone-evidence/WINDOWS_BLE_IDENTITY_CACHE_DIAGNOSTIC_2026-06-04.md`
  record Windows pairing/cache diagnostics for same-address personas, including
  Generic/U6 host-visible HID and Xbox XInput evidence when Windows cache was
  cleaned between tests.
- 2026-06-04: `docs/milestone-evidence/WINDOWS_PER_PERSONA_STATIC_RANDOM_IDENTITY_DIAGNOSTIC_2026-06-04.md`
  records that `persona_static_random_experimental` produced distinct
  advertised addresses for Generic default, U6, and Xbox. Each persona paired
  individually after Windows Settings intervention, and Xbox exposed XInput
  deterministic reports. It does not prove cache-free switching or coexistence:
  Alex reported that the previous persona still had to be removed before the
  next persona would connect.
- 2026-06-04: `docs/milestone-evidence/WINDOWS_XBOX_XINPUT_WITNESS_2026-06-04.md`
  records the product-progress path after the cache-free switching diagnostic:
  single-persona Xbox BLE-compatible mode paired as `Xbox Wireless Controller`,
  exposed HID `045e:0b13`, connected XInput slot 0, drove deterministic and
  virtual Flight Pack Xbox mappings through XInput, and showed movement in
  `joy.cpl` Properties. This is still a single-PC diagnostic and controller
  panel smoke, not broad Windows or real game compatibility.
- 2026-06-04:
  `docs/milestone-evidence/WINDOWS_XBOX_APP_COMPATIBILITY_WITNESS_2026-06-04_SPYRO_REIGNITED_TRILOGY.md`
  records one installed-game data point for the same single-persona Xbox path:
  Spyro Reignited Trilogy 1.0.1.0 stayed open while virtual Xbox mapping and
  deterministic reports moved XInput, and Alex observed controls moving plus
  menu items being selected. This is one PC, one game, and virtual input only.
- 2026-06-04: `docs/milestone-evidence/WINDOWS_XBOX_RECONNECT_DIAGNOSTIC_2026-06-04.md`
  records the next reconnect diagnostic. Baseline manual Windows pairing still
  exposed `Xbox Wireless Controller`, HID `045e:0b13`, and XInput slot 0 with
  deterministic report movement. After target soft reset, however, the target
  returned to `legacy_public` with no active persona and `bonds=false`;
  reapplying the Xbox persona restored apparent Windows/target connection state
  but deterministic reports did not move XInput and later publish attempts
  returned `ERROR:Generic`. Durable BLE bond persistence and reconnect/report
  delivery robustness remain unproven.
- 2026-06-09:
  `docs/milestone-evidence/WINDOWS_XBOX_RECONNECT_FIX_DIAGNOSTIC_2026-06-09.md`
  records the follow-up reconnect/report-delivery fix diagnostic. New target
  diagnostics expose connection state, report-send status, publish counters,
  and ESP-IDF bond count/list. `STOP_BLE_PERSONA` provides a clean stop path
  without clearing bonds. After one manual baseline Windows pairing, stop/start
  persona and target soft reset plus explicit Xbox strategy/persona reapply both
  restored XInput report delivery without Windows cache cleanup. Direct
  `DISCONNECT_BLE_HOST` remains unsupported, runtime identity/persona still do
  not persist across reset, and durable BLE bond persistence is not fully
  proven.
- 2026-06-09:
  `docs/milestone-evidence/WINDOWS_XBOX_STARTUP_RECONNECT_WITNESS_2026-06-09.md`
  records explicit persisted startup BLE config for the single-persona Xbox
  path. With startup BLE enabled for Xbox plus
  `persona_static_random_experimental`, target soft reset and an
  operator-assisted ESP32-S3 serial USB power-cycle both restored the Xbox
  persona/address without serial strategy/persona reapply or Windows
  remove/re-pair. A one-time startup warm restart landed the ESP-IDF HIDD path
  in the known-good report-delivery state, and deterministic reports moved
  XInput after both reset paths. Direct `DISCONNECT_BLE_HOST`, deeper
  auth/encryption telemetry, durable BLE bond persistence, and post-reset
  app/game behavior remain unproven.
- 2026-06-10:
  `docs/milestone-evidence/WINDOWS_XBOX_STARTUP_RECONNECT_SOAK_WITNESS_2026-06-10.md`
  records richer ESP-IDF auth/security telemetry in `GET_BLE_BOND_INFO` and a
  five-cycle target soft-reset soak of the explicit persisted single-persona
  Xbox startup path. Each cycle restored the Xbox address/persona, kept XInput
  slot 0 connected, and moved deterministic reports without Windows
  remove/re-pair, serial persona reapply, or physical control movement. The
  target now reports auth-complete status and a bond-list entry, but active
  encryption/authentication and complete key persistence remain unproven.
- The next Windows hardware chunk should build from the single-persona Xbox
  path, with explicit startup reconnect/report delivery preserved. The next gap
  is either a longer no-removal reset/power-cycle soak, direct host-disconnect
  support if ESP-IDF exposes a safe path, or a post-reset app/game micro-smoke,
  not cache-free Generic/U6/Xbox switching. Do not treat
  advertisement visibility, apparent XInput connection, or PnP presence as
  app/game compatibility, durable bond persistence, or cache-free switching
  evidence.

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
