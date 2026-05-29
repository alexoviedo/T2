# Post-Alpha Plan

This queue keeps post-`v0.1.0-alpha` work evidence-backed and scoped. It does
not create new compatibility claims; each item defines the evidence needed
before status docs should change.

## 1. External Browser Or Native Game Compatibility Data Point

- Why it matters: proves USB2BLE works in a real third-party app/game surface,
  not only the repo-local browser app smoke.
- Evidence needed: app/game name and version, host OS/browser, active persona,
  bridge counter deltas, screenshots or app logs showing recognized controls,
  orientation notes, and limitations.
- Hardware/user action: likely required for pairing, app focus, and physical
  control movements.
- Recommended next prompt type: hardware/browser witness chunk following
  `docs/GAME_COMPATIBILITY_WITNESS.md`.
- Risk: medium, because app input handling varies widely.

## 2. Xbox Standard Button Layout And Refined Live Mapping

- Why it matters: the refined Xbox mapping is target-side proven, and a
  deterministic macOS/Chrome diagnostic now shows `mapping="standard"` with
  expected standard stick, trigger, D-pad, A, and B movement. Several other
  button positions did not match, and refined live Flight Pack host movement is
  still not proven.
- Evidence needed: determine whether the X/Y/LB/RB/View/Menu mismatch comes from
  report-map button ordering, macOS/Chrome remapping, or witness expectations;
  then capture persisted Xbox config, host-visible trigger and stick movement,
  serial report bytes, bridge counters, browser samples, and limitations. A
  literal Xbox-like browser `id` is useful context but should not be treated as
  the sole success criterion.
- Hardware/user action: likely required for BLE pairing and physical controls.
- Recommended next prompt type: Xbox standard button-layout correction chunk,
  followed by a focused refined Xbox Flight Pack live-bridge witness for rudder
  and toe brakes.
- Risk: medium-high, because host Xbox HID handling and pairing state can be
  sticky.

## 3. BLE Bond And Reconnect Persistence

- Why it matters: early adopters need to know whether reconnect behavior is
  reliable across resets, power cycles, and host Bluetooth cache states.
- Evidence needed: before/after bond state, reboot/power-cycle transcript,
  reconnect timing, bridge status counters, host connection state, and failure
  modes.
- Hardware/user action: likely required for Bluetooth UI and power/reset steps.
- Recommended next prompt type: reconnect/bond persistence witness chunk.
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
