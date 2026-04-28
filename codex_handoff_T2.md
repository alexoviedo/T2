# T2 / USB2BLE — Codex Handoff

## 1) What this project is

This repo is the contract-first rebuild of the old USBLERST effort.

Mission:
- ESP32-S3 firmware
- USB HID input over USB host
- eventual support for **multiple USB HID devices through a powered USB-C hub**
- normalized internal input model
- mapping to selectable BLE output personas
- eventual support for both:
  - Generic BLE Gamepad output
  - BLE Xbox Wireless controller output
- milestone-by-milestone hardware demonstrations
- host-testable pure crates and reproducible CI

The architecture is intentionally split into pure crates and platform crates so multiple agents can work in parallel.

## 2) Current repo state on `main`

### Workspace and repo shape
The workspace already contains the expected crate layout:
- `usb2ble-contracts`
- `usb2ble-hid`
- `usb2ble-input`
- `usb2ble-mapping`
- `usb2ble-personas`
- `usb2ble-control`
- `usb2ble-storage`
- `usb2ble-platform-esp32`
- `usb2ble-app`
- `usb2ble-fw`
- `usb2ble-tools-replay`

### Milestone status
Treat the current state as:
- M0: complete
- M1: complete
- M2A: complete
- M2B.1: **code-path implemented, hardware verification still pending**
- M2B.2+: not complete

Do **not** treat M2B.1 as finished until there is checked-in, reproducible hardware evidence.

### Current firmware/runtime state
The firmware currently:
- boots
- initializes UART and USB ingress
- exposes serial control-plane commands
- services USB events in the main loop
- emits a startup banner

Current control-plane commands already include:
- `GET_INFO`
- `GET_STATUS`
- `GET_PROFILE`
- `GET_USB_STATUS`
- `LIST_USB_DEVICES`
- `GET_USB_DESCRIPTOR`
- `GET_LAST_USB_REPORT`

### Current USB host state
The USB host code currently has groundwork for:
- target-side `usb_host_install()` / client registration
- scanning enumerated devices
- attach/detach witness
- VID/PID reporting
- HID interface discovery from active config descriptor

Descriptor capture and input report capture are **not** complete yet.
Hub traversal was being worked on and appears to have caused version thrash.

## 3) The two biggest repo problems right now

These must be treated as likely regressions from Antigravity until proven otherwise.

### Problem A — hardcoded `IDF_PATH` to a local `master` checkout
`.cargo/config.toml` currently contains a checked-in absolute local path:

- `IDF_PATH = "/Users/alex/Developer/T2/T2/.embuild/espressif/esp-idf/master"`

This is a reproducibility bug.
It is hostile to:
- CI
- other machines
- local reproducibility after path changes
- version pinning discipline

It also forces use of a `master` checkout when the project should be using a deliberate, supported release.

### Problem B — stale experimental-hub configuration
`sdkconfig.defaults` currently contains:
- `CONFIG_IDF_EXPERIMENTAL_FEATURES=y`
- comment claiming experimental features are required for v5.3 hub traversal
- `CONFIG_USB_HOST_EXT_HUB_SUPPORT=y`
- `CONFIG_USB_HOST_HUBS_SUPPORTED=y`

This looks like the repo got dragged into an outdated experimental path.
The current stable ESP-IDF USB Host docs for ESP32-S3 document hub support via stable hub-related config options. The project should not carry experimental switches unless they are truly required and justified by current upstream behavior.

## 4) Recommended platform/toolchain strategy

### Decision
**Pin the project to ESP-IDF `v5.5.3` and stay on `esp-idf-sys` `0.37.x`.**

### Why this is the best compromise
1. ESP-IDF stable docs for ESP32-S3 explicitly document hub support via:
   - `CONFIG_USB_HOST_HUBS_SUPPORTED`
   - `CONFIG_USB_HOST_HUB_MULTI_LEVEL`
   - downstream-port timing options
