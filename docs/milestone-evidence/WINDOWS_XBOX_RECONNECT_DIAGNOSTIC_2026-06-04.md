# Windows Xbox Reconnect Diagnostic - 2026-06-04

Status: single-persona Windows Xbox reconnect diagnostic from Alex's Windows
PC. This run confirms the known good baseline after manual Windows Settings
pairing, then shows that a target soft reset does not prove durable BLE bond
persistence or reliable report delivery. After reset, Windows and the target
reported a connected Xbox path, but deterministic Xbox reports no longer moved
XInput and later publish attempts returned `ERROR:Generic`.

This is not broad Windows compatibility, broad game compatibility, Xbox console
compatibility, proprietary Xbox Wireless compatibility, durable BLE bond
persistence, physical HOTAS movement, or final calibration evidence.

## Context

- Date/time: 2026-06-04 around 15:40-15:58 Mountain time.
- Repo/firmware commit at start: `97c298c38bdfdf87a00f0238a6e383289d161897`
- Branch: `main`
- CI gate: latest GitHub Actions run for `main` was green before hardware work:
  <https://github.com/alexoviedo/T2/actions/runs/26980368557>
- Windows host: Alex's Windows PC. Registry reported `Windows 10 Home`,
  display version `25H2`, build `26200.8457`.
- Selected serial port: `COM3`
- Serial device: WCH CH343, `USB\VID_1A86&PID_55D3\5B5E020088`
- Primary artifact root:
  `target/windows-xbox-reconnect/windows_xbox_reconnect_20260604_154059`
- Main reconnect helper run:
  `target/windows-xbox-reconnect/windows_xbox_reconnect_20260604_154059/helper_runs/windows_xbox_reconnect_witness_20260604T215511Z`

No firmware was flashed in this chunk. No physical HOTAS controls were moved.

## Repo And Validation Gate

The run started from clean, synced `main`:

```text
branch=main
HEAD=97c298c38bdfdf87a00f0238a6e383289d161897
origin/main=97c298c38bdfdf87a00f0238a6e383289d161897
working tree clean before reconnect helper changes
```

GitHub Actions for `main` was green before hardware work. Local no-hardware
validation passed before hardware work:

```text
.\scripts\validate_no_hardware.ps1
python tools\check_evidence_docs.py --verbose
python tools\check_persona_acceptance.py
python tools\check_xbox_ble_profile.py
git diff --check
```

## Target Topology

The target was autodetected as `COM3`, WCH CH343. The practical RJ12 Flight Pack
topology was present:

```text
USB_STATUS:devices=3;interfaces=2;
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b10a|id=3,vid=044f,pid=b687
```

This proves target-side USB topology only. It does not prove physical HOTAS
movement.

## Identity And Bond Diagnostics

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

Target bond diagnostics before and after the reconnect test were consistently
negative:

```text
STATUS:ble=Connected;profile=none;persona=xbox_wireless_controller;bonds=false;
security.bonds_present=false
security.bond_count=0
security.last_bonded_host=unavailable
```

The target reports `bond_storage_enabled=true` as intended profile policy, but
this run did not observe any stored target bonds. Therefore it does not prove
BLE bond persistence.

## Manual Actions

Automated Windows cache removal correctly identified only USB2BLE-associated
Xbox nodes at `CB:B3:AE:FA:FC:EF`, including `Xbox Wireless Controller`,
`Bluetooth LE XINPUT compatible input device`, and the HID
`VID_045E&PID_0B13` child. Windows denied each `pnputil /remove-device`
operation with `Access is denied`.

Manual actions required:

1. Alex removed/forgot the USB2BLE-associated Xbox device in Windows Bluetooth
   settings after automated removal was denied.
2. Automated WinRT pairing discovered `Xbox Wireless Controller` at
   `CB:B3:AE:FA:FC:EF`, but `pair_async()` returned `FAILED`.
3. Alex paired/connected `Xbox Wireless Controller` in Windows Bluetooth
   settings.

No physical controls were moved.

## Baseline Pair/XInput Result

After manual Windows pairing, the baseline path was healthy:

```text
target_state=Connected
target_persona=xbox_wireless_controller
target_bonds=false
Windows Bluetooth= Xbox Wireless Controller
Windows HID= VID_045E&PID_0B13
XInput slot 0= connected
```

Baseline deterministic XInput sanity passed:

| Scenario | XInput observation |
| --- | --- |
| neutral | Slot 0 connected, neutral values |
| left_stick_right | Left thumb X reached `32767` |
| left_trigger_max | Left trigger reached `255` |
| right_trigger_max | Right trigger reached `255` |
| button_a | Button bitfield included `4096` |

This reconfirms the known single-persona Xbox/XInput baseline after manual
Windows Settings pairing.

## Reconnect Tests

