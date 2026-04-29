# Compatibility Matrix

This matrix tracks the support status for devices, personas, and milestones.

## Milestones

| Milestone | Status | Note | Evidence |
|-----------|--------|------|----------|
| M0 | Complete | Repo skeleton and contracts baseline | Host test evidence |
| M1 | Complete | Boot + serial control witness | Real target transcript (historical) |
| M2A | Complete | USB contracts/app/control groundwork | Host tests |
| M2B.1 | Partial hardware evidence | Hub attach/detach identity and HID-class discovery captured; direct attach blocked by cabling | `docs/milestone-evidence/M2B1_HUB_WITNESS_2026-04-28.md` |
| M2B.2 | Partial hardware evidence | HID report descriptor capture via control-plane works; live input report capture pending | `docs/milestone-evidence/M2B2_DESCRIPTOR_WITNESS_2026-04-29.md` |
| M3 | Planned | HID Parser | |
| M4 | Planned | Live input | |
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
| THRUSTMASTER T.16000 FCS HOTAS | 044f | b10a | Descriptor capture witness captured | Enumerates behind HooToo hub with one HID `CLASS=03` interface; app reports `interfaces=1`; `GET_USB_DESCRIPTOR` returned 134 bytes |
| THRUSTMASTER T.16000M FCS FLIGHT PACK device | 044f | b687 | Hub downstream identity and HID interface witness captured | One of three simultaneous Flight Pack devices; exact physical unit mapping not captured; app contributes one HID interface |
| THRUSTMASTER T.16000M FCS FLIGHT PACK device | 044f | b679 | Hub downstream identity and HID interface witness captured | One of three simultaneous Flight Pack devices; exact physical unit mapping not captured; app contributes one HID interface |
| THRUSTMASTER T.16000M FCS FLIGHT PACK device | 044f | b10a | Hub downstream identity and HID interface witness captured | One of three simultaneous Flight Pack devices; exact physical unit mapping not captured; app contributes one HID interface |

## Personas

| Persona | ID | Status | Note |
|---------|----|--------|------|
| Generic Gamepad | `generic_gamepad` | Planned | Not in M2B scope |
| Xbox Wireless | `xbox_wireless` | Planned | Not in M2B scope |