2. `esp-idf-sys 0.37.x` explicitly added compatibility with ESP-IDF `v5.4.x` and `v5.5.x` and deprecated support for releases `< 5.3.0`.
3. The repo is already on `esp-idf-sys = "0.37"`, so staying on that line is aligned with current Rust bindings.
4. ESP-IDF `v6.0.x` also documents hub support, but current `esp-idf-sys 0.37.x` documentation does **not** explicitly claim `v6.0.x` compatibility. Moving to `6.0` would increase integration risk right when the project needs stability.
5. Using `master` is explicitly the wrong move for a production-oriented hardware project unless a missing must-have feature exists only there and there is no stable alternative.

### What not to do
- Do **not** keep using `IDF_PATH` pointing to a local `master` checkout.
- Do **not** chase ESP-IDF `master`.
- Do **not** jump to `v6.0.x` unless `v5.5.3` is proven insufficient for the required hub scenario.
- Do **not** keep `CONFIG_IDF_EXPERIMENTAL_FEATURES=y` unless you can prove with current upstream docs/code that it is actually required for the exact S3 hub path you need.

## 5) Exact build-system direction Codex should enforce

### Version pinning
The project should pin ESP-IDF **deliberately** through `esp-idf-sys` configuration, not through a checked-in absolute path.

Target approach:
- keep `ESP_IDF_SYS_ROOT_CRATE = "usb2ble-fw"`
- add `[package.metadata.esp-idf-sys]` to `crates/usb2ble-fw/Cargo.toml`
- set:
  - `esp_idf_version = "v5.5.3"`
  - `esp_idf_tools_install_dir = "workspace"`
- remove checked-in `IDF_PATH` from `.cargo/config.toml`

If a local override is needed for debugging, it must be:
- uncommitted, or
- opt-in through developer-local environment variables, not repo defaults

### Local build direction
Preferred local flow:
1. install toolchain with `espup install`
2. source `export-esp.sh`
3. use `cargo +esp build -Z build-std=std,panic_abort --target xtensa-esp32s3-espidf`
4. use `espflash` / `cargo espflash` for flash and monitor

### CI direction
CI should continue to validate the xtensa target build, but it must do so using the same pinned release and with no dependence on any absolute local path.

That means:
- no `IDF_PATH` hardcoded in the repo
- no reliance on a local clone of `master`
- CI and local should resolve the same IDF version by default

## 6) What Codex should do first

This is the priority order.

### Priority 1 — stabilize the build foundation
Codex should first clean up the build/toolchain/config state before doing any more USB feature work.

#### Required tasks
1. audit all repo references to:
   - `IDF_PATH`
   - `ESP_IDF_VERSION`
   - `CONFIG_IDF_EXPERIMENTAL_FEATURES`
   - hub-related config options
   - any references to `master`
2. remove or neutralize checked-in absolute-path / `master` assumptions
3. pin ESP-IDF to `v5.5.3`
4. keep `esp-idf-sys` on the `0.37.x` line
5. make sure local build + CI target build use the same version by default
6. update docs/scripts so the intended build path is explicit and reproducible

### Priority 2 — re-prove M2B.1 on real hardware
Once the toolchain is stabilized, Codex should complete the actual milestone proof that is still missing.

#### Required hardware proof for M2B.1
Checked-in evidence must include:
- board model
- exact powered hub used
- exact HID device(s) used
- connection topology
- build command
- flash command
- monitor command
- boot transcript
- `GET_USB_STATUS` before plug
- `LIST_USB_DEVICES` before plug
- attach transcript after plug
- `GET_USB_STATUS` after plug
- `LIST_USB_DEVICES` after plug
- detach transcript after unplug
- post-unplug status transcript

### Priority 3 — only then move to M2B.2
After M2B.1 is real and documented, proceed to descriptor/report capture.

Do **not** start M3 or BLE work yet.

## 7) What Codex should specifically investigate about hub traversal

Hub traversal on ESP32-S3 is not just “does the hub enumerate.”
Codex needs to explicitly verify:

1. whether `CONFIG_USB_HOST_HUBS_SUPPORTED` alone is enough on `v5.5.3`
2. whether `CONFIG_USB_HOST_HUB_MULTI_LEVEL` is needed for the actual hub topology being tested
3. whether `CONFIG_USB_HOST_EXT_PORT_CUSTOM_POWER_ON_DELAY_ENABLE`
   and `CONFIG_USB_HOST_EXT_PORT_CUSTOM_POWER_ON_DELAY_MS`
   need tuning for the chosen powered hub
