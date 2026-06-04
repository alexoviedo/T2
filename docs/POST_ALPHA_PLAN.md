# Post-Alpha Plan

This queue keeps post-`v0.1.0-alpha` work evidence-backed and scoped. It does
not create new compatibility claims; each item defines the evidence needed
before status docs should change.

## 1. External Browser Or Native Game Compatibility Data Point

- Why it matters: proves USB2BLE works in a real third-party app/game surface,
  not only the repo-local browser app smoke or Windows `joy.cpl` controller
  panel.
- Evidence needed: app/game name and version, host OS/browser, active persona,
  bridge counter deltas, screenshots or app logs showing recognized controls,
  orientation notes, and limitations.
- Current best path: single-persona Windows Xbox BLE-compatible mode, because
  `docs/milestone-evidence/WINDOWS_XBOX_XINPUT_WITNESS_2026-06-04.md` proves
  pairing, HID `045e:0b13`, XInput slot 0, virtual mapping, and `joy.cpl`
  controller-panel movement on Alex's PC.
- Hardware/user action: likely required for pairing/app focus; physical
  controls should wait until a virtual-input app/game smoke is understood.
- Recommended next prompt type: Windows single-persona Xbox real app/game
  witness following `docs/GAME_COMPATIBILITY_WITNESS.md`, starting with a
  low-friction app/game target and virtual input before physical movement.
- Risk: medium, because app input handling varies widely.

## 2. Xbox Stick-Press Gap And Physical Refined Live Mapping

- Why it matters: the refined Xbox mapping is target-side proven, and a
  deterministic macOS/Chrome diagnostic now shows `mapping="standard"` with
  expected standard stick, trigger, D-pad, A/B/X/Y, LB/RB, View, and Menu
  movement. Virtual normalized-input replay now proves the refined Xbox
  stick/rudder/toe mapping through the live bridge into Chrome standard controls.
  Chrome did not expose left/right stick press as B10/B11, and physical
  refined Flight Pack host movement is still not separately proven.
- Evidence needed: decide whether the B10/B11 gap is Chrome/macOS suppression,
  report-map button ordering, or descriptor semantics; then capture physical
  refined Flight Pack Xbox movement, serial report bytes, bridge counters,
  browser samples, and limitations. A literal Xbox-like browser `id` is useful
  context but should not be treated as the sole success criterion.
- Hardware/user action: likely required for BLE pairing and physical controls.
- Recommended next prompt type: focused Xbox stick-press descriptor/report-map
  investigation, followed by a physical refined Xbox Flight Pack live-bridge
  witness for rudder and toe brakes with operator movement.
- Risk: medium-high, because host Xbox HID handling and pairing state can be
  sticky.

## 3. BLE Bond And Reconnect Persistence

- Why it matters: early adopters need to know whether reconnect behavior is
  reliable across resets, power cycles, persona switches, and host Bluetooth
  cache states. The 2026-05-31 persona-switching diagnostic showed strict
  browser stale-slot detection works, but no-human Generic browser replay
  remained blocked after target bond clear/reset because macOS/Chrome did not
  reconnect automatically. A manual cleanup follow-up restored Generic BLE HID
  visibility in macOS `hidutil`/`ioreg`, but Chrome still captured zero Generic
  Gamepad API samples while the target bridge published reports. A direct
  Chrome profile diagnostic narrowed this further: the existing Chrome profile
  returned no gamepads, while a clean temporary profile exposed the Generic
  device with empty mapping, 10 axes, and 16 buttons. A follow-up Generic
  virtual bridge diagnostic validated the clean-profile throttle A2 endpoint
  pair, but Chrome did not surface later virtual rudder/toe/stick report
  changes despite target mapping/report and bridge publication changes. A
  lower-level HID delivery diagnostic added a Swift IOKit callback probe and
  showed macOS HID events for Generic X/Y/Z/Rx usages while Ry/Rz toe-axis
  changes and one negative Rx direction did not produce macOS HID callback
  events despite target report and bridge deltas. A descriptor diagnosis then
  confirmed the Generic default descriptor declares X/Y/Z/Rx/Ry/Rz at expected
  offsets, the encoder writes the intended fields, and macOS enumerates all six
  elements, so the current evidence does not justify changing the proven
  default descriptor. The `generic_unsigned_6axis` experiment verified an
  unsigned six-axis variant on target, but A/B diagnostics did not improve the
  missing macOS HID/Chrome delivery for later refined Generic axes. The
  2026-06-04 Windows per-persona static-random diagnostic proved distinct
  advertised addresses for Generic default, U6, and Xbox, but Alex still had to
  remove the previous Windows Bluetooth device before the next persona would
  connect. Cache-free Windows persona switching and coexistence are therefore
  still unproven. The immediate product-progress path moved to single-persona
  Windows Xbox testing, which is checked in separately as
  `docs/milestone-evidence/WINDOWS_XBOX_XINPUT_WITNESS_2026-06-04.md`.
