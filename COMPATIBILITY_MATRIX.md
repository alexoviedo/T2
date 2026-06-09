# Compatibility Matrix

This matrix tracks the support status for devices, personas, and milestones.

## Milestones

| Milestone | Status | Note | Evidence |
|-----------|--------|------|----------|
| M0 | Complete | Repo skeleton and contracts baseline | Host test evidence |
| M1 | Complete | Boot + serial control witness | Real target transcript (historical) |
| M2A | Complete | USB contracts/app/control groundwork | Host tests |
| M2B.1 | Partial hardware evidence | Hub attach/detach identity and HID-class discovery captured; direct attach blocked by cabling | `docs/milestone-evidence/M2B1_HUB_WITNESS_2026-04-28.md` |
| M2B.2 | Hardware evidence captured | HID report descriptor and raw input report capture via control-plane works for the T.16000 FCS HOTAS through the hub | `docs/milestone-evidence/M2B2_DESCRIPTOR_WITNESS_2026-04-29.md` |
| M3 | Summary hardware evidence captured | HID parser and capability summary work for the T.16000 FCS HOTAS descriptor on host and target | `docs/milestone-evidence/M3_HID_SUMMARY_WITNESS_2026-04-29.md` |
| M4 | Expanded hardware evidence captured | Normalized live-input diagnostics work for the T.16000 stick, TFRP pedals, TWCS throttle, and the RJ12 two-USB Flight Pack topology; practical RJ12 axis labels are witnessed; button/detach and simultaneous three-separate-USB streaming remain open | `docs/milestone-evidence/M4_NORMALIZED_INPUT_WITNESS_2026-04-29.md`; `docs/milestone-evidence/M4_FLIGHT_PACK_NORMALIZED_WITNESS_2026-04-29.md`; `docs/milestone-evidence/M4_RJ12_TWO_USB_FLIGHT_PACK_WITNESS_2026-04-29.md`; `docs/milestone-evidence/FLIGHT_PACK_CALIBRATION_WITNESS_2026-05-28.md` |
| M5 | Generic BLE self-test witnessed | Generic Gamepad BLE advertising, macOS pairing/input, and synthetic self-test input are witnessed. `FORGET_BLE_BONDS` exists as a command path, but bond-clear recovery and durable bond persistence are not proven. | `docs/milestone-evidence/BLE_HID_DEMO_CODEPATH_BUILD_WITNESS_2026-04-30.md`; `docs/milestone-evidence/BLE_HID_GENERIC_GAMEPAD_ADVERTISING_WITNESS_2026-04-30.md`; `docs/milestone-evidence/BLE_HID_MAC_PAIRING_INPUT_WITNESS_2026-04-30.md`; `docs/milestone-evidence/BROWSER_GAMEPAD_API_WITNESS_2026-04-30.md` |
| M6 | Demo bridge slice witnessed; formal hardening open | Generic Gamepad USB-derived BLE publish and explicit live bridge are witnessed through macOS/browser evidence; practical RJ12 Flight Pack target-side mapping refinement, host-visible Generic axis exposure, a refined Generic 300-second live bridge soak, and a self-hosted browser game/app smoke are witnessed; broad external/native game/app compatibility, reconnect hardening, and final calibration are not proven | `docs/milestone-evidence/FLIGHT_PACK_DEMO_BLE_BROWSER_WITNESS_2026-05-08.md`; `docs/milestone-evidence/ASAP_DEMO_REHEARSAL_WITNESS_2026-05-08.md`; `docs/milestone-evidence/LIVE_BRIDGE_WITNESS_2026-05-10.md`; `docs/milestone-evidence/FLIGHT_PACK_MAPPING_REFINEMENT_WITNESS_2026-05-28.md`; `docs/milestone-evidence/REFINED_GENERIC_AXIS_EXPOSURE_WITNESS_2026-05-28.md`; `docs/milestone-evidence/REFINED_GENERIC_LIVE_BRIDGE_SOAK_WITNESS_2026-05-28.md`; `docs/milestone-evidence/GAME_COMPATIBILITY_WITNESS_2026-05-28_SELF_HOSTED_SKY_RUN.md` |
| M11 | Xbox persona slice witnessed; broad compatibility open | Xbox report encoding, BLE identity/report publishing, earlier macOS/browser VID/PID support, and Xbox live bridge/soak evidence exist; Xbox BLE Profile v1 adds target-side model-1914 profile/report-map diagnostics and checker evidence. A deterministic macOS/Chrome diagnostic reached target BLE `Connected`; Chrome exposed `Xbox Wireless Controller (STANDARD GAMEPAD)` with `mapping="standard"` and expected standard stick, trigger, D-pad, A/B/X/Y, LB/RB, View, and Menu movement. Stick-press buttons did not surface at B10/B11. Virtual normalized-input replay proves refined Flight Pack Xbox stick/rudder/toe mappings can drive Chrome standard controls through the live bridge. Windows single-persona Xbox evidence now shows `Xbox Wireless Controller` pairing, HID `045e:0b13`, XInput slot 0 deterministic reports, virtual Flight Pack Xbox mapping through XInput, and `joy.cpl` controller-panel movement on Alex's PC. A follow-up Windows Spyro Reignited Trilogy witness adds one installed-game data point for the same Xbox path: XInput stayed connected while virtual Xbox mapping and deterministic reports ran, and Alex observed controls moving plus menu items being selected in Spyro. The first reconnect diagnostic captured a reset/report-delivery failure; the 2026-06-09 reconnect/report-delivery fix diagnostic adds `STOP_BLE_PERSONA`, connection/bond diagnostics, and shows stop/start plus soft reset with explicit Xbox persona/strategy reapply restored XInput report delivery without Windows cache cleanup. Direct host disconnect, runtime persona/identity persistence, durable bond persistence, and power-cycle behavior remain unproven. Generic virtual replay diagnostics show stale-slot rejection, temporary Chrome profile exposure, and lower-level HID delivery separation: target Generic mapping/report and bridge publication are healthy, X/Y/Z/Rx positive-side changes reach macOS HID/Chrome, and Ry/Rz plus one negative Rx path currently fail below Chrome at the macOS HID callback layer. Descriptor diagnosis confirms the Generic default declares and encodes all six axes at expected offsets and macOS enumerates all six elements, so no default descriptor change is claimed from this evidence. The `generic_unsigned_6axis` experimental A/B diagnostic verified the variant on target but did not improve the missing macOS HID/Chrome delivery, so it remains non-default. Broad game/app compatibility, physical refined Xbox Flight Pack host movement, automatic persona switching, durable reconnect robustness, and host breadth are not claimed | `docs/milestone-evidence/XBOX_BLE_WITNESS_2026-05-09.md`; `docs/milestone-evidence/LIVE_BRIDGE_WITNESS_2026-05-10.md`; `docs/milestone-evidence/LIVE_BRIDGE_SOAK_WITNESS_2026-05-10.md`; `docs/milestone-evidence/XBOX_BLE_PROFILE_V1_2026-05-29.md`; `docs/milestone-evidence/XBOX_STANDARD_LAYOUT_DIAGNOSTIC_2026-05-29.md`; `docs/milestone-evidence/VIRTUAL_INPUT_XBOX_BRIDGE_WITNESS_2026-05-30.md`; `docs/milestone-evidence/WINDOWS_XBOX_XINPUT_WITNESS_2026-06-04.md`; `docs/milestone-evidence/WINDOWS_XBOX_APP_COMPATIBILITY_WITNESS_2026-06-04_SPYRO_REIGNITED_TRILOGY.md`; `docs/milestone-evidence/WINDOWS_XBOX_RECONNECT_DIAGNOSTIC_2026-06-04.md`; `docs/milestone-evidence/WINDOWS_XBOX_RECONNECT_FIX_DIAGNOSTIC_2026-06-09.md`; `docs/milestone-evidence/PERSONA_SWITCHING_HYGIENE_DIAGNOSTIC_2026-05-31.md`; `docs/milestone-evidence/GENERIC_CHROME_GAMEPAD_EXPOSURE_DIAGNOSTIC_2026-05-31.md`; `docs/milestone-evidence/GENERIC_HID_DELIVERY_DIAGNOSTIC_2026-06-02.md`; `docs/milestone-evidence/GENERIC_REPORT_DESCRIPTOR_DIAGNOSTIC_2026-06-02.md`; `docs/milestone-evidence/GENERIC_COMPAT_VARIANT_DIAGNOSTIC_2026-06-02.md` |