4. whether `CONFIG_USB_HOST_EXT_PORT_RESET_RECOVERY_DELAY_MS` needs tuning
5. whether channel pressure is the real failure mode (ESP32-S3 supports 8 host channels)
6. whether the failure is in:
   - enumeration,
   - device-open,
   - config descriptor retrieval,
   - interface discovery,
   - or app bookkeeping

Codex should not keep changing ESP-IDF versions until it has ruled out timing/config/channel problems on a pinned stable version.

## 8) Rules Codex must obey

1. Do not rewrite milestone definitions.
2. Do not widen scope beyond the current milestone.
3. Do not start BLE persona work.
4. Do not start HID parser / normalization work unless M2B.1 is fully proven and the next task explicitly requests M2B.2.
5. Do not leave any checked-in absolute local paths.
6. Do not pin to `master` or an experimental branch unless there is a documented, validated blocker on `v5.5.3`.
7. Do not claim hub support is working without checked-in hardware evidence.
8. Keep pure crates host-testable.
9. Keep ESP-IDF-specific logic quarantined in `usb2ble-platform-esp32` and `usb2ble-fw`.
10. Do not silently change contracts; if a contract change is required, explain it explicitly.

## 9) Local environment assumptions for Codex

Codex can assume:
- it is running locally with repo access
- it can inspect the entire local environment
- the ESP32 is attached over USB
- it can run local commands
- it can build, flash, and monitor
- it can inspect the current checked-out repo state, not just GitHub

Codex should still prefer careful, reversible steps because build/toolchain changes are high-risk.

Recommended Codex operating style:
- use a cautious approval mode for toolchain/config work
- use high-approval / review for destructive changes
- stage build-system stabilization separately from feature work
- commit in small checkpoints

## 10) Concrete success criteria for the next Codex session

Codex’s next session is successful only if it produces all of the following:

### Build / toolchain success
- no checked-in absolute `IDF_PATH`
- no checked-in dependency on a local `master` clone
- project pinned to ESP-IDF `v5.5.3`
- local target build works
- CI target build path remains viable

### M2B.1 success
- direct-attach witness proven on real hardware
- hub-attached witness either proven or clearly characterized
- checked-in milestone evidence added
- compatibility matrix updated honestly
- acceptance checklist updated honestly

### Decision outcome
At the end of the session, Codex must leave the repo in one of these two states:
1. **Stable path proven on `v5.5.3`**, with evidence and next step M2B.2 clearly defined, or
2. **Pinned `v5.5.3` shown insufficient with concrete evidence**, plus a narrow, justified proposal for the smallest upgrade needed

What is not acceptable:
- “we tried a bunch of versions”
- “it works on my machine with `IDF_PATH` to master”
- “CI probably still works”
- “hub support seems flaky but let’s move on”

## 11) Copy/paste prompt for Codex

