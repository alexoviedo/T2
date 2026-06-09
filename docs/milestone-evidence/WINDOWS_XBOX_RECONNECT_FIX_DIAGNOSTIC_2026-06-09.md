# Windows Xbox Reconnect Fix Diagnostic - 2026-06-09

Status: single-persona Windows Xbox reconnect/report-delivery diagnostic from
Alex's Windows PC. This run adds explicit BLE persona stop diagnostics,
connection diagnostics, and target-side bond diagnostics, then verifies that
the single-persona Xbox path can recover XInput report delivery after
`STOP_BLE_PERSONA`/restart and after target soft reset/reapply without clearing
the Windows Bluetooth cache.

This is not broad Windows compatibility, broad game compatibility, Xbox console
compatibility, proprietary Xbox Wireless compatibility, physical HOTAS
movement, final calibration evidence, or a durable BLE bond-persistence claim.

## Context

- Date/time: 2026-06-09 around 15:34-17:08 Mountain time.
- Base repo commit before the local fix: `5dadc97ee24dde70fe845f443e1a1a5258b95371`
- Branch: `main`
- CI gate before hardware work: latest GitHub Actions run for `main` was green:
  <https://github.com/alexoviedo/T2/actions/runs/26982367965>
- Windows host: Alex's Windows PC. Registry reported product name
  `Windows 10 Home`, display version `25H2`, build `26200.8457`.
- Selected serial port: `COM3`
- Serial device: WCH CH343, `USB\VID_1A86&PID_55D3\5B5E020088`
- Primary artifact root:
  `target/windows-xbox-reconnect-fix/windows_xbox_reconnect_fix_20260609_153448`
- Main reconnect helper run:
  `target/windows-xbox-reconnect-fix/windows_xbox_reconnect_fix_20260609_153448/helper_runs/windows_xbox_reconnect_witness_20260609T230514Z`

No physical HOTAS controls were moved. No game/app test was run in this chunk.

## Repo And Validation Gate

The run started from clean, synced `main`:

```text
branch=main
HEAD=5dadc97ee24dde70fe845f443e1a1a5258b95371
```

The local no-hardware gate passed before hardware work:

```text
.\scripts\validate_no_hardware.ps1
python tools\check_evidence_docs.py --verbose
python tools\check_persona_acceptance.py
python tools\check_xbox_ble_profile.py
git diff --check
```

After the reconnect/report-delivery changes, the focused host checks passed:

```text
cargo test -p usb2ble-contracts -p usb2ble-control -p usb2ble-platform-esp32 -p usb2ble-fw --locked
python -m unittest discover -s tools/tests -p "test_*.py"
python -m py_compile tools\serial_command.py tools\windows_xbox_reconnect_witness.py
```

Target build verification succeeded from the short-path copy `C:\t2x` after the
normal Windows repo path hit ESP-IDF's output-path length limit. The resulting
firmware was flashed to `COM3` with `espflash flash --port COM3
--non-interactive`.

## Target Topology

The target was autodetected as `COM3`, WCH CH343. The practical RJ12 Flight Pack
topology was present before and after flashing:

```text
USB_STATUS:devices=3;interfaces=2;
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b687|id=3,vid=044f,pid=b10a
```

This proves target-side USB topology only. It does not prove physical HOTAS
movement.

## Commands And Diagnostics Added

This chunk added narrow control-plane support:

| Command | Result in this run |
| --- | --- |
| `STOP_BLE_PERSONA` | Stops bridge/virtual input, deinitializes the active BLE HID persona, stops advertising state, clears active app persona/variant, and returns target state to `Idle` without clearing bonds. |
| `GET_BLE_CONNECTION_INFO` | Reports active persona/variant, identity strategy/address, connection state, HIDD counters, stop/disconnect support, publish counters, last report-send status, and whether deterministic Xbox reports are currently allowed. |
| `GET_BLE_BOND_INFO` | Reports ESP-IDF bond count/list plus security parameters where available. Event-level authentication/encryption fields remain `unknown`. |
| `DISCONNECT_BLE_HOST` | Exposed as an explicit diagnostic command, but target support is currently `false`; the command returns `ERROR:Generic` and records `last_disconnect_host_return=-2147483648`. |