## Toolchain

| Component | Version / Setting | Status | Note |
|-----------|-------------------|--------|------|
| ESP-IDF | `v5.5.3` via `crates/usb2ble-fw/Cargo.toml` | Baseline | No checked-in `IDF_PATH`; local env overrides bypass this pin |
| `esp-idf-sys` | `0.37.2` resolved from `esp-idf-sys = "0.37"` | Baseline | 0.37.x line retained |
| USB host hub config | `CONFIG_USB_HOST_HUBS_SUPPORTED=y` | Hub identity witness captured | Stable hub config; no experimental hub flag |

## Devices

| Device | VID | PID | Status | Note |
|--------|-----|-----|--------|------|
| HooToo SHUTTLE HT-UC001 powered hub | 2109 | 2813 | Hub identity and interface-class witness captured | Enumerates through ESP32-S3 USB host path as USB hub class `09` |
| AFTERGLOW PL-3702 Xbox-style wired gamepad | 0e6f | 0213 | Hub downstream identity and interface-class witness captured | Enumerates behind HooToo hub with four vendor-specific `CLASS=ff` interfaces; `interfaces=0` is expected for HID-only bookkeeping |
| USB keyboard, exact model not captured | 30fa | 2031 | Hub downstream identity and HID interface witness captured | Enumerates behind HooToo hub with two HID `CLASS=03` interfaces; app reports `interfaces=2` |
| THRUSTMASTER T.16000 FCS HOTAS | 044f | b10a | Descriptor, raw input report, HID summary, and baseline normalized-input witness captured | Enumerates behind HooToo hub with one HID `CLASS=03` interface; app reports `interfaces=1`; `GET_USB_DESCRIPTOR` returned 134 bytes; `GET_LAST_USB_REPORT` returned a 64-byte raw input report; `GET_HID_SUMMARY` returned 4 axes, 16 buttons, 1 hat, report ID 0; `GET_NORMALIZED_INPUT` returned 21 controls |
| THRUSTMASTER T.16000M FCS FLIGHT PACK device | 044f | b687 | TWCS normalized-input, practical RJ12 axis-label, refined target-side mapping, and host-visible Generic axis exposure witnesses captured | App contributes one HID interface; with TFRP pedals connected by RJ12, TWCS normalized axes changed during pedals-only movement; checked-in labels identify TWCS throttle as `axis_01_32`, RJ12 rudder as `axis_01_36`, left toe as `axis_01_34`, and right toe as `axis_01_33`; target-side refined mapping sends throttle/rudder/toe axes to intended Generic/Xbox controls with documented Xbox throttle compromise; browser Gamepad API evidence maps refined Generic `z/rx/ry/rz` to A2/A3/A4/A5 in Chrome on the witnessed Mac; three-separate-USB full-pack capture can fail with `ESP_ERR_NOT_SUPPORTED` while claiming the third interrupt stream |
| THRUSTMASTER T.16000M FCS FLIGHT PACK device | 044f | b679 | TFRP normalized-input witness captured as separate USB and through RJ12-to-TWCS topology | As separate USB, normalized report returned 3 axes plus vendor usages; through RJ12, pedal movement is represented in the TWCS `044f:b687` normalized report, with axis labels captured in `docs/milestone-evidence/FLIGHT_PACK_CALIBRATION_WITNESS_2026-05-28.md` |
| THRUSTMASTER T.16000M FCS FLIGHT PACK device | 044f | b10a | Hub downstream identity, HID interface, baseline normalized-input witness, and RJ12 two-USB simultaneous witness captured | App contributes one HID interface; normalized stream runs simultaneously with TWCS in the RJ12 two-USB topology; can fail as the third stream in the three-separate-USB topology depending on enumeration order |

