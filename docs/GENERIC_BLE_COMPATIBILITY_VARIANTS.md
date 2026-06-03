# Generic BLE Compatibility Variants

USB2BLE keeps `generic_default` as the proven Generic BLE Gamepad path. Host-specific experiments must be explicit, non-default, and evidence-gated before they can be promoted.

## Current Default

`generic_default`

- Persona: `generic_gamepad`
- Identity: `USB2BLE Gamepad`, VID/PID `303a:4001`
- Report shape: buttons, hat, signed 16-bit `X/Y/Z/Rx/Ry/Rz`
- Axis offsets: `X` byte 3, `Y` byte 5, `Z` byte 7, `Rx` byte 9, `Ry` byte 11, `Rz` byte 13
- Status: evidence-backed for earlier macOS/Chrome real-input Generic Flight Pack path; current virtual replay diagnostics show partial host callback delivery on this Mac for later axes.

## Implemented Experiment

`generic_unsigned_6axis`

- Persona: `generic_gamepad`
- Identity: `USB2BLE Gamepad U6`, VID/PID `303a:4002`
- Report shape: same buttons, hat, and six Generic Desktop axes as `generic_default`
- Axis value type: unsigned 16-bit centered range `0..65535`
- Neutral axis value: `32768`
- Purpose: test whether macOS/Chrome deliver all six refined Flight Pack axes more reliably when the Generic Desktop axes use an unsigned logical range.
- Claim boundary: experimental macOS/Chrome delivery variant; not broad host compatibility and not physical USB movement evidence.
- Hardware A/B result: `docs/milestone-evidence/GENERIC_COMPAT_VARIANT_DIAGNOSTIC_2026-06-02.md` verified the variant on target, but unsigned logical ranges did not improve the missing macOS HID/Chrome delivery for the later refined Generic axes. Keep this variant non-default.

## Candidate Experiments

`generic_compact_4axis_2trigger`

- Purpose: prioritize common browser/game compatibility if hosts continue to ignore `Ry/Rz`.
- Sketch: expose `X/Y/Z/Rx` as axes and map toe brakes to trigger-like controls or buttons.
- Status: design candidate only.

`generic_split_collections`

- Purpose: test whether clearer physical collections improve host delivery of later axes.
- Sketch: split left stick, throttle/rudder, and toe axes into separate physical collections while keeping the same logical controls.
- Status: design candidate only.

## Promotion Rule

A Generic compatibility variant can move toward supported status only after checked-in evidence shows:

1. host discovery and pairing,
2. descriptor/profile diagnostics,
3. target mapping/report changes,
4. BLE bridge publication,
5. macOS HID or equivalent host-layer delivery for intended controls,
6. browser/app exposure when browser compatibility is claimed,
7. limitations documented in the evidence index and compatibility matrix.
