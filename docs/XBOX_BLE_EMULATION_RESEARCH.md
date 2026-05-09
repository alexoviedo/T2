# Xbox BLE Emulation Research

Status: **research-backed implementation plan with the first host-tested Xbox
persona report and mapping step started.**

## Decision

Continue mapping work immediately, and implement Xbox Wireless Controller
emulation as a new BLE HID persona while preserving the current Generic Gamepad
demo path.

The Xbox path should be:

```text
USB HID inputs -> normalized frames -> selected mapping profile
-> xbox_wireless_controller persona frame -> Xbox BLE HID report
-> existing BLE transport
```

Do not replace the Generic Gamepad demo path. Add Xbox as a separate persona and
serial command set so the current demo remains available while Xbox support
stabilizes.

## Source Notes

- Bluetooth SIG HOGP says HID over GATT is the BLE profile used for HID devices
  over the Generic Attribute Profile.
- Espressif documents ESP32-S3 support for Bluetooth LE, Bluedroid, and NimBLE.
  ESP32-S3 Bluedroid/NimBLE support is BLE-only, which matches the desired Xbox
  BLE mode and excludes Xbox proprietary wireless work from this milestone.
- Espressif's HID device API demonstrates the report-oriented shape we already
  use: activate a HID device, connect, and send reports by report ID.
- `esp32beans/ESP32-BLE-HID-exp` includes an Xbox One BLE report-map capture and
  decodes Xbox input reports on ESP32/NimBLE hardware.
- `esp-cpp/espp` has an ESP32-S3 BLE HID service example that can emulate
  Xbox One, DualShock 4, DualSense, and Switch Pro controllers. Its Xbox helper
  models the same important shape: 15 buttons, a d-pad, four 16-bit stick axes,
  two 10-bit trigger axes, a consumer record/capture button, rumble output, and
  a battery report.
- `atar-axis/xpadneo` is a mature Linux Bluetooth driver for Xbox Wireless
  Controllers. It documents important host-facing behavior for BLE models,
  including unified HID descriptors, PID differences, share/profile quirks,
  battery reporting, rumble modes, and connection-parameter sensitivity.
- Microsoft's published GIPUSB material is useful background for Xbox USB/GIP,
  but the first Xbox BLE milestone should not implement GIPUSB or proprietary
  Xbox Wireless behavior.

## Xbox BLE HID Shape

The Xbox BLE input report is not the same as the current Generic Gamepad report.
The report-map capture from `ESP32-BLE-HID-exp` describes report ID `1` with:

- X and Y as unsigned 16-bit values, logical range `0..65534`
- Z and Rz as unsigned 16-bit values, logical range `0..65534`
- Brake as a 10-bit simulation-control value, logical range `0..1023`
- Accelerator as a 10-bit simulation-control value, logical range `0..1023`
- Hat switch as 4 bits, logical range `1..8`, with a null state
- 15 buttons as single-bit values
- a Consumer Page `Record` bit, used by sources as capture/share

That yields a 16-byte input payload when sent without the report ID byte in our
current `EncodedBleReport.bytes` convention:

```text
u16 x
u16 y
u16 z
u16 rz
u10 brake + 6 bits padding
u10 accelerator + 6 bits padding
u4 hat + 4 bits padding
u15 buttons + 1 bit padding
u1 record + 7 bits padding
```

The same report map also includes output report ID `3` for PID/rumble effects.
Rumble support should be parsed and logged in the first Xbox milestone, but it
does not need to drive hardware yet.

## Identity And Advertising

For host compatibility testing, the Xbox BLE persona should use Xbox-like HID
identity in the HID Device Information/PnP path:

```text
name: Xbox Wireless Controller
manufacturer: Microsoft
VID: 0x045e
PID: 0x0b13 for standard BLE models
PID: 0x0b22 for Elite Series 2-style identity
appearance: HID Gamepad
```

This is a compatibility target, not a claim of Microsoft certification.

`xpadneo` notes that BLE firmware moved Xbox controllers toward a unified HID
report descriptor and that only Elite Series 2 uses PID `0x0B22`; other BLE
models use PID `0x0B13`. It also notes that non-Elite controllers can appear to
have a Share button even when the physical controller does not.

## Unique Xbox Behaviors To Respect

- Xbox BLE is HOGP/BLE HID, not Xbox proprietary wireless.
- Xbox BLE input axes are unsigned, centered around the midpoint, unlike our
  Generic Gamepad persona's signed `i16` axes.
- Xbox triggers are separate 10-bit simulation controls, not signed axes.
- The hat range is `1..8` with null state, while our current Generic Gamepad
  report uses `0..8`.
- Button numbering is not a simple first-15 passthrough if we want Xbox-labeled
  semantics. Use an explicit persona schema with named controls.