## Personas

| Persona | ID | Status | Note |
|---------|----|--------|------|
| Generic Gamepad | `generic_gamepad` | Witnessed demo bridge path | Starts on ESP32-S3, pairs/connects to macOS, publishes synthetic and live USB-derived reports, appears in browser Gamepad API, works with `START_BRIDGE`, exposes refined practical RJ12 Flight Pack `z/rx/ry/rz` axes as browser A2/A3/A4/A5 in the checked-in Chrome witness, has a checked-in 300-second refined Generic live bridge soak, and passes a self-hosted browser game/app smoke. This is not broad external/native game/app compatibility, not final Flight Pack calibration, and not durable bond persistence. |
| Xbox Wireless Controller | `xbox_wireless_controller` | Witnessed compatibility persona slice plus target profile diagnostics; current host-visible standard-layout diagnostic is partial | Starts on ESP32-S3 with Xbox model 1914 / Series X\|S BLE identity, pairs/connects on macOS in earlier evidence as `Xbox Wireless Controller`, publishes synthetic and USB-derived 16-byte reports, exposes Xbox VID/PID in earlier browser evidence, and works with `START_BRIDGE`. Xbox BLE Profile v1 adds checked target-side diagnostics for Report ID 1 input, Report ID 3 output, model-1914 identity, and Flight Pack Xbox mapping. The 2026-05-29 deterministic host-visible run reached target BLE `Connected`; Chrome exposed `Xbox Wireless Controller (STANDARD GAMEPAD)` with `mapping="standard"` and expected standard stick, trigger, D-pad, A/B/X/Y, LB/RB, View, and Menu movement; stick-press buttons did not surface at B10/B11. Virtual normalized-input replay proves refined Flight Pack Xbox stick/rudder/toe mappings through the live bridge into Chrome standard controls. Broad Xbox/game/app compatibility and physical refined Xbox Flight Pack host movement are not claimed. |

