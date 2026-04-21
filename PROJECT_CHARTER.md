# USB2BLE Project Charter

## Mission

Build a professional, production-ready ESP32-S3 firmware system that:

1. ingests USB HID input devices over USB host,
2. ultimately supports **multiple USB HID devices through a powered USB-C hub**,
3. normalizes and composes those inputs into a stable internal model,
4. maps them to selectable BLE output personas,
5. and publishes them as a real, usable BLE controller on real hardware.

The project must optimize for:

- real-world usability,
- deterministic testability,
- clean crate boundaries,
- parallel development by multiple engineers or coding agents,
- and milestone-by-milestone hardware demonstrations.

## North-star product definition

At maturity, the system will:

- support hub-connected multi-device USB HID input ingestion,
- support device-specific and generic mapping profiles,
- map normalized input to either:
  - an arbitrary **BLE Generic Gamepad** output definition, or
  - an emulated **BLE Xbox Wireless controller** output,
- persist profile/configuration and bonding state,
- expose a stable control and diagnostics plane,
- and be demonstrable on ESP32-S3 hardware at every major phase.

## Release philosophy

This project will **not** attempt to ship all target functionality at once.

Instead, it will ship in layers:

- **Layer 1:** prove real hardware viability early,
- **Layer 2:** prove one end-to-end usable slice,
- **Layer 3:** expand to multi-device composition and richer personas,
- **Layer 4:** harden, optimize, and improve operator UX.

## Success criteria

This effort is successful only if all of the following are true:

1. The codebase is usable by another engineer without tribal knowledge.
2. Multiple agents can implement in parallel without changing each other's crates.
3. Every milestone has a real ESP32 hardware demo path.
4. The first supported end-to-end slice is actually usable, not merely log-driven.
5. Future hub / multi-device / persona expansion is enabled by the initial contracts.
6. The system remains testable in host replay mode even as embedded capability grows.

## Scope categories

### In scope from day one
- contract-first crate layout
- ESP32-S3 target
- USB host ingestion
- HID descriptor capture and parsing
- normalized input model
- mapping/profile system
- BLE persona encoding
- BLE transport abstraction
- persistence abstraction
- serial control plane
- host replay fixtures and deterministic tests
- milestone acceptance scripts and docs

### In scope for the overall product, but not required in the first demo
- powered USB-C hub topology
- multiple simultaneous USB HID devices
- composite input merge
- arbitrary generic gamepad mappings
- BLE Xbox Wireless persona
- richer configuration tooling

### Explicitly out of scope for the first repo milestone set
- universal support for all HID devices
- web UI as a dependency for core functionality
- dynamic generation of arbitrary HID personas at runtime
- support for every console-specific BLE persona
- cloud services

## Engineering principles

1. **Hardware truth beats simulation.**
   Host replay is required, but hardware demos are the source of truth.

2. **Contracts before implementation.**
   No major implementation begins until its contract surface is frozen in `CONTRACTS.md`.

3. **Unsafe code is quarantined.**
   All `unsafe` remains inside platform crates unless explicitly approved in the contract docs.

4. **Single responsibility by crate.**
   If a crate needs to know too much about another crate's internals, the boundary is wrong.

5. **Stable data model, replaceable platform glue.**
   Core crates must remain host-testable.

6. **Curated compatibility first.**
   Release 1 supports a curated list of devices and scenarios, not “all HID.”

7. **No invisible done.**
   Every feature must have a demo path, test evidence, and acceptance criteria.

8. **Optimize for coding agents.**
   Tasks must be narrow, bounded, and defined in terms of explicit files, traits, tests, and acceptance evidence.

## Delivery artifacts required in the new repo

At minimum, the new repo must include:

- `PROJECT_CHARTER.md`
- `FEATURES.md`
- `CONTRACTS.md`
- `MILESTONES.md`
- `AGENT_PROMPTS.md`
- `COMPATIBILITY_MATRIX.md`
- `ACCEPTANCE_CHECKLIST.md`

## Exact workspace / crate layout

```text
.
├── Cargo.toml
├── PROJECT_CHARTER.md
├── FEATURES.md
├── CONTRACTS.md
├── MILESTONES.md
├── AGENT_PROMPTS.md
├── COMPATIBILITY_MATRIX.md
├── ACCEPTANCE_CHECKLIST.md
├── docs/
│   ├── architecture/
│   ├── decisions/
│   ├── milestone-evidence/
│   └── fixtures/
├── fixtures/
│   ├── descriptors/
│   ├── replay/
│   ├── mappings/
│   └── personas/
├── scripts/
│   ├── build/
│   ├── flash/
│   ├── monitor/
│   ├── replay/
│   └── acceptance/
└── crates/
    ├── usb2ble-contracts
    ├── usb2ble-hid
    ├── usb2ble-input
    ├── usb2ble-mapping
    ├── usb2ble-personas
    ├── usb2ble-control
    ├── usb2ble-storage
    ├── usb2ble-platform-esp32
    ├── usb2ble-app
    ├── usb2ble-fw
    └── usb2ble-tools-replay
```

