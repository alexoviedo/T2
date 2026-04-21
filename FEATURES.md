# Exact Feature List

This document defines the feature backlog for the new repo.

Statuses:
- **R0** = required for the first usable release path
- **R1** = required for the planned product path after the first usable slice
- **R2** = important but not required for early product viability
- **NX** = explicitly not planned right now

---

## 1. Build, bootstrap, and operator basics

### F-001 Workspace builds on host
Priority: R0
Description:
- `cargo test` works on host-supported crates.
- replay/tooling crates run on host.
Acceptance:
- all non-ESP crates compile and test on CI.

### F-002 ESP32-S3 firmware builds reproducibly
Priority: R0
Description:
- one documented firmware target,
- one documented build command,
- one documented flash command,
- one documented monitor command.
Acceptance:
- clean-machine instructions work.

### F-003 Startup banner and version identity
Priority: R0
Description:
- firmware prints project name, git/version, active profile, BLE transport state, USB state.
Acceptance:
- visible on serial after boot.

### F-004 Stable serial control plane
Priority: R0
Description:
- newline-framed protocol for device info, status, profile/config, diagnostics, reboot/test hooks.
Acceptance:
- round-trip command/response on hardware and host replay.

---

## 2. USB host and topology

### F-010 USB device attach/detach witness
Priority: R0
Description:
- detect attach/detach on hardware,
- report VID/PID/basic interface information.
Acceptance:
- hardware demo logs attach and detach cleanly.

### F-011 HID descriptor capture
Priority: R0
Description:
- receive and store raw HID report descriptors from supported devices.
Acceptance:
- descriptor bytes visible via diagnostics and replay fixtures.

### F-012 HID input report capture
Priority: R0
Description:
- receive input reports with device identity, interface identity, report ID, and payload bytes.
Acceptance:
- hardware and host replay parity for sample fixtures.

### F-013 Hub-aware topology model
Priority: R1
Description:
- contracts must represent devices behind a powered USB-C hub,
- each input source must carry stable source identity and topology metadata.
Acceptance:
- contracts and platform model include hub path / parent path concept even before full multi-device merge ships.

### F-014 Multiple simultaneous HID devices
Priority: R1
Description:
- more than one HID source may be active at once.
Acceptance:
- app state can track multiple devices concurrently.

### F-015 Powered USB-C hub support
Priority: R1
Description:
- intended supported scenario includes a powered USB-C hub with multiple HID devices attached.
Acceptance:
- milestone evidence shows multi-device enumeration through hub for curated hardware.

### F-016 Interface and endpoint diagnostics
Priority: R1
Description:
- diagnostics show interfaces, endpoints, report lengths, and input transfer status.
Acceptance:
- queryable through control plane.

---

## 3. HID parsing and capability modeling

### F-020 Descriptor IR
Priority: R0
Description:
- stable intermediate representation for HID descriptors and fields.
Acceptance:
- parser output is snapshot-testable.

### F-021 Capability extraction
Priority: R0
Description:
- derive axes, buttons, hats, report IDs, ranges, and usage metadata from parsed descriptors.
Acceptance:
- capability summary available in replay and diagnostics.

### F-022 Report decode
Priority: R0
Description:
- decode incoming HID reports against descriptor IR.
Acceptance:
- deterministic fixtures with expected decoded outputs.

### F-023 Parser parity between host and hardware
Priority: R0
Description:
- the same descriptor bytes must yield the same parsed result on host and device.
Acceptance:
- parity tests and hardware evidence.

### F-024 Support for more than trivial report shapes
Priority: R1
Description:
- parser and decoder design must allow expanding past minimal v1 limitations.
Acceptance:
- contract model does not assume one report count, one device, or one field style.

### F-025 Quirk hooks
Priority: R1
Description:
- device-specific quirks can patch capability extraction or decode behavior in a controlled way.
Acceptance:
- quirks are registered declaratively and unit-tested.

---

## 4. Normalized input model

### F-030 Stable normalized control model
Priority: R0
Description:
- internal model for axes, buttons, hats, source identity, and timestamp.
Acceptance:
- pure tests validate deterministic normalization.

### F-031 Source-aware normalized frames
Priority: R0
Description:
- normalized events retain which USB source generated them.
Acceptance:
- contract type includes source reference.

### F-032 Composite input state
Priority: R1
Description:
- aggregate state can be composed from multiple devices.
Acceptance:
- app and input crates expose a composite state type.

### F-033 Merge policy engine
Priority: R1
Description:
- rules for how multiple devices contribute to one logical controller state.
Acceptance:
- deterministic merge tests for curated scenarios.

### F-034 Device detach recovery
Priority: R0
Description:
- when a device detaches, its contributed state is removed safely.
Acceptance:
- hardware and replay tests show correct reset/update behavior.

---

## 5. Mapping and profiles

### F-040 Device signature model
Priority: R0
Description:
- supported devices can be identified by VID/PID/interface/capability signature.
Acceptance:
- selection logic unit-tested.

### F-041 Data-driven mapping profiles
Priority: R0
Description:
- profiles describe how source capabilities map into normalized state and/or output persona.
Acceptance:
- profile fixtures load and validate.

### F-042 Curated first-device support
Priority: R0
Description:
- first supported device path is explicitly documented and tested.
Acceptance:
- one end-to-end supported hardware path works on ESP32.

