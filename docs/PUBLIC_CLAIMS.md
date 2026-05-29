# Public Claims Guide

This document protects contributor trust by separating evidence-backed public
claims from tempting overclaims.

## Allowed Claims

These claims are supported by checked-in evidence:

- USB2BLE is experimental ESP32-S3 firmware for bridging USB HID input to BLE
  gamepad personas.
- The practical RJ12 Flight Pack topology has target-side axis-label evidence.
- Runtime config import/save/load across an actual board reset is proven.
- Chrome Web Serial configurator smoke is proven.
- Refined Generic Flight Pack mapping/report encoding is target-witnessed.
- Refined Generic `z/rx/ry/rz` axis exposure is visible in Chrome Gamepad API.
- Refined Generic live bridge completed a 300-second Chrome/browser soak.
- A self-hosted browser game/app smoke completed using the refined Generic
  profile.
- Xbox BLE identity/report publishing has a macOS pairing/input witness for the
  existing Xbox slice.
- Xbox BLE Profile v1 has target-side model-1914 profile/report-map diagnostics
  and checker evidence; this is not host-visible refined mapping evidence.
- A current Xbox macOS/Chrome deterministic diagnostic reached target BLE
  `Connected`; Chrome exposed `USB2BLE Gamepad (STANDARD GAMEPAD)` with
  `mapping="standard"` and expected standard stick, trigger, D-pad, A, and B
  movement, while several other button positions did not match.

## Forbidden Overclaims

Do not claim any of these until matching checked-in evidence exists:

- broad game/app compatibility,
- external/native game compatibility,
- iPhone compatibility,
- Xbox host-visible refined Flight Pack mapping,
- complete Xbox standard button layout,
- BLE bond persistence or reconnect robustness,
- final product-quality calibration or deadzone feel,
- broad host/browser support,
- three-separate-USB Flight Pack streaming,
- consumer-ready or safety-critical reliability.

## Preferred Wording

Use:

- "witnessed on..."
- "proven by..."
- "narrow smoke..."
- "not yet proven..."
- "requires separate evidence..."

Avoid:

- "works with games" without naming the exact witnessed app/game,
- "supports Xbox" without scoping to the exact persona and witness,
- "compatible" without host/app/version/evidence,
- "production ready" or "final calibration."