The post-reset `ERROR:Generic`/neutral-report failure from the 2026-06-04
diagnostic was narrowed to missing report-delivery readiness and active-persona
diagnostics. After the fix, the app/control path reports when deterministic
Xbox publishing is allowed, and the transport records publish attempts and the
last `esp_hidd_dev_input_set` return value.

## Identity And Pairing

The single Xbox persona used the explicit experimental identity strategy:

```text
strategy=persona_static_random_experimental
active_persona=xbox_wireless_controller
active_variant=xbox_compatibility
current_address=CB:B3:AE:FA:FC:EF
address_type=static_random
identity_applied=true
```

`legacy_public` remains the default identity behavior. The experimental
strategy remains explicit and non-default.

Windows cache removal and pairing were still not fully automated:

1. Automated cache removal safely identified USB2BLE-associated Xbox nodes at
   `CB:B3:AE:FA:FC:EF`, including the `VID_045E&PID_0B13` HID child, but
   `pnputil /remove-device` returned `Access is denied`.
2. Alex removed the USB2BLE-associated Xbox device in Windows Bluetooth
   settings.
3. The Windows BLE watcher saw `Xbox Wireless Controller` at
   `CB:B3:AE:FA:FC:EF`; automated WinRT pairing returned `FAILED`.
4. Alex paired/connected `Xbox Wireless Controller` in Windows Bluetooth
   settings.

No Windows cache cleanup was performed between the baseline pair and reconnect
tests.

## Baseline Pair/XInput Result

After manual Windows Settings pairing, the baseline was healthy:

```text
target_state=Connected
target_persona=xbox_wireless_controller
Windows Bluetooth= Xbox Wireless Controller
Windows HID= VID_045E&PID_0B13
XInput slot 0= connected
```

Target-side bond diagnostics now reported one stored bond:

```text
bond_count=1
bonds_present=true
bonded_device_addresses=["50:FE:0C:02:AE:6A"]
security_parameters.auth_request=bond
security_parameters.io_capability=none
security_parameters.key_size=16
security_parameters.init_key_mask=enc|id
security_parameters.rsp_key_mask=enc|id
```

The older semicolon `GET_STATUS`/`GET_BLE_ADVERTISING_INFO` bond fields still
reported `bonds=false`, so the new JSON `GET_BLE_BOND_INFO` is the more useful
target-side bond diagnostic. Authentication/encryption event fields remain
`unknown`, so this is not enough to claim durable BLE bond persistence.

Baseline deterministic XInput sanity passed:

| Scenario | XInput observation |
| --- | --- |
| `neutral` | Slot 0 connected, neutral values |
| `left_stick_right` | Left thumb X reached `32767` |
| `left_trigger_max` | Left trigger reached `255` |
| `right_trigger_max` | Right trigger reached `255` |
| `button_a` | Button bitfield included `4096` |

## Reconnect Tests

| Test | Target action | Classification | XInput/report result | Manual Windows action |
| --- | --- | --- | --- | --- |
| A - stop/start persona | `STOP_BLE_PERSONA`, then `START_BLE_XBOX_CONTROLLER` with the same strategy/address | `reconnect_pass_after_target_restart` | Slot 0 was connected immediately; deterministic sanity passed for left stick, triggers, and A. | No |
| B - disconnect/reconnect | `DISCONNECT_BLE_HOST` | `disconnect_unsupported` | The command returned `ERROR:Generic`; the host remained connected and deterministic sanity still passed. This did not exercise a true host disconnect. | No |
| C - soft reset | `espflash reset`, then reapply `persona_static_random_experimental` and `START_BLE_XBOX_CONTROLLER` | `reconnect_pass_after_target_restart` | Slot 0 was connected immediately after persona reapply; deterministic sanity passed for left stick, triggers, and A. | No |

After `STOP_BLE_PERSONA`, target state was cleanly idle without clearing bonds:

```text
STATUS:ble=Idle;profile=none;persona=none;bonds=false;
connection_state=Idle
active_persona=null
deterministic_xbox_reports_allowed=false
hidd_stop_count=1
bond_count=1
bonds_present=true
```