- Evidence needed: before/after bond state, reboot/power-cycle transcript,
  reconnect timing, bridge status counters, host connection state, stale
  Gamepad API slot state, HID callback events, no-removal Windows pairing
  failure logs, and failure modes.
- Hardware/user action: likely required for Bluetooth UI and power/reset steps.
- Recommended next prompt type: return to controlled Windows BLE cache/bond
  lifecycle only after the single-persona Xbox product path has a real
  app/game data point or after a specific identity/bond fix exists.
- Risk: high, because BLE cache behavior is host-dependent.

## 4. Deadzone And Calibration Quality Tuning

- Why it matters: target-side labels are known, but product-quality feel and
  default deadzones are not proven.
- Evidence needed: raw and normalized ranges, jitter at rest, deadzone behavior,
  transformed report values, operator notes, and repeat runs for weak controls.
- Hardware/user action: required for controlled physical movements.
- Recommended next prompt type: calibration tuning plus focused target witness.
- Risk: medium, because tuning can improve one setup while hurting another.

## 5. Three-Separate-USB Flight Pack Investigation

- Why it matters: current evidence covers TFRP through TWCS RJ12, not separate
  stick/throttle/pedals USB devices.
- Evidence needed: USB topology, device identities, descriptor/report captures,
  normalized input catalog, mapping feasibility, and any bridge limitations.
- Hardware/user action: required to rewire and move controls.
- Recommended next prompt type: USB topology discovery and calibration witness.
- Risk: high, because hub bandwidth, descriptors, and device scheduling may
  differ from the RJ12 path.

## 6. Broader Host And Browser Matrix

- Why it matters: current host-visible evidence is narrow, mostly Chrome on
  macOS.
- Evidence needed: host OS/browser versions, active BLE compatibility variant,
  profile checker output, raw advertisement or scanner import when possible,
  BLE identity, Gamepad/API or app visibility, bridge counters,
  screenshots/logs, and explicit limitations for each host.
- Hardware/user action: likely required for pairing and permission prompts.
- Recommended next prompt type: BLE Compatibility Lab profile/scanner reset
  workflow, then one-host-at-a-time compatibility matrix witness.
- Risk: medium, because host stacks differ.

## 7. iPhone And iPad Compatibility Exploration

- Why it matters: mobile support is useful, but the first iPhone exploration
  failed at Bluetooth discovery while the target reported Generic BLE HID
  advertising. A follow-up diagnostic captured the target's intended Generic
  advertisement fields, and iPhone discovery still failed.
- Evidence needed: raw BLE advertisement capture from an independent scanner,
  an explicit experimental advertisement-layout variant, iOS/iPadOS version,
  pairing steps, browser/app target, visible input behavior if pairing
  succeeds, reconnect behavior if tested, and limitations.
- Hardware/user action: required for iPhone/iPad UI and pairing.
- Recommended next prompt type: add/test Apple/iOS experimental advertising
  variants after raw advertisement capture, then retry manual iPhone Safari
  witness only if the iPhone discovers a variant.
- Risk: high, because automation and BLE/gamepad visibility are constrained.

## 8. Witness Helper Library Refactor

- Why it matters: repeated serial probing, artifact writing, JSON summaries, and
  operator prompts make witness scripts harder to maintain.
- Evidence needed: no-hardware tests for shared helpers, unchanged witness
  behavior, and successful syntax/validation runs.
- Hardware/user action: none for the refactor itself.
- Recommended next prompt type: no-hardware tooling refactor chunk.
- Risk: low-medium, because witness scripts are evidence infrastructure and
  should be changed carefully.
