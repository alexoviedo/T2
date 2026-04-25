# Milestone-by-Milestone Acceptance Criteria

Each milestone must be:
- implementable by an independent coding agent,
- demonstrable on real hardware where indicated,
- and validated with host-side replay or unit tests where applicable.

---

## M0 — Repo skeleton, contracts, and build discipline

### Goal
Create the new repo with the full crate layout, frozen contract surfaces, and a build/test harness that other agents can safely target.

### Scope
- workspace skeleton
- crate creation
- lint policy
- `PROJECT_CHARTER.md`, `FEATURES.md`, `CONTRACTS.md`, `MILESTONES.md`
- memory-backed trait implementations
- placeholder host tests
- CI scaffolding

### Deliverables
- repo skeleton compiles
- contracts crate defined
- all pure crates compile on host
- CI runs host tests

### Acceptance criteria
- `cargo test --workspace` passes for host-supported crates
- crate dependency graph follows charter
- no ESP-IDF symbols outside platform/fw crates
- docs are present and internally consistent

### Demo
- host-only: workspace builds and tests cleanly

### Parallelization after completion
- all downstream milestone work may begin once contracts are accepted

---

## M1 — Boot, serial control plane, and operator witness

### Goal
Boot firmware on ESP32-S3 and prove the system is alive, inspectable, and controllable before USB/BLE complexity is added.

### Scope
- firmware entrypoint
- startup banner
- serial framing
- `GET_INFO`, `GET_STATUS`, `GET_PROFILE`
- memory-backed or stub-backed app state on target
- scripted build/flash/monitor flow

### Deliverables
- real board boots
- serial commands round-trip
- active profile / persona / BLE state visible

### Acceptance criteria
- clean flash and monitor instructions work on a clean machine
- board prints startup banner within expected boot flow
- `GET_INFO` returns contract version, firmware identity, and persona info
- `GET_STATUS` returns BLE/link/profile/bond summary
- host replay tests for control-plane framing pass

### Hardware demo
1. Flash firmware to ESP32-S3
2. Open serial monitor
3. Observe startup banner
4. Send `GET_INFO`
5. Send `GET_STATUS`
6. Receive valid responses

### Notes
This milestone intentionally proves operator visibility before device functionality.

---

## M2 — USB witness on real hardware

### M2A (Complete)
Groundwork complete: contracts, app bookkeeping, control-plane USB visibility, and platform plumbing.

### M2B.1 (Code-path implemented, hardware verification pending)
Real attach/detach + identity witness plumbing on ESP32-S3; on-device evidence still required.

### M2B.2 (Pending)
Descriptor and input-report capture exposed through control plane.

> Review note for current PR scope: only M2B.1 code-path work (attach/detach + identity witness)
> is in scope; descriptor/report capture remains deferred to M2B.2.

### Goal
Prove real USB host viability on ESP32-S3 with curated supported hardware.

### Scope
- USB host init
- device attach/detach events
- VID/PID reporting
- interface discovery
- descriptor receipt plumbing
- raw input report receipt plumbing
- diagnostics for USB events

### Deliverables
- USB ingress trait implemented on target
- attach/detach logs
- descriptor and input packets visible

### Acceptance criteria
- attach event includes stable `DeviceId`, topology, VID, and PID
- detach event is clean and resets source state
- descriptor receipt can be observed and dumped
- input reports are visible as raw packets
- host replay fixture model matches target event shapes

### Hardware demo
1. Boot firmware
2. Plug supported USB HID device directly into ESP32-S3 host path
3. Observe attach event
4. Observe descriptor received event
5. Generate input by moving control/button
6. Observe raw input packets
7. Unplug device and observe detach

### Future-aware requirement
Contracts used here must already include topology support for future powered USB-C hub scenarios.

---

## M3 — HID descriptor IR and hardware/host parity

### Goal
Convert raw descriptors into a stable parsed capability model and prove host/device parity.

### Scope
- descriptor parser
- IR definitions
- capability extraction
- descriptor summary diagnostics
- hardware-captured descriptor fixtures
- parity tests

### Deliverables
- parser crate working on host
- descriptor summaries available in diagnostics
- replay fixtures built from hardware captures

