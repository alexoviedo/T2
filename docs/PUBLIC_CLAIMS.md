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
  `Connected`; Chrome exposed `Xbox Wireless Controller (STANDARD GAMEPAD)`
  with `mapping="standard"` and expected standard stick, trigger, D-pad,
  A/B/X/Y, LB/RB, View, and Menu movement. Stick-press buttons did not surface
  at B10/B11, so this is still not a complete Xbox standard-layout claim.
- Virtual normalized-input replay proves the refined Flight Pack Xbox mapping
  can drive macOS Chrome standard Gamepad controls for stick, rudder, and toe
  brake mappings through the live bridge. This is virtual-input regression
  evidence, not physical USB movement evidence.
- Generic virtual replay remains diagnostic: the latest HID delivery evidence
  narrows the incomplete Generic browser replay to macOS HID delivery for later
  axes. The follow-up descriptor diagnostic confirms the default descriptor and
  encoder declare/write all six axes as intended, but it is still not a
  complete Generic virtual browser replay claim. The `generic_unsigned_6axis`
  A/B diagnostic verified the experimental variant on target, but did not
  improve the missing macOS HID/Chrome delivery, so it is not a supported
  replacement for `generic_default`.
- On Alex's Windows 11 PC, the explicit
  `persona_static_random_experimental` strategy produced distinct stable
  advertised addresses for Generic default, U6, and Xbox. Each persona could be
  paired individually after Windows Settings intervention, and Xbox exposed
  XInput slot 0 deterministic reports. This is partial diagnostic evidence only:
  Alex reported manual removal of the previous persona was still required before
  the next persona would connect.
- On Alex's Windows PC, single-persona Xbox BLE-compatible mode can pair as
  `Xbox Wireless Controller`, expose HID `045e:0b13`, connect XInput slot 0,
  drive deterministic and virtual Flight Pack Xbox mappings through XInput, and
  show movement in `joy.cpl` Properties. This is a single-PC Windows XInput and
  controller-panel witness, not broad Windows or real game compatibility.
- On Alex's Windows PC, the same single-persona Xbox BLE-compatible path has one
  installed-game data point: Spyro Reignited Trilogy 1.0.1.0 stayed open while
  virtual Flight Pack Xbox mapping and deterministic Xbox reports moved XInput,
  and Alex observed controls moving plus menu items being selected in Spyro.
  This is one PC and one game target, with virtual input only.
- On Alex's Windows PC, a follow-up single-persona Xbox reconnect diagnostic
  showed the current reset/reconnect gap: after target soft reset, Windows and
  the target could show an apparently connected Xbox path, but deterministic
  reports did not resume XInput movement and later target publish attempts
  returned `ERROR:Generic`. This is failure/diagnostic evidence, not reconnect
  robustness.

## Forbidden Overclaims

Do not claim any of these until matching checked-in evidence exists:

- broad game/app compatibility,
- broad external/native game compatibility,
- physical HOTAS movement in Spyro or other games,
- treating `joy.cpl` controller-panel movement as game compatibility,
- iPhone compatibility,
- physical Xbox host-visible refined Flight Pack movement from real USB input,
- complete Xbox standard button layout, including stick-press buttons,
- BLE bond persistence or reconnect robustness,
- cache-free Windows persona switching or Generic/U6/Xbox coexistence,
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