## Compatibility Claim Boundaries

- Browser Gamepad API evidence is host-visible HID support, not a real game/app
  witness.
- Windows per-persona static-random identity evidence is checked in at
  `docs/milestone-evidence/WINDOWS_PER_PERSONA_STATIC_RANDOM_IDENTITY_DIAGNOSTIC_2026-06-04.md`.
  It proves distinct advertised addresses for Generic default, U6, and Xbox on
  Alex's Windows 11 PC, plus individual Windows Settings pairing and Xbox XInput
  deterministic reports. It does not prove cache-free Windows persona switching
  or coexistence, because Alex reported manual removal of the previous persona
  was still required before the next persona would connect.
- Windows single-persona Xbox XInput evidence is checked in at
  `docs/milestone-evidence/WINDOWS_XBOX_XINPUT_WITNESS_2026-06-04.md`.
  It proves `Xbox Wireless Controller` pairing, HID `045e:0b13`, XInput slot 0,
  deterministic Xbox reports, virtual Flight Pack Xbox mapping through XInput,
  and `joy.cpl` controller-panel movement on Alex's PC. It does not prove broad
  Windows compatibility, real game compatibility, BLE bond persistence,
  physical HOTAS movement, Xbox console support, or proprietary Xbox Wireless
  compatibility.
- Windows single-persona Xbox installed-game evidence is checked in at
  `docs/milestone-evidence/WINDOWS_XBOX_APP_COMPATIBILITY_WITNESS_2026-06-04_SPYRO_REIGNITED_TRILOGY.md`.
  It records one Spyro Reignited Trilogy 1.0.1.0 data point on Alex's PC:
  XInput slot 0 stayed connected while virtual Xbox mapping and deterministic
  reports ran, and Alex observed controls moving plus menu items being selected
  in Spyro. It does not prove broad game/app compatibility, physical HOTAS
  movement, final calibration quality, BLE bond persistence, Xbox console
  support, or proprietary Xbox Wireless compatibility.
- Windows single-persona Xbox reconnect diagnostic evidence is checked in at
  `docs/milestone-evidence/WINDOWS_XBOX_RECONNECT_DIAGNOSTIC_2026-06-04.md`.
  It records a failure/diagnostic: after target soft reset and Xbox persona
  reapply, Windows/PnP/HID/XInput could still show an apparently connected Xbox
  path, but deterministic reports stayed neutral and later target publish
  attempts returned `ERROR:Generic`. It does not prove durable BLE bond
  persistence, reconnect robustness, app/game behavior after reset, or physical
  HOTAS movement.
- Windows single-persona Xbox reconnect/report-delivery fix diagnostic evidence
  is checked in at
  `docs/milestone-evidence/WINDOWS_XBOX_RECONNECT_FIX_DIAGNOSTIC_2026-06-09.md`.
  It adds `STOP_BLE_PERSONA`, connection diagnostics, and bond diagnostics; after
  one manual Windows baseline pairing, stop/start persona and target soft reset
  plus explicit Xbox identity/persona reapply restored XInput report delivery
  without Windows cache cleanup. It does not prove direct host disconnect,
  runtime persona/identity persistence, durable BLE bond persistence,
  hard-power-cycle behavior, app/game behavior after reset, or physical HOTAS
  movement.
- Broad game/app compatibility remains unclaimed beyond the named checked-in
  app/game witnesses.
