# Windows Xbox Startup Reconnect Witness - 2026-06-09

## Summary

This witness covers the single-persona Xbox BLE-compatible path on Alex's
Windows PC after adding explicit persisted startup BLE configuration.

Result: pass for the scoped workflow. With startup BLE explicitly enabled for
Xbox plus `persona_static_random_experimental`, the target booted/reset into
the Xbox persona at `CB:B3:AE:FA:FC:EF` without serial reapply, Windows kept
XInput slot 0 connected, and deterministic Xbox reports moved XInput after
both target soft reset and an operator-assisted ESP32-S3 serial USB
power-cycle.

This does not make `persona_static_random_experimental` the default. It remains
explicit and non-default.

## Environment

- Source base before this evidence commit:
  `82b3fa88b429c34537b399f66b73f11a4dea73b8`
- Firmware state tested: working-tree startup BLE persistence and warm-restart
  changes that are checked in by this evidence commit.
- Host: Alex's Windows PC
- Windows query result during the run:
  - Product name: `Windows 10 Home`
  - Version: `2009`
  - Build: `26200`
  - HAL: `10.0.26100.1`
- Serial port: `COM3`
- Serial adapter: `USB-Enhanced-SERIAL CH343`
- Target: ESP32-S3
- USB topology reported by target:
  - HooToo hub: `2109:2813`
  - TWCS/RJ12: `044f:b687`
  - T.16000M: `044f:b10a`
- Physical HOTAS controls moved: no
- Windows Bluetooth remove/re-pair during this witness: no

Primary artifact root:

```text
target/windows-xbox-startup-persistence/windows_xbox_startup_20260609_174731
```

## Startup Configuration

The target was configured through the serial control plane:

```text
SET_STARTUP_BLE_IDENTITY_STRATEGY persona_static_random_experimental
SET_STARTUP_BLE_PERSONA xbox_wireless_controller
SET_STARTUP_BLE_VARIANT xbox_compatibility
ENABLE_STARTUP_BLE true
SAVE_CONFIG
```

The saved configuration then reported:

```text
startup_ble_enabled=true
startup_ble_persona=xbox_wireless_controller
startup_ble_identity_strategy=persona_static_random_experimental
startup_ble_variant=xbox_compatibility
```

The default configuration remains disabled and `legacy_public`. This run only
proves an explicit saved startup configuration.

## Firmware Fix During Witness

The first startup implementation loaded the saved config and started the Xbox
persona after soft reset, but deterministic report publication failed:

```text
PUBLISH_XBOX_TEST_REPORT left_stick_right
ERROR:Generic
last_report_send_return=-1
last_report_send_status=error
```

Windows and target diagnostics still showed an apparent connected Xbox path, so
the issue was not accepted as a reconnect pass. A controlled target-side
`STOP_BLE_PERSONA` followed by `START_BLE_XBOX_CONTROLLER` restored report
delivery without Windows cache cleanup. The firmware was then updated to run
that same one-time internal warm restart after opt-in startup BLE activation.

Final runtime startup diagnostics after the fix:

```json
{
  "enabled": true,
  "persona": "xbox_wireless_controller",
  "identity_strategy": "persona_static_random_experimental",
  "compatibility_variant": "xbox_compatibility",
  "runtime": {
    "attempted": true,
    "applied": true,
    "warm_restart_attempted": true,
    "warm_restart_applied": true,
    "last_action": "startup_ble_warm_restart",
    "last_error": null
  }
}
```

## Baseline Configured State

After flashing the startup-config firmware and saving the config:

- Target state: `Connected`
- Active persona: `xbox_wireless_controller`
- Active variant: `xbox_compatibility`
- Identity strategy: `persona_static_random_experimental`
- Current address: `CB:B3:AE:FA:FC:EF`
- Windows PnP/HID:
  - Bluetooth: `Xbox Wireless Controller`
  - HID path includes `VID_045E&PID_0B13`
  - BLE address in instance path: `CBB3AEFAFCEF`
- XInput:
  - slot 0 connected
- Deterministic report delivery:
  - left stick right: observed by XInput
  - left trigger max: observed by XInput
  - right trigger max: observed by XInput
  - A button: observed by XInput

Artifacts:

```text
target/windows-xbox-startup-persistence/windows_xbox_startup_20260609_174731/baseline_configured
```

## Soft Reset Result

A target soft reset was performed with:

```text
espflash reset --chip esp32s3 --port COM3 --non-interactive
```

After reset, no `SET_BLE_IDENTITY_STRATEGY` or
`START_BLE_XBOX_CONTROLLER` command was sent. The target reported:

```text
source=loaded
startup_ble_enabled=true
active_persona=xbox_wireless_controller
identity_strategy=persona_static_random_experimental
current_address=CB:B3:AE:FA:FC:EF
warm_restart_attempted=true
warm_restart_applied=true
```

Windows still showed:

- Bluetooth: `Xbox Wireless Controller`
- HID: `VID_045E&PID_0B13`
- XInput slot 0 connected

Deterministic report delivery after soft reset:

