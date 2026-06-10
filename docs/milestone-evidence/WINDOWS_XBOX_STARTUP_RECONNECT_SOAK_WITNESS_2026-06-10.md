# Windows Xbox Startup Reconnect Soak Witness - 2026-06-10

## Summary

This witness covers two narrow follow-ups to the 2026-06-09 single-persona
Xbox startup reconnect witness on Alex's Windows PC:

1. `GET_BLE_BOND_INFO` now surfaces richer ESP-IDF GAP authentication and
   bond-list telemetry.
2. The explicit persisted startup Xbox mode completed a five-cycle target
   soft-reset soak without Windows remove/re-pair or physical control movement.

Result: pass for the scoped reconnect/report-delivery soak. Across five target
soft resets, the target automatically returned to the Xbox persona at
`CB:B3:AE:FA:FC:EF`, Windows kept XInput slot 0 connected, and deterministic
Xbox reports moved XInput for left stick, triggers, and A button.

This does not make startup BLE or `persona_static_random_experimental` the
default. Both remain explicit and non-default.

## Environment

- Source base before this evidence commit:
  `c9e23651adf2be2e6725d893885b178a8be4d2ca`
- Firmware state tested: working-tree ESP-IDF bond telemetry changes that are
  checked in by this evidence commit.
- Host: Alex's Windows PC
- Windows query result during the run:
  - OS name: `Microsoft Windows 11 Home`
  - OS version: `10.0.26200`
  - OS build: `26200`
  - Windows product name reported by PowerShell: `Windows 10 Home`
  - Windows version field: `2009`
- Serial port: `COM3`
- Target: ESP32-S3
- USB topology reported by target:
  - HooToo hub: `2109:2813`
  - TWCS/RJ12: `044f:b687`
  - T.16000M: `044f:b10a`
- Physical HOTAS controls moved: no
- Windows Bluetooth remove/re-pair during this witness: no

Primary artifact root:

```text
target/windows-xbox-reconnect-soak/windows_xbox_reconnect_soak_20260610_000938
```

## Telemetry Added

`GET_BLE_BOND_INFO` now reports additional ESP32 target telemetry when the
ESP-IDF GAP callbacks expose it:

- auth-complete event count, status, success flag, failure reason, address,
  address type, and auth mode,
- key event count, last key type, and last key event address,
- security-request event count, address, and security response return,
- numeric-comparison, passkey-notification, and passkey-request event counts,
- per-bond address, address type, key mask, and key mask names,
- last clear-bond status and whether `FORGET_BLE_BONDS` completed,
- security parameter summary,
- an explicit encryption telemetry source/status field.

The ESP-IDF binding path used here does not expose a separate encryption-change
GAP event, so the target reports:

```text
last_encryption_status=unknown_no_dedicated_gap_event
encryption_event_source=esp_gap_auth_complete_and_key_events
```

Host-side stubs also return the expanded schema, with unknown/default values,
so host tests can keep validating response shape without claiming target
security behavior.

## Build And Flash

After the telemetry patch, host checks and the ESP32-S3 target build passed.
The target firmware was built from the short Windows path mirror and flashed to
`COM3`.

Target build artifact:

```text
target/windows-xbox-reconnect-soak/windows_xbox_reconnect_soak_20260610_000938/target_build_after_telemetry_patch.txt
```

Flash artifact:

```text
target/windows-xbox-reconnect-soak/windows_xbox_reconnect_soak_20260610_000938/flash_after_telemetry_patch.txt
```

The flash log reported:

```text
Chip type: esp32s3
Flash size: 16MB
App/part. size: 2,728,128/16,384,000 bytes, 16.65%
```

## Baseline After Flash

The board already had explicit startup BLE config saved from the prior startup
reconnect witness:

```text
startup_ble_enabled=true
startup_ble_persona=xbox_wireless_controller
startup_ble_identity_strategy=persona_static_random_experimental
startup_ble_variant=xbox_compatibility
```

After flashing the telemetry build, the target reported:

```text
active_persona=xbox_wireless_controller
active_variant=xbox_compatibility
identity_strategy=persona_static_random_experimental
current_address=CB:B3:AE:FA:FC:EF
startup_ble.runtime.applied=true
startup_ble.runtime.warm_restart_applied=true
connection_state=Connected
deterministic_xbox_reports_allowed=true
```

Windows probe after flash reported:

- Bluetooth device: `Xbox Wireless Controller`
- HID path includes: `VID_045E&PID_0B13`
- BLE address in the HID/Bluetooth path: `CBB3AEFAFCEF`
- XInput slot 0: connected

Artifacts:

```text
target/windows-xbox-reconnect-soak/windows_xbox_reconnect_soak_20260610_000938/target_baseline_after_flash.txt
target/windows-xbox-reconnect-soak/windows_xbox_reconnect_soak_20260610_000938/xinput_probe_after_flash.txt
target/windows-xbox-reconnect-soak/windows_xbox_reconnect_soak_20260610_000938/post_flash_xinput_sanity
```