- Xbox support is limited to the checked-in macOS/browser compatibility evidence
  and live bridge/soak transcripts; it is not a claim of console, Windows,
  Steam, or arbitrary app compatibility. Xbox BLE Profile v1 target diagnostics
  are checked in at
  `docs/milestone-evidence/XBOX_BLE_PROFILE_V1_2026-05-29.md`, but they do not
  prove host-visible refined Xbox Flight Pack mapping by itself. A current deterministic
  macOS/Chrome diagnostic is checked in at
  `docs/milestone-evidence/XBOX_STANDARD_LAYOUT_DIAGNOSTIC_2026-05-29.md`; it
  reached target BLE `Connected`; Chrome exposed the device as
  `Xbox Wireless Controller (STANDARD GAMEPAD)` with `mapping="standard"` and
  expected standard stick, trigger, D-pad, A/B/X/Y, LB/RB, View, and Menu
  movement. Stick-press buttons did not surface at B10/B11. Virtual
  normalized-input replay for the refined Flight Pack Xbox mapping is checked
  in at
  `docs/milestone-evidence/VIRTUAL_INPUT_XBOX_BRIDGE_WITNESS_2026-05-30.md`;
  it proves deterministic virtual mapping/persona/bridge/Chrome visibility, not
  physical USB movement. Persona-switching hygiene diagnostic evidence is
  checked in at
  `docs/milestone-evidence/PERSONA_SWITCHING_HYGIENE_DIAGNOSTIC_2026-05-31.md`;
  it proves stale browser slots are detected/rejected and that manual macOS
  cache cleanup can restore Generic BLE HID visibility. The Generic Chrome
  exposure diagnostic at
  `docs/milestone-evidence/GENERIC_CHROME_GAMEPAD_EXPOSURE_DIAGNOSTIC_2026-05-31.md`
  narrows the remaining blocker to existing Chrome profile/session state by
  showing a clean temporary Chrome profile exposes the Generic gamepad again. It
  does not prove complete Generic virtual browser replay, automatic persona
  switching, or reconnect robustness. A follow-up Generic virtual bridge
  diagnostic at
  `docs/milestone-evidence/VIRTUAL_INPUT_GENERIC_BRIDGE_DIAGNOSTIC_2026-05-31.md`
  validates the throttle A2 endpoint pair in the clean temporary profile, but
  Chrome did not surface later virtual rudder/toe/stick report changes despite
  target report and bridge publication changes.
- Runtime configuration APIs and Web Serial tooling exist, and durable runtime
  config persistence is proven by
  `docs/milestone-evidence/CONFIG_PERSISTENCE_WITNESS_2026-05-28.md`.
- Browser Web Serial configurator smoke is proven for Google Chrome by
  `docs/milestone-evidence/WEB_SERIAL_CONFIGURATOR_SMOKE_2026-05-28.md`.
  Browser breadth and product-ready recovery behavior remain unproven.
- Practical RJ12 Flight Pack axis labels are proven by
  `docs/milestone-evidence/FLIGHT_PACK_CALIBRATION_WITNESS_2026-05-28.md`;
- Practical RJ12 Flight Pack target-side mapping refinement is proven by
  `docs/milestone-evidence/FLIGHT_PACK_MAPPING_REFINEMENT_WITNESS_2026-05-28.md`.
- Practical RJ12 Flight Pack refined Generic host-visible axis exposure is proven
  by
  `docs/milestone-evidence/REFINED_GENERIC_AXIS_EXPOSURE_WITNESS_2026-05-28.md`.
- Refined practical RJ12 Generic 300-second live bridge soak is proven by
  `docs/milestone-evidence/REFINED_GENERIC_LIVE_BRIDGE_SOAK_WITNESS_2026-05-28.md`.
- Self-hosted browser game/app smoke for the refined practical RJ12 Generic
  profile is proven by
  `docs/milestone-evidence/GAME_COMPATIBILITY_WITNESS_2026-05-28_SELF_HOSTED_SKY_RUN.md`.
  Final deadzone/calibration quality, real game/app mapping quality, and
  physical Xbox host-visible refined movement remain unproven.
- iPhone compatibility remains unproven. The first iPhone exploration is checked
  in as a useful failure: the target reported Generic BLE HID advertising, but
  the iPhone did not discover `USB2BLE Gamepad` in Settings > Bluetooth. See
  `docs/milestone-evidence/IPHONE_SAFARI_GENERIC_GAMEPAD_FAILURE_2026-05-29.md`
  and the follow-up target-side advertising diagnostic in
  `docs/milestone-evidence/IPHONE_BLE_ADVERTISING_DIAGNOSTIC_2026-05-29.md`.
