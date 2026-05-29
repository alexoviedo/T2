# Compatibility Matrix

This matrix tracks the support status for devices, personas, and milestones.

## Milestones

| Milestone | Status | Note | Evidence |
|-----------|--------|------|----------|
| M0 | Complete | Repo skeleton and contracts baseline | Host test evidence |
| M1 | Complete | Boot + serial control witness | Real target transcript (historical) |
| M2A | Complete | USB contracts/app/control groundwork | Host tests |
| M2B.1 | Partial hardware evidence | Hub attach/detach identity and HID-class discovery captured; direct attach blocked by cabling | `docs/milestone-evidence/M2B1_HUB_WITNESS_2026-04-28.md` |
| M2B.2 | Hardware evidence captured | HID report descriptor and raw input report capture via control-plane works for the T.16000 FCS HOTAS through the hub | `docs/milestone-evidence/M2B2_DESCRIPTOR_WITNESS_2026-04-29.md` |
| M3 | Summary hardware evidence captured | HID parser and capability summary work for the T.16000 FCS HOTAS descriptor on host and target | `docs/milestone-evidence/M3_HID_SUMMARY_WITNESS_2026-04-29.md` |
| M4 | Expanded hardware evidence captured | Normalized live-input diagnostics work for the T.16000 stick, TFRP pedals, TWCS throttle, and the RJ12 two-USB Flight Pack topology; practical RJ12 axis labels are witnessed; button/detach and simultaneous three-separate-USB streaming remain open | `docs/milestone-evidence/M4_NORMALIZED_INPUT_WITNESS_2026-04-29.md`; `docs/milestone-evidence/M4_FLIGHT_PACK_NORMALIZED_WITNESS_2026-04-29.md`; `docs/milestone-evidence/M4_RJ12_TWO_USB_FLIGHT_PACK_WITNESS_2026-04-29.md`; `docs/milestone-evidence/FLIGHT_PACK_CALIBRATION_WITNESS_2026-05-28.md` |
| M5 | Generic BLE self-test witnessed | Generic Gamepad BLE advertising, macOS pairing/input, and synthetic self-test input are witnessed. `FORGET_BLE_BONDS` exists as a command path, but bond-clear recovery and durable bond persistence are not proven. | `docs/milestone-evidence/BLE_HID_DEMO_CODEPATH_BUILD_WITNESS_2026-04-30.md`; `docs/milestone-evidence/BLE_HID_GENERIC_GAMEPAD_ADVERTISING_WITNESS_2026-04-30.md`; `docs/milestone-evidence/BLE_HID_MAC_PAIRING_INPUT_WITNESS_2026-04-30.md`; `docs/milestone-evidence/BROWSER_GAMEPAD_API_WITNESS_2026-04-30.md` |
| M6 | Demo bridge slice witnessed; formal hardening open | Generic Gamepad USB-derived BLE publish and explicit live bridge are witnessed through macOS/browser evidence; practical RJ12 Flight Pack target-side mapping refinement, host-visible Generic axis exposure, a refined Generic 300-second live bridge soak, and a self-hosted browser game/app smoke are witnessed; broad external/native game/app compatibility, reconnect hardening, and final calibration are not proven | `docs/milestone-evidence/FLIGHT_PACK_DEMO_BLE_BROWSER_WITNESS_2026-05-08.md`; `docs/milestone-evidence/ASAP_DEMO_REHEARSAL_WITNESS_2026-05-08.md`; `docs/milestone-evidence/LIVE_BRIDGE_WITNESS_2026-05-10.md`; `docs/milestone-evidence/FLIGHT_PACK_MAPPING_REFINEMENT_WITNESS_2026-05-28.md`; `docs/milestone-evidence/REFINED_GENERIC_AXIS_EXPOSURE_WITNESS_2026-05-28.md`; `docs/milestone-evidence/REFINED_GENERIC_LIVE_BRIDGE_SOAK_WITNESS_2026-05-28.md`; `docs/milestone-evidence/GAME_COMPATIBILITY_WITNESS_2026-05-28_SELF_HOSTED_SKY_RUN.md` |
| M11 | Xbox persona slice witnessed; broad compatibility open | Xbox report encoding, BLE identity/report publishing, macOS pairing/input, browser VID/PID support, and Xbox live bridge/soak evidence exist; app/game compatibility and host breadth are not claimed | `docs/milestone-evidence/XBOX_BLE_WITNESS_2026-05-09.md`; `docs/milestone-evidence/LIVE_BRIDGE_WITNESS_2026-05-10.md`; `docs/milestone-evidence/LIVE_BRIDGE_SOAK_WITNESS_2026-05-10.md` |

