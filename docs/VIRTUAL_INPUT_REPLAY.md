# Virtual Input Replay

Status: diagnostic/test infrastructure design for deterministic live-bridge
witnesses. This is not a replacement for real USB HID parser or physical-input
evidence.

## Purpose

USB2BLE already has checked-in evidence that the ESP32-S3 can enumerate the
practical RJ12 Flight Pack topology, parse real USB HID input, normalize source
controls, and publish refined Generic output to a host. Later bridge and persona
work should not require Alex to repeatedly move HOTAS and pedal controls when
the question under test is the mapping/persona/BLE/browser path.

Virtual input replay gives the firmware a diagnostic-only normalized input
source so tests can exercise:

```text
virtual normalized input
-> runtime mapping rules
-> persona encoder
-> BLE live bridge publish
-> host/browser Gamepad API witness
```

The witness must always label this as virtual normalized-input evidence, not
physical USB movement.

## Replay Layers

| Layer | What it tests | Risk |
| --- | --- | --- |
| Raw USB report replay | HID descriptor parser, report decoder, normalizer, mapper, persona, BLE | Strongest replay, but requires device-specific descriptor/report fixtures and more firmware plumbing. |
| Normalized input replay | mapper, runtime config, persona encoder, BLE bridge, host exposure | First implementation. It is deterministic and reuses the path after USB parsing. |
| Mapped persona report publication | persona encoder or explicit report bytes, BLE host exposure | Useful for persona layout diagnostics, but bypasses mapping and live bridge. |

Virtual Input Replay v1 uses normalized input replay first because USB parsing
and real source labels are already separately evidenced. Raw report replay is a
future enhancement for arbitrary HID regression coverage.

## Firmware Mode

Virtual input is disabled by default. It is enabled only by serial diagnostic
commands:

```text
START_VIRTUAL_INPUT
STOP_VIRTUAL_INPUT
GET_VIRTUAL_INPUT_STATUS
PUBLISH_VIRTUAL_INPUT_FRAME <scenario>
RUN_VIRTUAL_INPUT_SEQUENCE <sequence_name>
```

When enabled, report/mapping/bridge calls consume the virtual composite frame
instead of the latest live USB frame. When disabled, normal USB host behavior is
unchanged. Status reports include the active input source so witnesses can tell
whether a bridge publish came from virtual replay or live USB input.

## Flight Pack v1 Scenarios

The first scenario set models the known practical RJ12 topology:

- T.16000M stick source: `044f:b10a`
- TWCS/RJ12 source: `044f:b687`
- source controls: `axis_01_30`, `axis_01_31`, `axis_01_32`,
  `axis_01_36`, `axis_01_34`, `axis_01_33`

Supported named scenarios:

- `neutral`
- `stick_left`, `stick_right`, `stick_forward`, `stick_back`
- `rudder_left`, `rudder_right`
- `left_toe_released`, `left_toe_pressed`
- `right_toe_released`, `right_toe_pressed`
- `throttle_min`, `throttle_max`

## Witness Tool

`tools/virtual_input_bridge_witness.py` drives the workflow:

```bash
python3 tools/virtual_input_bridge_witness.py --persona generic --scenarios all
python3 tools/virtual_input_bridge_witness.py --persona xbox --scenarios all
```

Use `--no-browser` for target-only dry runs. Use `--no-human`,
`--auto-arm`, and `--assume-bluetooth-connected` when target/browser state is
already sufficient and the run should not pause for operator confirmation.
Browser-backed runs start the local Gamepad witness and capture serial
transcripts, mapping diagnostics, encoded reports, bridge counters, and Gamepad
API changes under:

```text
target/virtual-input-bridge-witness/
```

The first checked-in host-visible virtual replay evidence is
`docs/milestone-evidence/VIRTUAL_INPUT_XBOX_BRIDGE_WITNESS_2026-05-30.md`.

## Browser Slot Hygiene

Persona switching can leave Chrome/macOS with a stale Gamepad API slot from the
previous BLE persona. The witness page and `tools/virtual_input_bridge_witness.py`
therefore support strict browser expectations:

```text
autoArm=1
expectedPersona=generic|xbox
expectedMapping=none|standard|any
expectedIdContains=<substring>
rejectStale=1
sessionLabel=<unique-run-label>
```

For Generic replay, the strict witness expects a non-standard Generic slot with
at least six axes and rejects stale Xbox-shaped `STANDARD GAMEPAD` samples. For
Xbox replay, it expects Chrome's `mapping="standard"` layout.

`tools/persona_switch_hygiene.py` runs one or more virtual bridge witnesses as a
persona-switching hygiene check. The 2026-05-31 diagnostic showed that the
stale-slot detector prevents false Generic evidence, but this Mac still needed
host Bluetooth/cache cleanup before a clean no-human Generic browser replay
could be captured. See
`docs/milestone-evidence/PERSONA_SWITCHING_HYGIENE_DIAGNOSTIC_2026-05-31.md`.

## Claim Boundaries

Virtual input evidence can prove deterministic mapping/persona/live-bridge
behavior for a known normalized source model. It cannot prove:

- physical USB movement happened,
- HID descriptor parsing is correct for a new device,
- final calibration feel,
- broad host/game compatibility,
- BLE bond/reconnect behavior.

Real USB/HID parser regressions still require raw HID report fixtures or target
hardware witnesses. Virtual input should complement that evidence, not replace
it.
