# Demo Roadmap

Status: **working plan for an ASAP demo without narrowing the final product.**

## Direction

The project should support many reasonable USB HID controller combinations:
HOTAS, throttles, pedals, gamepads, button boxes, keyboards used as controls,
and mixed-manufacturer setups. The path to that is descriptor-driven HID input,
source-aware normalized frames, data-driven mapping profiles, persona encoders,
and a BLE transport that only publishes already-encoded persona reports.

The first demo should not wait for all of that to be perfect. It should prove a
thin vertical slice while preserving those boundaries.

## Demo Slices

### Slice 0: USB to Encoded Generic Gamepad Report

Implemented in code, host-tested:

```text
USB HID reports -> HID descriptor decode -> normalized frames -> composite frame
-> generic auto mapper -> Generic Gamepad persona encoder -> encoded report bytes
```

Operator command:

```text
GET_GENERIC_GAMEPAD_REPORT
GET_GENERIC_GAMEPAD_MAPPING
```

Expected response shape:

```text
ENCODED_REPORT:persona=generic_gamepad;report_id=1;bytes=<hex>;
GENERIC_GAMEPAD_MAPPING:profile=generic_auto;persona=generic_gamepad;entries=<n>;mappings=<...>;
```

What this proves:

- the app can bridge from current live USB input state into a BLE-ready Generic
  Gamepad report payload
- mapping decisions can be inspected by source VID/PID/interface, source
  control, target control, value, and reason
- the target firmware can return those mapping diagnostics against live TWCS and
  T.16000M input state
- mapping/persona logic lives in pure host-testable crates
- the output payload shape is independent of USB and ESP-IDF details

What this does not prove:

- BLE advertising
- host BLE connection
- report publication over BLE
- exact semantic mapping for every HOTAS/pedal axis

### Slice 1: BLE-Only Generic Gamepad Self-Test

Implemented in code, target-build verified, and real Mac host connection/input
evidence exists:

```text
synthetic Generic Gamepad report -> BLE HID transport -> host-visible input
```

This isolates BLE transport risk from USB/HID complexity. The board can now
start a Generic Gamepad persona and accept an explicit synthetic self-test
command through the serial control plane.

Operator commands:

```text
START_BLE_GENERIC_GAMEPAD
SEND_BLE_SELF_TEST_REPORT
```

Expected response shape:

```text
BLE_ACTION:action=<action>;state=<state>;persona=generic_gamepad;report_id=1;bytes=<hex>;
```

What this proves today:

- BLE HID transport code links into the ESP32-S3 firmware target
- the BLE transport boundary accepts a `PersonaDescriptor` plus
  `EncodedBleReport`, keeping it independent of Generic Gamepad internals
- the self-test report is explicit synthetic evidence, not USB hardware input

What hardware evidence now exists:

- firmware boots as `0.4.2-ble-hid-demo`
- `START_BLE_GENERIC_GAMEPAD` initializes the BLE controller and returns
  `state=Advertising`
- a Mac host connects to the target and reports `USB2BLE Gamepad` as a connected
  BLE gamepad
- `GET_STATUS` reports `ble=Connected`
- `SEND_BLE_SELF_TEST_REPORT` produces visible host HID input
- the browser Gamepad API sees `USB2BLE Gamepad` and receives visible synthetic
  self-test input changes

What still needs hardware evidence:

- durable BLE bond persistence; target status still reports `bonds=false`
- game/application compatibility beyond the browser Gamepad API witness

### Slice 2: First Real USB to BLE Demo

First smoke witness exists, with semantic mapping/calibration still rough:

```text
curated USB input -> Generic auto/profile mapping -> Generic Gamepad BLE report
-> BLE publish -> host-visible input
```

Recommended hardware path for the Flight Pack demo:

```text
TFRP pedals -> RJ12 -> TWCS throttle
ESP32-S3 USB host path -> HooToo SHUTTLE HT-UC001 -> TWCS USB + T.16000M stick USB
```

This is the practical topology proven by the current M4 evidence.

What hardware evidence now exists:

- `PUBLISH_GENERIC_GAMEPAD_REPORT` can publish a report generated from live USB
  input over BLE
- Mac IOHID receives axis values from the live USB-derived BLE report
- a browser Gamepad API witness receives a change snapshot after a live
  USB-derived BLE publish
- a browser Gamepad API witness receives a live `flight_pack_demo` T.16000M
  stick-right movement as Generic Gamepad axis `0 = 1`
- `GET_GENERIC_GAMEPAD_MAPPING` has a target operator movement witness for
  T.16000M stick movement after refreshing a stale USB host session
- TWCS throttle movement, TFRP pedal movement through TWCS/RJ12, and T.16000M
  trigger press now have target delta witnesses
- downstream HID detach cleanup now removes stale device/interface/report state
  while preserving the attached hub
- a curated `flight_pack_demo` mapping profile is implemented, host-tested, and
  target-witnessed for the known T.16000M + TWCS/RJ12 topology
- GitHub Actions is expected to package a flashable merged ESP32-S3 firmware
  image for demo builds

What still needs demo polish:

- game/application compatibility beyond the browser Gamepad API witness
- calibration refinements for the explicit T.16000M/TWCS/TFRP mapping profile
- exact TFRP pedal axis naming through the TWCS/RJ12 report
- cleaner host naming after macOS has cached an older BLE product name

## Architecture Rules

- Keep USB/HID parsing generic and descriptor-driven.
- Keep source identity attached to every normalized value.
- Keep device-specific assumptions in mapping/profile data, not in USB,
  normalizer, persona, or BLE transport code.
- Keep BLE transport persona-agnostic: future Xbox Wireless-style output should
  be added as an Xbox persona/report encoder, not by rewriting USB decode or BLE
  publication plumbing.
- Prefer auto-mapping for fast demos and explicit profiles for supported paths.
- Treat manufacturer presets as accelerators, not as the core architecture.
- Do not claim universal HID support; claim curated and best-effort behavior
  with evidence.

## Mapping Strategy

The current generic auto mapper is intentionally conservative:

- buttons map to `button_1` through `button_16`
- the first hat maps to `hat`
- axes fill `x`, `y`, `z`, `rx`, `ry`, and `rz`
- sources with fewer unknown vendor fields are preferred for primary axes, so a
  joystick-like source is favored over a vendor-heavy throttle report

Near-term improvements:

- add explicit profile rules for the T.16000M + TWCS + TFRP RJ12 topology
- add calibration and inversion rules for axes
- add source selectors based on VID/PID, interface, capability fingerprint, and
  eventually serial/topology where available
- refine profile rules with calibration/deadzone metadata after the demo profile
  has a target witness
- when a mapping delta run shows no movement, first prove raw byte movement with
  `tools/usb_report_delta_witness.py`, then rerun the mapping delta witness