### Acceptance criteria
- same descriptor bytes produce same IR on host and device
- at least one curated supported device has a committed descriptor fixture
- capability summary includes axes/buttons/hats/report IDs
- parse failures are surfaced as typed errors, not silent ignores

### Hardware demo
1. Connect curated device
2. Request descriptor summary over control plane
3. Compare with host replay output for same descriptor blob

### Parallelization after completion
- input normalization and mapping work can proceed independently
- persona work can proceed independently

---

## M4 — Live normalized input on hardware

### Goal
Turn real HID input into a stable normalized model that can be inspected live on hardware.

### Scope
- HID report decode
- normalization to internal control model
- live diagnostics of normalized state
- source identity retained in normalized frames
- detach recovery for normalized state

### Deliverables
- `usb2ble-hid` decode path
- `usb2ble-input` normalized model
- app integration for one curated device

### Acceptance criteria
- moving a real control updates normalized state in predictable form
- button presses, axes, and hat values are visible in diagnostics
- device detach removes stale contributed state
- host replay and hardware behavior match for committed fixtures

### Hardware demo
1. Connect curated device
2. Request live normalized diagnostics stream
3. Move axes / press buttons
4. Observe normalized events
5. Unplug device
6. Observe normalized state cleanup

### Important note
This is the earliest milestone where real-world usability starts to matter materially.

---

## M5 — BLE persona self-test without USB dependency

### Goal
Prove real BLE transport end-to-end using synthetic input injection before full USB-to-BLE integration.

### Scope
- BLE transport initialization
- Generic BLE Gamepad persona descriptor
- persona activation
- synthetic normalized input injection through control plane
- host-visible BLE input updates
- bond clear command

### Deliverables
- real BLE advertising/connect path
- real Generic BLE Gamepad persona on hardware
- self-test input injection path

### Acceptance criteria
- host can discover and connect to device
- synthetic input injection produces host-visible control changes
- disconnect/reconnect path works in the supported scenario
- `FORGET_BONDS` clears bond state

### Hardware demo
1. Boot firmware with no USB device attached
2. Put board into BLE advertising mode
3. Connect from host
4. Use control plane to inject test input
5. Observe input on host gamepad viewer
6. Clear bonds and verify state resets

### Reason for milestone
This isolates BLE transport risk from USB/HID complexity.

---

## M6 — First end-to-end usable slice

### Goal
Deliver the first actually usable bridge path:
one curated USB HID device -> normalization -> mapping -> Generic BLE Gamepad persona.

### Scope
- device signature selection
- first mapping profile
- app pipeline integration
- BLE publish from real USB input
- reconnect-safe supported path
- compatibility matrix entry for first device

### Deliverables
- first curated device officially supported end-to-end
- mapping profile fixture
- end-to-end acceptance script

### Acceptance criteria
- with one curated supported device, live input is visible on host through BLE
- demo works for more than a trivial momentary interaction
- disconnect and reconnect recover cleanly in the supported path
- no manual code edits required between runs
- compatibility matrix updated to “supported” for the exact tested path

### Hardware demo
1. Boot firmware
2. Connect curated USB device
3. Connect host to BLE persona
4. Move device controls
5. Observe host-visible controls
6. Disconnect/reconnect BLE and verify continued function

### Release gate
This is the first milestone that counts as a usable product slice.

---

## M7 — Persistence and session recovery

### Goal
Make the first usable slice feel durable and product-like.

### Scope
- active profile persistence
- config persistence baseline
- bond persistence validation
- reboot recovery
- status reporting improvements

### Deliverables
- persisted active profile
- persisted bond state
- reboot-safe startup behavior

### Acceptance criteria
- set profile, reboot, verify profile persists
- connect and bond, reboot, verify reconnect path in supported scenario
- status output reflects persisted state correctly
- no corrupted or partial state after detach/reboot in tested scenarios

### Hardware demo
1. Set active profile
2. Reboot
3. Verify active profile after boot
4. Bond BLE host
5. Reboot
6. Verify reconnect behavior

---

## M8 — Hub-aware multi-device enumeration

### Goal
Prove that the architecture is not trapped in single-device assumptions.