## Toolchain

| Component | Version / Setting | Status | Note |
|-----------|-------------------|--------|------|
| ESP-IDF | `v5.5.3` via `crates/usb2ble-fw/Cargo.toml` | Baseline | No checked-in `IDF_PATH`; local env overrides bypass this pin |
| `esp-idf-sys` | `0.37.2` resolved from `esp-idf-sys = "0.37"` | Baseline | 0.37.x line retained |
| USB host hub config | `CONFIG_USB_HOST_HUBS_SUPPORTED=y` | Hub identity witness captured | Stable hub config; no experimental hub flag |

## Devices

| Device | VID | PID | Status | Note |
|--------|-----|-----|--------|------|
| HooToo SHUTTLE HT-UC001 powered hub | 2109 | 2813 | Hub identity and interface-class witness captured | Enumerates through ESP32-S3 USB host path as USB hub class `09` |
| AFTERGLOW PL-3702 Xbox-style wired gamepad | 0e6f | 0213 | Hub downstream identity and interface-class witness captured | Enumerates behind HooToo hub with four vendor-specific `CLASS=ff` interfaces; `interfaces=0` is expected for HID-only bookkeeping |
| USB keyboard, exact model not captured | 30fa | 2031 | Hub downstream identity and HID interface witness captured | Enumerates behind HooToo hub with two HID `CLASS=03` interfaces; app reports `interfaces=2` |
| THRUSTMASTER T.16000 FCS HOTAS | 044f | b10a | Descriptor, raw input report, HID summary, and baseline normalized-input witness captured | Enumerates behind HooToo hub with one HID `CLASS=03` interface; app reports `interfaces=1`; `GET_USB_DESCRIPTOR` returned 134 bytes; `GET_LAST_USB_REPORT` returned a 64-byte raw input report; `GET_HID_SUMMARY` returned 4 axes, 16 buttons, 1 hat, report ID 0; `GET_NORMALIZED_INPUT` returned 21 controls |
| THRUSTMASTER T.16000M FCS FLIGHT PACK device | 044f | b687 | TWCS normalized-input, practical RJ12 axis-label, refined target-side mapping, and host-visible Generic axis exposure witnesses captured | App contributes one HID interface; with TFRP pedals connected by RJ12, TWCS normalized axes changed during pedals-only movement; checked-in labels identify TWCS throttle as `axis_01_32`, RJ12 rudder as `axis_01_36`, left toe as `axis_01_34`, and right toe as `axis_01_33`; target-side refined mapping sends throttle/rudder/toe axes to intended Generic/Xbox controls with documented Xbox throttle compromise; browser Gamepad API evidence maps refined Generic `z/rx/ry/rz` to A2/A3/A4/A5 in Chrome on the witnessed Mac; three-separate-USB full-pack capture can fail with `ESP_ERR_NOT_SUPPORTED` while claiming the third interrupt stream |
| THRUSTMASTER T.16000M FCS FLIGHT PACK device | 044f | b679 | TFRP normalized-input witness captured as separate USB and through RJ12-to-TWCS topology | As separate USB, normalized report returned 3 axes plus vendor usages; through RJ12, pedal movement is represented in the TWCS `044f:b687` normalized report, with axis labels captured in `docs/milestone-evidence/FLIGHT_PACK_CALIBRATION_WITNESS_2026-05-28.md` |
| THRUSTMASTER T.16000M FCS FLIGHT PACK device | 044f | b10a | Hub downstream identity, HID interface, baseline normalized-input witness, and RJ12 two-USB simultaneous witness captured | App contributes one HID interface; normalized stream runs simultaneously with TWCS in the RJ12 two-USB topology; can fail as the third stream in the three-separate-USB topology depending on enumeration order |