### F-043 Multiple curated device profiles
Priority: R1
Description:
- support more than one device family without changing core crates.
Acceptance:
- adding a new profile does not require app-logic rewrites.

### F-044 Arbitrary generic gamepad mapping
Priority: R1
Description:
- normalized inputs can be mapped into any arbitrary Generic Gamepad output schema supported by persona definitions.
Acceptance:
- mapping config can target different generic layouts without rewriting transport code.

### F-045 Composite profile definitions
Priority: R1
Description:
- multiple USB sources can be intentionally combined into one logical output profile.
Acceptance:
- at least one composite profile example fixture.

### F-046 Runtime profile selection
Priority: R1
Description:
- profile may be selected automatically by signature and/or explicitly by operator command.
Acceptance:
- control plane can query/set active profile.

---

## 6. BLE personas and encoding

### F-050 Generic BLE Gamepad persona
Priority: R0
Description:
- one real BLE Generic Gamepad persona with stable report map and encoder.
Acceptance:
- actual host sees and receives input from ESP32.

### F-051 Persona descriptor registry
Priority: R0
Description:
- persona definitions are first-class objects with IDs, report maps, and encoders.
Acceptance:
- app can query persona metadata generically.

### F-052 Encoded report validation
Priority: R0
Description:
- every persona encoder has exact-wire tests.
Acceptance:
- snapshot tests for report bytes.

### F-053 Arbitrary Generic Gamepad output layouts
Priority: R1
Description:
- system can support multiple Generic Gamepad output schemas, not just one hardcoded layout.
Acceptance:
- at least two generic persona definitions compile and validate.

### F-054 BLE Xbox Wireless persona
Priority: R1
Description:
- system can emit an emulated BLE Xbox Wireless controller persona.
Acceptance:
- persona crate contains a formal persona contract and milestone plan; release evidence required before claiming supported.

### F-055 Persona self-test injection mode
Priority: R0
Description:
- inject synthetic normalized state into persona encoder + BLE transport without USB dependency.
Acceptance:
- hardware self-test demo drives host-visible BLE inputs.

---

## 7. BLE transport and connection lifecycle

### F-060 Real BLE advertising/connect/disconnect
Priority: R0
Description:
- embedded BLE transport advertises, connects, disconnects, and publishes input reports.
Acceptance:
- hardware demo with external host.

### F-061 BLE publish path independent from USB path
Priority: R0
Description:
- BLE transport can be proven via self-test without USB attached.
Acceptance:
- milestone acceptance includes BLE-only test.

### F-062 Bond persistence
Priority: R0
Description:
- bonds can be stored, queried, and cleared.
Acceptance:
- control plane exposes state and clear operation.

### F-063 Reconnect behavior
Priority: R1
Description:
- known host can reconnect predictably after reboot/disconnect.
Acceptance:
- hardware regression test.

### F-064 BLE diagnostics
Priority: R1
Description:
- advertising, connection, publish failures, and bond state visible through control plane/logging.
Acceptance:
- visible in diagnostics output.

---

## 8. Persistence and configuration

### F-070 Active profile persistence
Priority: R0
Description:
- selected profile persists across reboot.
Acceptance:
- set, reboot, verify.

### F-071 Config persistence
Priority: R1
Description:
- operator config persists across reboot.
Acceptance:
- stored and read back through control plane.

### F-072 Import/export friendly config model
Priority: R2
Description:
- config can be represented as data suitable for future tooling.
Acceptance:
- stable schema documented.

---

## 9. Replay, testing, and evidence

### F-080 Deterministic replay fixtures
Priority: R0
Description:
- attach/descriptor/input/detach sequences can be replayed deterministically on host.
Acceptance:
- fixture runner in CI.

### F-081 Hardware parity fixtures
Priority: R0
Description:
- hardware-captured descriptors and sample reports can be replayed on host.
Acceptance:
- parity evidence for curated devices.

### F-082 Acceptance scripts per milestone
Priority: R0
Description:
- every milestone has a scripted or checklist-based acceptance workflow.
Acceptance:
- script or checklist exists under `scripts/acceptance/`.

### F-083 Compatibility matrix
Priority: R0
Description:
- support status per device/persona/milestone is documented.
Acceptance:
- checked into repo.

### F-084 Performance and stability telemetry
Priority: R2
Description:
- counters/timings for dropped reports, queue depth, error counts, and publish cadence.
Acceptance:
- visible via diagnostics.

---

## 10. Tooling and future UX

### F-090 Web tooling compatibility
Priority: R2
Description:
- config/protocol choices should be future-compatible with a web tool, but core functionality must not depend on it.
Acceptance:
- control plane schema suitable for future UI.

### F-091 Firmware flashing workflow
Priority: R2
Description:
- scripted flashing required; future web flashing optional.
Acceptance:
- documented scripted flash path.

### F-092 Web flashing support
Priority: R2
Description:
- optional future feature, not required for first usable release.
Acceptance:
- deferred until explicit milestone.

---

## 11. Explicit non-features for now

### F-100 Universal HID support
Priority: NX
Description:
- do not promise all HID devices.

### F-101 Dynamic arbitrary runtime persona synthesis
Priority: NX
Description:
- personas are defined and validated intentionally, not synthesized freely at runtime.

### F-102 Cloud-managed control plane
Priority: NX
Description:
- no cloud dependency for basic product use.
