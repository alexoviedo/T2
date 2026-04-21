# Compatibility Matrix

This matrix tracks the support status for devices, personas, and milestones.

## Milestones

| Milestone | Status | Note | Evidence |
|-----------|--------|------|----------|
| M0 | In Progress | Initial bootstrap and contracts | Unit tests, PR review |
| M1 | Planned | Boot and serial control | |
| M2 | Planned | USB witness | |
| M3 | Planned | HID Parser | |
| M4 | Planned | Live input | |
| M5 | Planned | BLE self-test | |
| M6 | Planned | E2E Usable slice | |

## Devices

| Device | VID | PID | Status | Note |
|--------|-----|-----|--------|------|
| Generic Keyboard | Any | Any | Planned | Curated list TBD |
| Generic Mouse | Any | Any | Planned | |
| Generic Gamepad | Any | Any | Planned | |

## Personas

| Persona | ID | Status | Note |
|---------|----|--------|------|
| Generic Gamepad | `generic_gamepad` | Planned | Standard HID Gamepad |
| Xbox Wireless | `xbox_wireless` | Planned | BLE Xbox Persona |

## Evidence Notes

- `M0`: Validated via `cargo test --workspace` on host.