## Bond And Security Diagnostics

The expanded `GET_BLE_BOND_INFO` response after flash included:

```text
bond_count=1
bonds_present=true
bonded_device_addresses=["50:FE:0C:02:AE:6A"]
bonded_devices[0].address_type_name=public
bonded_devices[0].key_mask_names=["peer_identity_key"]
auth_complete_count=2
last_auth_complete_status=success
last_auth_complete_success=true
last_auth_complete_address=50:FE:0C:02:AE:6A
last_auth_complete_auth_mode_name=bond
last_auth_complete_key_present=false
last_auth_complete_bonded=false
key_event_count=0
security_request_count=0
last_encryption_status=unknown_no_dedicated_gap_event
```

This improves the diagnostic picture compared with the prior
`auth/encryption=unknown` state. It shows an ESP-IDF bond-list entry and
auth-complete callbacks for the Windows host address. It does not fully prove
durable BLE bond persistence: the latest auth-complete event reported
`key_present=false`, the stored key mask only listed `peer_identity_key`, and
the active encrypted/authenticated link state still reports `unknown`.

The legacy `GET_STATUS` `bonds=false` field was not treated as authoritative
for this witness; `GET_BLE_BOND_INFO` is the richer diagnostic path.

## Five-Cycle Soft-Reset Soak

The soak used `espflash reset --chip esp32s3 --port COM3 --non-interactive` for
each cycle. No Windows Bluetooth device removal, Windows re-pair, serial
identity/persona reapply, or physical control movement was performed.

Summary artifact:

```text
target/windows-xbox-reconnect-soak/windows_xbox_reconnect_soak_20260610_000938/soft_reset_soak_5cycles/soak_summary.json
```

Overall result:

```text
cycles_requested=5
pass_count=5
fail_count=0
overall_pass=true
windows_remove_repair_used=false
physical_controls_used=false
```

| Cycle | Startup Xbox Applied | Address | XInput Slot 0 | Deterministic Reports | Bond Count | Publish Status |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | yes | `CB:B3:AE:FA:FC:EF` | connected | left stick, LT, RT, A moved | 1 | `publish_ok_count=12`, no not-connected or persona-mismatch publishes |
| 2 | yes | `CB:B3:AE:FA:FC:EF` | connected | left stick, LT, RT, A moved | 1 | `publish_ok_count=12`, no not-connected or persona-mismatch publishes |
| 3 | yes | `CB:B3:AE:FA:FC:EF` | connected | left stick, LT, RT, A moved | 1 | `publish_ok_count=12`, no not-connected or persona-mismatch publishes |
| 4 | yes | `CB:B3:AE:FA:FC:EF` | connected | left stick, LT, RT, A moved | 1 | `publish_ok_count=12`, no not-connected or persona-mismatch publishes |
| 5 | yes | `CB:B3:AE:FA:FC:EF` | connected | left stick, LT, RT, A moved | 1 | `publish_ok_count=12`, no not-connected or persona-mismatch publishes |

Representative XInput observations in every cycle:

```text
left_stick_right  -> left_thumb_x=32767
left_trigger_max  -> left_trigger=255
right_trigger_max -> right_trigger=255
button_a          -> buttons=4096
```

## Classification

| Area | Classification | Notes |
| --- | --- | --- |
| Expanded bond/auth telemetry | pass | `GET_BLE_BOND_INFO` now reports auth-complete, key, security-request, key-mask, and explicit encryption-source fields. |
| Startup Xbox soft-reset soak | pass | Five of five soft resets restored Xbox startup config and XInput report delivery. |
| Windows remove/re-pair avoidance | pass for this soak | The existing Windows pairing was reused throughout all five cycles. |
| XInput report delivery after reset | pass | Deterministic reports moved left stick, triggers, and A button in every cycle. |
| Durable BLE bond persistence | partial/diagnostic only | Target reports one bond-list entry and auth-complete success, but active encryption/authentication and complete key persistence are still not proven. |
| Direct BLE host disconnect | unchanged | Earlier diagnostics still record this path as unsupported. |
| Hard power-cycle breadth | not tested here | The prior 2026-06-09 witness covered one operator-assisted ESP32-S3 serial USB power-cycle; this witness is a soft-reset soak. |
| App/game after reset | not tested here | This witness is reconnect/report-delivery evidence only. |

## Limitations

- This is single-persona Xbox startup reconnect evidence on Alex's Windows PC
  only.
- It does not prove broad Windows compatibility.
- It does not prove broad game/app compatibility.
- It does not prove Xbox console support or proprietary Xbox Wireless support.
- It does not prove physical HOTAS movement or final calibration quality.
- It does not prove cache-free Generic/U6/Xbox persona switching or
  coexistence.
- It does not fully prove durable BLE bond persistence; the target reports a
  stored bond entry and auth-complete events, but active encryption,
  authenticated host state, and complete key persistence remain bounded by the
  telemetry above.
- Startup BLE remains explicit and disabled by default.
