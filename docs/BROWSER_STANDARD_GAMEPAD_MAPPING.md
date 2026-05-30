# Browser Standard Gamepad Mapping

Status: contract for USB2BLE browser-standard persona witnesses. This document
does not create compatibility claims; it defines what a Chrome/Safari/Firefox
Gamepad API witness must capture before a persona can be called
browser-standard on a specific host/browser.

## Standard Controls

When a browser reports `gamepad.mapping === "standard"`, USB2BLE witnesses use
these expected positions:

| Logical control | Browser position |
| --- | --- |
| A | B0 |
| B | B1 |
| X | B2 |
| Y | B3 |
| LB / left bumper | B4 |
| RB / right bumper | B5 |
| LT / left trigger | B6, analog value 0.0..1.0 |
| RT / right trigger | B7, analog value 0.0..1.0 |
| View / Back / Select | B8 |
| Menu / Start | B9 |
| Left stick press | B10 |
| Right stick press | B11 |
| D-pad up | B12 |
| D-pad down | B13 |
| D-pad left | B14 |
| D-pad right | B15 |
| Left stick X/Y | A0/A1 |
| Right stick X/Y | A2/A3 |

## Witness Rules

- Browser `id` text is useful context, but it is not the sole success criterion.
- `mapping === "standard"` plus correct axes/buttons is stronger evidence than a
  literal device-name match.
- A persona witness should record the browser `id`, `mapping`, axis count,
  button count, full axes/buttons arrays, serial report bytes, expected standard
  positions, observed changed positions, and pass/fail for each scenario.
- Host/browser behavior can remap or suppress controls. If a host exposes a
  partial standard layout, evidence must call that partial and list mismatches.
- Browser Gamepad API evidence is host-visible HID evidence. It is not, by
  itself, real app/game compatibility.

## Current USB2BLE Status

| Persona | macOS Chrome status | Evidence |
| --- | --- | --- |
| Generic Gamepad | Refined Flight Pack axes `z/rx/ry/rz` are host-visible as A2/A3/A4/A5; 300-second refined Generic live bridge soak is witnessed. | `docs/milestone-evidence/REFINED_GENERIC_AXIS_EXPOSURE_WITNESS_2026-05-28.md`; `docs/milestone-evidence/REFINED_GENERIC_LIVE_BRIDGE_SOAK_WITNESS_2026-05-28.md` |
| Xbox-compatible BLE gamepad | Partial deterministic standard-layout diagnostic: sticks, triggers, D-pad, A/B/X/Y, LB/RB, View, and Menu align; stick-press buttons did not surface at B10/B11. | `docs/milestone-evidence/XBOX_STANDARD_LAYOUT_DIAGNOSTIC_2026-05-29.md` |
| BLE Keyboard / iCade fallback | Planned/not implemented. | none |

## Promotion Criteria

A persona can be marked browser-standard for a host/browser only when checked-in
evidence proves:

- the host connects to the BLE persona,
- the browser exposes a connected Gamepad API device,
- the browser reports `mapping === "standard"`,
- every claimed standard axis/button position is driven by deterministic reports
  or live mapped input,
- serial report bytes match the persona report format,
- limitations are documented for controls that are not exposed or not aligned.