After restarting the Xbox persona, the target reconnected on the same address:

```text
STATUS:ble=Connected;profile=none;persona=xbox_wireless_controller;bonds=false;
connection_state=Connected
current_address=CB:B3:AE:FA:FC:EF
hidd_connect_count=2
deterministic_xbox_reports_allowed=true
```

After target soft reset, runtime state still did not persist by itself:

```text
connection_state=Idle
identity_strategy=legacy_public
active_persona=null
current_address=null
bond_count=1
bonds_present=true
```

The helper then reapplied the explicit experimental identity strategy and Xbox
persona. Windows/XInput reconnected without Windows cache cleanup, and report
delivery resumed. Final target diagnostics after the soft-reset sanity run
showed:

```text
connection_state=Connected
identity_strategy=persona_static_random_experimental
current_address=CB:B3:AE:FA:FC:EF
deterministic_xbox_reports_allowed=true
last_report_id=1
last_report_len=16
last_report_send_return=0
last_report_send_status=ok
publish_attempt_count=10
publish_ok_count=10
publish_not_connected_count=0
publish_persona_mismatch_count=0
bond_count=1
bonds_present=true
```

## Artifact Map

- Repo/CI/hygiene and pre-hardware validation:
  `target/windows-xbox-reconnect-fix/windows_xbox_reconnect_fix_20260609_153448/`
- Implementation review:
  `target/windows-xbox-reconnect-fix/windows_xbox_reconnect_fix_20260609_153448/implementation_review.md`
- Target build/flash transcripts:
  `target/windows-xbox-reconnect-fix/windows_xbox_reconnect_fix_20260609_153448/target_build_preflash_short_path_retry.txt`
  and
  `target/windows-xbox-reconnect-fix/windows_xbox_reconnect_fix_20260609_153448/flash_output.txt`
- Automated cache-removal failure:
  `target/windows-xbox-reconnect-fix/windows_xbox_reconnect_fix_20260609_153448/helper_runs/windows_xbox_reconnect_witness_20260609T224055Z/`
- Clean Xbox advertisement plus failed automated pairing:
  `target/windows-xbox-reconnect-fix/windows_xbox_reconnect_fix_20260609_153448/helper_runs/windows_xbox_reconnect_witness_20260609T230154Z/`
- Baseline pair, stop/start, unsupported disconnect, and soft-reset reconnect:
  `target/windows-xbox-reconnect-fix/windows_xbox_reconnect_fix_20260609_153448/helper_runs/windows_xbox_reconnect_witness_20260609T230514Z/`
- Final post-test target diagnostics:
  `target/windows-xbox-reconnect-fix/windows_xbox_reconnect_fix_20260609_153448/final_target_diagnostics_after_reconnect_tests.txt`

## Conclusion

For the single-persona Xbox BLE-compatible path on Alex's Windows PC:

- Baseline manual Windows Settings pairing still works.
- Windows exposes `Xbox Wireless Controller`, HID `045e:0b13`, and XInput slot
  0 after manual pairing.
- `GET_BLE_BOND_INFO` now reports one target-side stored bond after Windows
  pairing and after target soft reset, but durable BLE bond persistence is not
  fully proven because authentication/encryption event fields remain `unknown`
  and no long-term or hard power-cycle witness was run.
- `STOP_BLE_PERSONA` provides a clean no-bond-clear way to stop the active BLE
  HID persona.
- Stop/start persona and soft reset plus explicit persona/identity reapply both
  restored report delivery without Windows cache cleanup.
- The previous post-reset neutral-report/`ERROR:Generic` failure was not
  reproduced after these diagnostics/control changes; deterministic reports
  moved XInput and target report-send status was `ok`.
- Direct host disconnect is still unsupported by the current ESP32 target path.
- Runtime identity strategy and active persona still do not persist across soft
  reset; they must be reapplied.

The next product-quality chunk should target persistence and disconnect
hardening: decide whether the explicit Xbox strategy/persona should be stored
as a user-selected runtime config, add deeper GAP/HIDD security event telemetry
if available, and either implement a real host-disconnect path or document it
as unsupported for this ESP-IDF HIDD layer.