## Personas

| Persona | ID | Status | Note |
|---------|----|--------|------|
| Generic Gamepad | `generic_gamepad` | Witnessed demo bridge path | Starts on ESP32-S3, pairs/connects to macOS, publishes synthetic and live USB-derived reports, appears in browser Gamepad API, works with `START_BRIDGE`, exposes refined practical RJ12 Flight Pack `z/rx/ry/rz` axes as browser A2/A3/A4/A5 in the checked-in Chrome witness, has a checked-in 300-second refined Generic live bridge soak, and passes a self-hosted browser game/app smoke. This is not broad external/native game/app compatibility, not final Flight Pack calibration, and not durable bond persistence. |
| Xbox Wireless Controller | `xbox_wireless_controller` | Witnessed compatibility persona slice | Starts on ESP32-S3 with Xbox model 1914 / Series X\|S BLE identity, pairs/connects on macOS as `Xbox Wireless Controller`, publishes synthetic and USB-derived 16-byte reports, exposes Xbox VID/PID in browser evidence, and works with `START_BRIDGE`. Broad Xbox/game/app compatibility is not claimed. |

## Compatibility Claim Boundaries

- Browser Gamepad API evidence is host-visible HID support, not a real game/app
  witness.
- Broad game/app compatibility remains unclaimed until evidence following
  `docs/GAME_COMPATIBILITY_WITNESS.md` is checked in.
- Xbox support is limited to the checked-in macOS/browser compatibility evidence
  and live bridge/soak transcripts; it is not a claim of console, Windows,
  Steam, or arbitrary app compatibility.
- Runtime configuration APIs and Web Serial tooling exist, and durable runtime
  config persistence is proven by
  `docs/milestone-evidence/CONFIG_PERSISTENCE_WITNESS_2026-05-28.md`.
- Browser Web Serial configurator smoke is proven for Google Chrome by
  `docs/milestone-evidence/WEB_SERIAL_CONFIGURATOR_SMOKE_2026-05-28.md`.
  Browser breadth and product-ready recovery behavior remain unproven.
- Practical RJ12 Flight Pack axis labels are proven by
  `docs/milestone-evidence/FLIGHT_PACK_CALIBRATION_WITNESS_2026-05-28.md`;
- Practical RJ12 Flight Pack target-side mapping refinement is proven by
  `docs/milestone-evidence/FLIGHT_PACK_MAPPING_REFINEMENT_WITNESS_2026-05-28.md`.
- Practical RJ12 Flight Pack refined Generic host-visible axis exposure is proven
  by
  `docs/milestone-evidence/REFINED_GENERIC_AXIS_EXPOSURE_WITNESS_2026-05-28.md`.
- Refined practical RJ12 Generic 300-second live bridge soak is proven by
  `docs/milestone-evidence/REFINED_GENERIC_LIVE_BRIDGE_SOAK_WITNESS_2026-05-28.md`.
- Self-hosted browser game/app smoke for the refined practical RJ12 Generic
  profile is proven by
  `docs/milestone-evidence/GAME_COMPATIBILITY_WITNESS_2026-05-28_SELF_HOSTED_SKY_RUN.md`.
  Final deadzone/calibration quality, real game/app mapping quality, and Xbox
  host-visible refined mapping remain unproven.
- iPhone compatibility remains unproven. The first iPhone exploration is checked
  in as a useful failure: the target reported Generic BLE HID advertising, but
  the iPhone did not discover `USB2BLE Gamepad` in Settings > Bluetooth. See
  `docs/milestone-evidence/IPHONE_SAFARI_GENERIC_GAMEPAD_FAILURE_2026-05-29.md`
  and the follow-up target-side advertising diagnostic in
  `docs/milestone-evidence/IPHONE_BLE_ADVERTISING_DIAGNOSTIC_2026-05-29.md`.