### Scope
- topology-aware USB events on hardware
- multiple simultaneous device tracking in app state
- enumeration through powered USB-C hub
- per-source diagnostics

### Deliverables
- app tracks more than one connected source
- USB events include topology/source identity
- compatibility matrix includes tested hub scenario

### Acceptance criteria
- at least two devices can be observed concurrently through a powered USB-C hub
- each device has unique source identity
- attach/detach of one device does not corrupt the other device’s state
- app state and diagnostics show multiple known devices

### Hardware demo
1. Connect powered USB-C hub
2. Attach two curated HID devices
3. Observe both enumerate
4. Generate input from both
5. Detach one
6. Verify the other remains present

### Important note
This milestone may still route only one device into active BLE output depending on mapping scope, but enumeration and state model must be truly multi-device.

---

## M9 — Composite mapping and multi-device merge

### Goal
Support intentional composition of multiple USB HID sources into one logical output.

### Scope
- composite profile definition
- merge policy engine
- per-source-to-composite mapping
- detach recovery within composite scenarios

### Deliverables
- at least one composite mapping profile
- deterministic merge tests
- composite diagnostics

### Acceptance criteria
- two curated devices can contribute to one logical output state
- merge behavior is deterministic and fixture-backed
- detaching one source degrades gracefully without full failure
- composite scenario works through powered USB-C hub

### Hardware demo
Example:
- joystick contributes stick axes
- pedals contribute rudder/brakes
- throttle contributes throttle inputs
- combined output appears as one BLE controller state

---

## M10 — Arbitrary Generic Gamepad mapping family

### Goal
Support more than one Generic BLE Gamepad output schema without rewriting core app logic.

### Scope
- persona registry expansion
- mapping-to-persona abstraction hardening
- at least two generic persona definitions
- configuration/profile selection of generic persona target

### Deliverables
- multiple generic persona descriptors
- encoder tests for each
- profile-level selection of target generic persona

### Acceptance criteria
- same normalized/composite input can target more than one generic persona definition
- BLE transport activation path works for each tested generic persona
- no USB or app crate rewrites required to add a new generic persona

---

## M11 — BLE Xbox Wireless persona

### Goal
Add BLE Xbox Wireless controller output as a formal target persona.

### Scope
- Xbox persona contract
- encoder implementation
- BLE transport integration as applicable
- compatibility and support notes
- milestone-specific risks documented

### Deliverables
- persona descriptor
- encoder tests
- explicit support status in compatibility matrix

### Acceptance criteria
- persona can be selected in the app model
- encoder and descriptor tests pass
- if transport is fully supported, host-visible demo exists
- if transport is not yet fully supported, milestone is not considered complete

### Caution
No agent may claim this milestone complete without real hardware evidence for the supported path.

---

## M12 — Hardening, observability, and operator UX

### Goal
Make the project professional and maintainable.

### Scope
- structured diagnostics
- error counters
- queue/publish metrics
- richer control plane
- docs cleanup
- acceptance automation
- clean-machine onboarding

### Deliverables
- production-style diagnostics surface
- troubleshooting docs
- acceptance checklist
- polished compatibility matrix

### Acceptance criteria
- operator can diagnose attach, parse, mapping, and BLE failures without code edits
- clean-machine onboarding works from docs
- milestone evidence directory is up to date
- project feels maintainable by a new engineer

---

# Milestone dependencies

```text
M0 -> M1 -> M2 -> M3 -> M4
M1 -> M5
M4 + M5 -> M6
M6 -> M7
M2 + M3 + M6 -> M8
M8 -> M9
M6 -> M10
M10 -> M11
M7 + M8 + M9 + M10 + M11 -> M12
```

# Acceptance evidence requirements for every milestone

Every milestone output must include:

1. What changed
2. Which crates/files changed
3. Which tests were added/updated
4. Exact command(s) used to validate
5. Host evidence
6. Hardware evidence if milestone requires it
7. Known limitations not covered by the milestone

# Agent execution policy

A coding agent implementing a milestone must not:

- skip ahead to future milestones,
- silently change contracts,
- claim “support” without acceptance evidence,
- or replace real milestone proof with logs that do not demonstrate user-visible behavior.

The first priority is always:
**make the milestone real, make it testable, and make it easy to verify.**
