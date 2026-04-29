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
| M4 | Expanded hardware evidence captured | Normalized live-input diagnostics work for the T.16000 stick, TFRP pedals, TWCS throttle, and the RJ12 two-USB Flight Pack topology; button/detach and simultaneous three-separate-USB streaming remain open | `docs/milestone-evidence/M4_NORMALIZED_INPUT_WITNESS_2026-04-29.md`; `docs/milestone-evidence/M4_FLIGHT_PACK_NORMALIZED_WITNESS_2026-04-29.md`; `docs/milestone-evidence/M4_RJ12_TWO_USB_FLIGHT_PACK_WITNESS_2026-04-29.md` |
| M5 | Planned | BLE self-test | |
| M6 | Planned | E2E usable slice | |

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
| THRUSTMASTER T.16000M FCS FLIGHT PACK device | 044f | b687 | TWCS normalized-input witness captured when isolated and in the RJ12 two-USB topology | App contributes one HID interface; with TFRP pedals connected by RJ12, TWCS normalized axes changed during pedals-only movement; three-separate-USB full-pack capture can fail with `ESP_ERR_NOT_SUPPORTED` while claiming the third interrupt stream |
| THRUSTMASTER T.16000M FCS FLIGHT PACK device | 044f | b679 | TFRP normalized-input witness captured as separate USB and through RJ12-to-TWCS topology | As separate USB, normalized report returned 3 axes plus vendor usages; through RJ12, pedal movement is represented in the TWCS `044f:b687` normalized report, with exact semantic axis labels still pending |
| THRUSTMASTER T.16000M FCS FLIGHT PACK device | 044f | b10a | Hub downstream identity, HID interface, baseline normalized-input witness, and RJ12 two-USB simultaneous witness captured | App contributes one HID interface; normalized stream runs simultaneously with TWCS in the RJ12 two-USB topology; can fail as the third stream in the three-separate-USB topology depending on enumeration order |

## Personas

| Persona | ID | Status | Note |
|---------|----|--------|------|
| Generic Gamepad | `generic_gamepad` | Planned | Not in M2B scope |
| Xbox Wireless | `xbox_wireless` | Planned | Not in M2B scope |