| Scenario | XInput result |
| --- | --- |
| left_stick_right | `left_thumb_x_max=32767` |
| left_trigger_max | `left_trigger_max=255` |
| right_trigger_max | `right_trigger_max=255` |
| button_a | `buttons_observed` included `4096` |

Artifacts:

```text
target/windows-xbox-startup-persistence/windows_xbox_startup_20260609_174731/soft_reset_final
```

## Power-Cycle Result

Alex performed the requested physical step:

```text
unplug and replug only the ESP32-S3 serial/programming USB cable
```

The HooToo hub and controls were left connected. After rediscovery:

- Serial port: `COM3`
- Startup config: loaded
- Active persona: `xbox_wireless_controller`
- Active variant: `xbox_compatibility`
- Identity strategy: `persona_static_random_experimental`
- Current address: `CB:B3:AE:FA:FC:EF`
- Startup runtime:
  - `attempted=true`
  - `applied=true`
  - `warm_restart_attempted=true`
  - `warm_restart_applied=true`
  - `last_error=null`
- Target bond diagnostics:
  - `bond_count=1`
  - `bonds_present=true`
  - bonded address: `50:FE:0C:02:AE:6A`
  - auth/encryption fields: `unknown`
- Windows PnP/HID:
  - Bluetooth: `Xbox Wireless Controller`
  - HID path includes `VID_045E&PID_0B13`
- XInput:
  - slot 0 connected

Deterministic report delivery after power-cycle:

| Scenario | XInput result |
| --- | --- |
| left_stick_right | `left_thumb_x_max=32767` |
| left_trigger_max | `left_trigger_max=255` |
| right_trigger_max | `right_trigger_max=255` |
| button_a | `buttons_observed` included `4096` |

Final target report-delivery counters:

```text
last_report_send_return=0
last_report_send_status=ok
publish_attempt_count=18
publish_ok_count=18
publish_not_connected_count=0
publish_persona_mismatch_count=0
```

Artifacts:

```text
target/windows-xbox-startup-persistence/windows_xbox_startup_20260609_174731/power_cycle
```

## Post-Final-Source Flash Sanity

After final formatting and evidence wording cleanup, the exact source tree for
this evidence commit was rebuilt for `xtensa-esp32s3-espidf` from the short
Windows path mirror and flashed successfully. This was a post-flash startup and
deterministic report-delivery sanity check, not a second hard power-cycle
witness.

Post-flash target diagnostics still showed:

- Startup BLE config loaded and enabled.
- Active persona: `xbox_wireless_controller`.
- Active variant: `xbox_compatibility`.
- Identity strategy: `persona_static_random_experimental`.
- Current address: `CB:B3:AE:FA:FC:EF`.
- Startup warm restart:
  - `attempted=true`
  - `applied=true`
  - `warm_restart_attempted=true`
  - `warm_restart_applied=true`
- Target bond diagnostics:
  - `bond_count=1`
  - `bonds_present=true`
- USB topology:
  - HooToo hub: `2109:2813`
  - TWCS/RJ12: `044f:b687`
  - T.16000M: `044f:b10a`

Post-flash deterministic XInput sanity:

| Scenario | XInput result |
| --- | --- |
| left_stick_right | `left_thumb_x_max=32767` |
| left_trigger_max | `left_trigger_max=255` |
| right_trigger_max | `right_trigger_max=255` |
| button_a | `buttons_observed` included `4096` |

Final target report-delivery status after the sanity check:

```text
last_report_send_return=0
last_report_send_status=ok
publish_attempt_count=12
publish_ok_count=12
publish_not_connected_count=0
publish_persona_mismatch_count=0
```

Artifacts:

```text
target/windows-xbox-startup-persistence/windows_xbox_startup_20260609_174731/post_final_flash_target_baseline.txt
target/windows-xbox-startup-persistence/windows_xbox_startup_20260609_174731/post_final_flash_xinput_sanity
```

## Classification

| Test | Classification | Notes |
| --- | --- | --- |
| Baseline saved startup config | pass | Config saved and target started Xbox at the expected static-random address. |
| Soft reset | pass | No serial identity/persona reapply; XInput report delivery worked after startup warm restart. |
| Operator-assisted ESP32-S3 serial USB power-cycle | pass | No Windows remove/re-pair; XInput report delivery worked after startup warm restart. |
| Direct BLE host disconnect | not tested here | Earlier diagnostic still records this path as unsupported. |
| Durable BLE bond persistence | partial/diagnostic only | Target reports `bond_count=1`, but auth/encryption details remain unknown. |
| App/game post-reset smoke | not run | This witness is reconnect/report-delivery evidence only. |

## Limitations

- This is a single-persona Xbox witness on Alex's Windows PC only.
- It does not prove broad Windows compatibility.
- It does not prove broad game/app compatibility.
- It does not prove Xbox console support or proprietary Xbox Wireless support.
- It does not prove physical HOTAS movement or final calibration quality.
- It does not prove cache-free Generic/U6/Xbox persona switching or coexistence.
- It does not fully prove durable BLE bond persistence; the target reported one
  stored bond, but auth/encryption event diagnostics remain `unknown`.
- The startup BLE path is explicit and disabled by default.