| Test | Result | Classification |
| --- | --- | --- |
| A - stop/start advertising | Not exercisable with current command surface. `STOP_BRIDGE` and `STOP_VIRTUAL_INPUT` do not stop the BLE HID persona, and there is no current `STOP_BLE_XBOX_CONTROLLER` or disconnect command. | `not_exercisable_no_stop_persona_command` |
| B - target soft reset | `espflash reset --chip esp32s3 --port COM3 --non-interactive` succeeded. After reset, target returned to `Idle`, `legacy_public`, no persona, and no bonds. The helper reapplied `persona_static_random_experimental` and `START_BLE_XBOX_CONTROLLER`; Windows/XInput slot 0 appeared connected, but deterministic reports did not move XInput. | `reconnect_fail` |
| C - power-cycle surrogate | Not run. The soft-reset diagnostic already showed a meaningful connected-but-no-input failure mode, so a hard power-cycle was not needed in this chunk. | `not_run` |

Soft-reset target state before reapplying the persona:

```text
STATUS:ble=Idle;profile=none;persona=none;bonds=false;
strategy=legacy_public
identity_applied=false
```

Soft-reset target state after reapplying the same persona and address:

```text
STATUS:ble=Connected;profile=none;persona=xbox_wireless_controller;bonds=false;
strategy=persona_static_random_experimental
current_address=CB:B3:AE:FA:FC:EF
```

Post-reset XInput sanity failed:

| Scenario | Post-reset XInput observation |
| --- | --- |
| neutral | Slot 0 connected, neutral values |
| left_stick_right | Slot 0 stayed neutral, left thumb X stayed `0` |
| left_trigger_max | Slot 0 stayed neutral, left trigger stayed `0` |
| right_trigger_max | Slot 0 stayed neutral, right trigger stayed `0` |
| button_a | Slot 0 stayed neutral, button bitfield stayed `0` |

A delayed follow-up sanity run after an additional settle period produced the
same host-visible result and target-side publish failures:

```text
PUBLISH_XBOX_TEST_REPORT neutral
ERROR:Generic
PUBLISH_XBOX_TEST_REPORT left_stick_right
ERROR:Generic
PUBLISH_XBOX_TEST_REPORT left_trigger_max
ERROR:Generic
PUBLISH_XBOX_TEST_REPORT right_trigger_max
ERROR:Generic
PUBLISH_XBOX_TEST_REPORT button_a
ERROR:Generic
```

Final Windows probe still showed PnP/HID and XInput presence:

```text
Bluetooth: Xbox Wireless Controller
HID: VID_045E&PID_0B13, address CBB3AEFAFCEF
XInput: slot 0 connected, neutral values
```

The important failure mode is therefore not simply "device absent." It is
"Windows and target report connected, but report delivery does not resume after
target reset."

## Artifact Map

- Repo/CI/hygiene and pre-hardware validation:
  `target/windows-xbox-reconnect/windows_xbox_reconnect_20260604_154059/`
- Initial automated cache-removal failure:
  `target/windows-xbox-reconnect/windows_xbox_reconnect_20260604_154059/helper_runs/windows_xbox_reconnect_witness_20260604T214940Z/`
- Clean advertisement plus failed automated pairing before manual pair:
  `target/windows-xbox-reconnect/windows_xbox_reconnect_20260604_154059/helper_runs/windows_xbox_reconnect_witness_20260604T215112Z/`
- Main baseline and soft-reset reconnect run:
  `target/windows-xbox-reconnect/windows_xbox_reconnect_20260604_154059/helper_runs/windows_xbox_reconnect_witness_20260604T215511Z/`
- Delayed post-reset sanity follow-up:
  `target/windows-xbox-reconnect/windows_xbox_reconnect_20260604_154059/delayed_post_reset_sanity/`
- Final failed reconnect state:
  `target/windows-xbox-reconnect/windows_xbox_reconnect_20260604_154059/final_failed_reconnect_state/`

The reconnect helper's first saved classification for the soft-reset run was
reviewed against the raw scenario data and corrected in the checked-in helper:
an XInput slot that is connected but does not move under deterministic reports
is a reconnect failure, not a reconnect pass.

## Conclusion

For the single-persona Xbox BLE-compatible path on Alex's Windows PC:

- Baseline manual Windows Settings pairing still works.
- Windows exposes `Xbox Wireless Controller`, HID `045e:0b13`, and XInput slot
  0 after manual pairing.
- Baseline deterministic reports still drive XInput.
- Target-side bond diagnostics report `bonds=false` and `bond_count=0`.
- Runtime identity strategy and persona do not persist across target reset; the
  target returns to `legacy_public`, no active persona.
- Reapplying the Xbox persona after soft reset can restore apparent
  Windows/target connection state, but deterministic reports do not resume
  XInput movement.
- Durable BLE bond persistence and reliable reconnect/report delivery are not
  proven.

## Limitations

- Evidence is from Alex's Windows PC only.
- Manual Windows Settings removal and pairing were required for the clean
  baseline.
- Automated WinRT pairing failed.
- No physical HOTAS controls were moved.
- This run did not test a hard power-cycle.
- This run did not test a real app/game after reset.
- The stop/start advertising test is blocked by the current lack of a BLE
  persona stop/disconnect command.
- The explicit `persona_static_random_experimental` strategy remains
  experimental and non-default.
- Broad Windows compatibility, broad game compatibility, Xbox console support,
  proprietary Xbox Wireless support, physical HOTAS movement, final calibration
  quality, and durable BLE bond persistence are not claimed.
