# Compatibility Matrix

This matrix tracks the support status for devices, personas, and milestones.

## Milestones

| Milestone | Status | Note | Evidence |
|-----------|--------|------|----------|
| M0 | Complete | Repo skeleton and contracts baseline | Host test evidence |
| M1 | Complete | Boot + serial control witness | Real target transcript (historical) |
| M2A | Complete | USB contracts/app/control groundwork | Host tests |
| M2B.1 | Code-path implemented (HW verification pending) | Target plumbing present; no checked-in on-device transcript yet | TODO: check-in transcript |
| M2B.2 | Planned | Descriptor/report capture via control-plane | |
| M3 | Planned | HID Parser | |
| M4 | Planned | Live input | |
| M5 | Planned | BLE self-test | |
| M6 | Planned | E2E usable slice | |

## Devices

| Device | VID | PID | Status | Note |
|--------|-----|-----|--------|------|
| Curated HID device #1 | TBD | TBD | Pending witness transcript | Attach/detach + identity only for M2B.1 |

## Personas

| Persona | ID | Status | Note |
|---------|----|--------|------|
| Generic Gamepad | `generic_gamepad` | Planned | Not in M2B scope |
| Xbox Wireless | `xbox_wireless` | Planned | Not in M2B scope |