## Crate responsibilities

### `usb2ble-contracts`
The stable shared type/trait surface for the whole workspace.

Must contain:
- cross-crate IDs and enums,
- trait definitions,
- DTO-style event types,
- error taxonomies,
- contract version constants,
- invariants that other crates must obey.

Must **not** contain:
- ESP-IDF bindings,
- HID parser logic,
- persona-specific encoding logic,
- persistence implementation,
- application orchestration.

### `usb2ble-hid`
Responsible for:
- HID descriptor ingestion model,
- descriptor IR,
- HID descriptor parser,
- report decode helpers,
- capability extraction.

Must be pure and host-testable.

### `usb2ble-input`
Responsible for:
- normalized control model,
- source-device-aware input frames,
- composite input state,
- merge/composition policy primitives,
- normalization helpers.

Must not know BLE transport details.

### `usb2ble-mapping`
Responsible for:
- profile selection,
- mapping tables,
- device signatures,
- quirks registry,
- source-to-normalized and normalized-to-persona mapping logic.

Must not talk directly to ESP-IDF or NVS.

### `usb2ble-personas`
Responsible for:
- persona definitions,
- BLE report maps,
- encoders,
- output schema validation,
- Generic Gamepad and Xbox persona models.

Must not know USB host specifics.

### `usb2ble-control`
Responsible for:
- serial control-plane protocol,
- command/response framing,
- schema validation,
- diagnostics streaming model.

Must not own application state.

### `usb2ble-storage`
Responsible for:
- profile persistence traits,
- bond persistence traits,
- config persistence traits,
- host-memory implementations for testing.

Must not depend on ESP-IDF directly.

### `usb2ble-platform-esp32`
Responsible for:
- ESP-IDF bindings,
- USB host driver glue,
- BLE stack glue,
- UART/NVS adapters,
- all embedded `unsafe`.

Must implement the contracts, not redefine them.

### `usb2ble-app`
Responsible for:
- orchestration,
- application state machine,
- coordination among USB, parser, mapping, personas, BLE, storage, and control,
- milestone-level app behavior.

Must not include raw ESP-IDF details.

### `usb2ble-fw`
Thin firmware entrypoint crate.
Responsible for:
- boot,
- wiring concrete implementations,
- startup banner,
- main loop/task bootstrap,
- target-specific feature flags.

### `usb2ble-tools-replay`
Responsible for:
- deterministic replay tools,
- fixture runners,
- host-side milestone checks,
- fixture generation/inspection tools.

## Boundary rules

These are mandatory.

- `usb2ble-platform-esp32` may depend on `usb2ble-contracts`, `usb2ble-control`, `usb2ble-storage`, `usb2ble-personas` interfaces, and other pure crates as needed.
- `usb2ble-hid`, `usb2ble-input`, `usb2ble-mapping`, `usb2ble-personas`, `usb2ble-control`, and `usb2ble-storage` must remain host-testable and must not import ESP-IDF crates.
- `usb2ble-app` may depend on all pure crates plus the contract traits; it must not depend on ESP-IDF symbols directly.
- `usb2ble-fw` is allowed to wire concrete platform implementations into `usb2ble-app`.
- No crate may reach into another crate’s private modules to bypass a trait boundary.

## Implementation policy for agents

Any coding agent working under this charter must:

1. only modify the crates/files explicitly assigned,
2. not redefine contract types locally,
3. not widen scope beyond the assigned milestone,
4. add tests for every new public behavior,
5. preserve host replay support,
6. include acceptance evidence in the PR description or task output,
7. avoid speculative abstractions that are not tied to a listed milestone.

## Definition of done

A task is only done when it includes:

- code changes,
- tests,
- documentation updates if public behavior changed,
- a short evidence section showing how acceptance was validated,
- and no contract boundary violations.

## Priority ordering

The order of priorities is:

1. hardware viability,
2. correctness,
3. observability,
4. contract stability,
5. extensibility,
6. performance,
7. UX polish.

## Required future-aware decisions

Even in the earliest demo milestones, the following must already be reflected in the contract design:

- multiple HID devices can exist simultaneously,
- USB topology can include a powered USB-C hub,
- mappings cannot be hardcoded to a single joystick,
- the output layer must support more than one persona family,
- Generic Gamepad and Xbox outputs are first-class target concepts,
- device/profile selection must be data-driven where practical.

## Final instruction to implementers

Do not optimize the early repo around the smallest possible demo if doing so creates a dead-end for:
- multi-device hub support,
- arbitrary mapping,
- or multiple BLE personas.

The first demo may be small.
The architecture may not be small-minded.