```text
You are taking over local implementation of repo `T2` / USB2BLE.

You have access to the full local environment, including the attached ESP32 over USB.
You are running locally, not in a constrained cloud PR-only environment.

Your job is NOT to continue version thrash.
Your first job is to stabilize the ESP-IDF/Rust build foundation and then honestly complete M2B.1 hardware verification.

Read these files first:
- PROJECT_CHARTER.md
- FEATURES.md
- CONTRACTS.md
- MILESTONES.md
- ACCEPTANCE_CHECKLIST.md
- COMPATIBILITY_MATRIX.md
- .cargo/config.toml
- sdkconfig.defaults
- crates/usb2ble-fw/Cargo.toml
- crates/usb2ble-platform-esp32/Cargo.toml
- crates/usb2ble-fw/src/main.rs
- crates/usb2ble-platform-esp32/src/lib.rs
- crates/usb2ble-platform-esp32/src/usb_host.rs
- scripts/build.sh
- scripts/flash.sh
- scripts/monitor.sh
- scripts/check_target_build.sh

## What I believe is wrong right now
- the repo appears to have a checked-in absolute `IDF_PATH` pointing to a local ESP-IDF `master` checkout
- `sdkconfig.defaults` still contains `CONFIG_IDF_EXPERIMENTAL_FEATURES=y` and comments implying old experimental hub traversal requirements
- Antigravity likely thrashed between ESP-IDF versions while trying to get hub traversal working

## Your top-level objective
Reach a stable, reproducible state that supports:
- local ESP32-S3 target builds
- GitHub Actions target builds
- continued work on USB host + hub traversal

without relying on:
- checked-in absolute local paths
- ESP-IDF `master`
- unjustified experimental flags

## Recommended baseline
Unless you find concrete evidence that it does not work, standardize on:
- `esp-idf-sys` `0.37.x`
- ESP-IDF `v5.5.3`

Reason:
- ESP-IDF stable docs for ESP32-S3 document hub support with stable hub config options
- `esp-idf-sys 0.37.x` explicitly supports ESP-IDF `v5.4.x` and `v5.5.x`
- current repo already depends on `esp-idf-sys = "0.37"`
- `v6.0.x` may be viable later, but it is not the safest current baseline for this repo

## Required task order

### Phase 1 — audit and stabilize build configuration
1. inspect all references to `IDF_PATH`, `ESP_IDF_VERSION`, `master`, and experimental hub flags
2. remove checked-in absolute-path assumptions
3. pin the project to ESP-IDF `v5.5.3` using the proper `esp-idf-sys` root-crate configuration path
4. keep tool installation reproducible and workspace-local where practical
5. make sure local build and CI build resolve the same ESP-IDF version by default
6. update docs/scripts if needed

Important:
- do not make speculative changes first
- explain exactly what you changed and why
- prefer metadata pinning over developer-specific environment hacks

### Phase 2 — prove M2B.1 on hardware
After the build foundation is stable:
1. build locally for `xtensa-esp32s3-espidf`
2. flash the ESP32
3. capture a real boot transcript
4. verify direct-attach USB witness on real hardware
5. test via powered hub
6. characterize failures precisely if the hub path is still failing
7. check in milestone evidence
8. update `ACCEPTANCE_CHECKLIST.md` and `COMPATIBILITY_MATRIX.md` honestly

## Hub-traversal investigation requirements
Do not change ESP-IDF versions again until you have checked whether the real issue is one of:
- missing or wrong stable hub config options
- downstream-port timing
- reset recovery timing
- host-channel exhaustion
- descriptor/config retrieval logic
- app bookkeeping bugs

Specifically investigate whether these stable config options are sufficient on the chosen baseline:
- `CONFIG_USB_HOST_HUBS_SUPPORTED`
- `CONFIG_USB_HOST_HUB_MULTI_LEVEL`
- `CONFIG_USB_HOST_EXT_PORT_CUSTOM_POWER_ON_DELAY_ENABLE`
- `CONFIG_USB_HOST_EXT_PORT_CUSTOM_POWER_ON_DELAY_MS`
- `CONFIG_USB_HOST_EXT_PORT_RESET_RECOVERY_DELAY_MS`

## Constraints
- Do not start M2B.2 until M2B.1 is truly proven.
- Do not start M3, M4, or BLE work.
- Do not keep `IDF_PATH` to a local master checkout in committed repo config.
- Do not keep `CONFIG_IDF_EXPERIMENTAL_FEATURES=y` unless you can justify it with current upstream requirements.
- Do not claim success without real hardware evidence.
- Do not widen scope.

## Deliverables
At the end of your run, provide:
1. exact files changed
2. exact config/toolchain decisions made
3. exact local build command used
4. exact flash/monitor commands used
5. exact hardware used (board, hub, HID device)
6. direct-attach results
7. hub-attached results
8. whether M2B.1 is now complete
9. what the next milestone should be

If `v5.5.3` truly cannot support the required hub path in this repo, stop and provide a tightly scoped upgrade rationale instead of thrashing across versions.
```

## 12) Optional follow-up task after the first Codex session

Only after the above is complete:
- implement M2B.2 descriptor capture and last-report capture through the control plane
- keep the same version pin
- do not touch BLE yet