- The capture/share function is a Consumer Page `Record` bit rather than one of
  the 15 gamepad button bits.
- Xbox BLE exposes output reports for rumble/haptics. Even if the first
  milestone ignores actuation, the BLE layer should be able to receive and
  report output report ID `3` so we do not paint ourselves into a corner.
- Battery reporting matters for host polish. We can start with a fixed battery
  value, then wire a real target/battery policy later.
- Bluetooth connection parameters can affect latency and stability. Keep this
  observable in target logs and avoid hiding reconnection problems behind demo
  claims.
- Audio is not part of the Bluetooth mode target. `xpadneo` explicitly notes
  audio is unavailable over Bluetooth mode for these controllers.

## Implementation Plan

1. Add an `xbox_wireless_controller` persona encoder in
   `crates/usb2ble-personas`. **Started:** the encoder, report map, schema,
   and focused host tests now exist.
2. Keep the encoder pure and host-tested. Current coverage includes:
   - descriptor exposes the Xbox BLE report map
   - neutral report encodes centered unsigned sticks, released triggers, neutral
     hat, no buttons
   - axis extremes scale from normalized `-32768..32767` to `0..65534`
   - triggers scale to `0..1023`
   - hat conversion maps our internal neutral to the Xbox null state
   - buttons map by named Xbox controls, not raw ordinal guesses
   - share/capture maps to the Consumer `Record` bit
3. Add a mapping profile that targets `xbox_wireless_controller` without
   changing the existing `flight_pack_demo` Generic Gamepad profile.
   **Started:** `xbox_auto` and `xbox_flight_pack_demo` host-tested mapping
   paths now exist.
4. Add control-plane commands after host tests. **Implemented:**
   `GET_XBOX_GAMEPAD_REPORT`, `GET_XBOX_GAMEPAD_MAPPING`,
   `START_BLE_XBOX_CONTROLLER`, `PUBLISH_XBOX_GAMEPAD_REPORT`, and
   `SEND_XBOX_SELF_TEST_REPORT` are decoded and handled through the
   app/firmware path.
5. Make the ESP32 BLE transport choose display name, PnP ID, appearance, and
   report map from `PersonaDescriptor` rather than hard-coding
   `USB2BLE Gamepad`. **Implemented:** Generic and Xbox identities are
   persona-specific static NUL-terminated constants.
6. Add output report plumbing for report ID `3` as an observed/logged event,
   then decide later whether to map it to physical rumble/haptics.
7. Capture evidence in this order:
   - host unit tests for encoder and mapping
   - target boot/advertise as Xbox persona
   - Mac/Windows host sees `Xbox Wireless Controller`
   - synthetic Xbox self-test changes host-visible input
   - live T.16000M/TWCS input publishes as Xbox BLE input

## Recommended Next Work

For the fastest honest demo, keep refining mapping/calibration on the Generic
Gamepad path while advancing Xbox behind pure encoders, mapping tests, and then
target BLE evidence. Do not make target BLE claims unless the host actually
discovers, pairs, and sees input from the Xbox persona.

## References

- Bluetooth SIG, HID over GATT Profile 1.0:
  https://www.bluetooth.com/specifications/specs/hid-over-gatt-profile-1-0/
- Bluetooth SIG, HID over GATT Profile 1.2:
  https://www.bluetooth.com/specifications/specs/hid-over-gatt-profile-hogp/
- Espressif ESP-IDF ESP32-S3 Bluetooth overview:
  https://docs.espressif.com/projects/esp-idf/en/v5.2/esp32s3/api-guides/bluetooth.html
- Espressif Bluetooth HID Device API:
  https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/bluetooth/esp_hidd.html
- `esp32beans/ESP32-BLE-HID-exp`:
  https://github.com/esp32beans/ESP32-BLE-HID-exp
- Xbox One BLE HID report map capture:
  https://raw.githubusercontent.com/esp32beans/ESP32-BLE-HID-exp/main/xbox_one_hid.md
- `esp-cpp/espp` HID service example:
  https://components.espressif.com/components/espp/hid_service/versions/1.0.34/examples/example?language=en
- `esp-cpp/espp` HID report helpers:
  https://esp-cpp.github.io/espp/hid/hid-rp.html
- `atar-axis/xpadneo`:
  https://github.com/atar-axis/xpadneo
- Linux HID BPF fixup for Xbox Elite 2 BLE:
  https://codebrowser.dev/linux/linux/drivers/hid/bpf/progs/Microsoft__Xbox-Elite-2.bpf.c.html
- Microsoft GIPUSB overview:
  https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-gipusb/15ad7aff-5ede-4fec-b047-9ddc6686973b
