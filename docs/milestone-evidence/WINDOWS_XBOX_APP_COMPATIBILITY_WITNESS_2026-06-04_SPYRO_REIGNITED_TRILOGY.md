# Windows Xbox Spyro Witness - 2026-06-04

Status: one installed-game data point from Alex's Windows PC. With USB2BLE in
single-persona Xbox BLE-compatible mode, Windows kept XInput slot 0 connected
while Spyro Reignited Trilogy was running, target-side virtual Flight Pack Xbox
frames and deterministic Xbox reports moved XInput controls, and Alex observed
the game screen responding with controls moving around and different menu items
being selected.

This is not broad Windows compatibility, broad game compatibility, Xbox console
compatibility, proprietary Xbox Wireless compatibility, BLE bond persistence,
physical HOTAS movement, or final calibration evidence.

## Context

- Date/time: 2026-06-04 around 15:06-15:16 Mountain time.
- Repo/firmware commit at start: `af69375ae17e360f91d3f4377d255566f3f6d9fc`
- Branch: `main`
- CI gate: latest GitHub Actions run for `main` was green before hardware/app
  work: <https://github.com/alexoviedo/T2/actions/runs/26978224569>
- Windows host: Alex's Windows PC. Registry reported `Windows 10 Home`,
  display version `25H2`, build `26200.8457`.
- Selected serial port: `COM3`
- Serial device: WCH CH343, `USB\VID_1A86&PID_55D3\5B5E020088`
- App target: Spyro Reignited Trilogy, Store package
  `38985CA0.SpyroReignitedTrilogyGamePC_1.0.1.0_x64__5bkah9njm3e9g`
- Game process during witness: `Spyro-Win64-Shipping.exe`
- Primary artifact root:
  `target/windows-game-compatibility/spyro_reignited_trilogy_20260604_150634`
- Repo/app witness root:
  `target/windows-game-compatibility/windows_xbox_game_20260604_145314`

No firmware was flashed in this chunk. No physical HOTAS controls were moved.

## Repo And Validation Gate

The run started from clean, synced `main`:

```text
branch=main
HEAD=af69375ae17e360f91d3f4377d255566f3f6d9fc
working tree clean before helper/evidence changes
```

GitHub Actions for `main` was green before app work. Local no-hardware validation
passed before hardware/app work:

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

## Xbox BLE/XInput Baseline

The test used the explicit experimental identity strategy for the single Xbox
persona:

```text
strategy=persona_static_random_experimental
active_persona=xbox_wireless_controller
active_variant=xbox_compatibility
current_address=CB:B3:AE:FA:FC:EF
address_type=static_random
identity_applied=true
```

Windows state carried forward from the checked-in Xbox XInput witness:

- Windows paired/connected the device as `Xbox Wireless Controller`.
- Windows PnP/HID exposed HID `045e:0b13`.
- XInput slot 0 was connected.

The quick pre-app XInput sanity gate in this run passed:

| Scenario | XInput observation |
| --- | --- |
| `neutral` | slot 0 connected, buttons `0`, triggers `0/0` |
| `left_stick_right` | left thumb X reached `32767` |
| `right_stick_right` | right thumb X reached `32767` |
| `left_trigger_max` | left trigger reached `255` |
| `right_trigger_max` | right trigger reached `255` |
| `button_a` | buttons `4096` |
| `button_b` | buttons `8192` |

## Target Discovery

Installed target discovery found:

- Spyro Reignited Trilogy as a Store app.
- Steam installed at `C:\Program Files (x86)\Steam\steam.exe`.
- Condor 3 installed.
- Microsoft Flight Simulator 2024 installed but treated as heavyweight.
- `joy.cpl` available only as a fallback controller-panel target.

Spyro was selected as the first real installed-game target because it was already
installed and launchable without a sign-in, download, or update blocker during
this run.

## Spyro Launch

The app was launched through its Store app ID:

```text
shell:AppsFolder\38985CA0.SpyroReignitedTrilogyGamePC_5bkah9njm3e9g!Falcon.Binaries.Win64.Spyro.Win64.Shipping
```

Before the witness loop, Windows showed:

```text
ProcessName: Spyro-Win64-Shipping
MainWindowTitle: Spyro Reignited Trilogy
Path: C:\Program Files\WindowsApps\38985CA0.SpyroReignitedTrilogyGamePC_1.0.1.0_x64__5bkah9njm3e9g\Falcon\Binaries\Win64\Spyro-Win64-Shipping.exe
```

Computer Use automation was unavailable in this session with
`Computer Use native pipe path is unavailable`, so the allowed manual observation
fallback was used. Alex brought the Spyro window forward and observed the screen
while the virtual sequence ran.

## Virtual Xbox App Sequence

The helper `tools/windows_xbox_app_witness.py` imported the `flight-pack-xbox`
runtime config, enabled virtual input, started the bridge, and sampled XInput
while Spyro was open:

```text
GET_CONFIG_STATUS
CONFIG_STATUS:valid=true;source=runtime;persona=xbox_wireless_controller;profile=custom_runtime;mappings=18;import_active=false;last_error=none;

START_VIRTUAL_INPUT
PUBLISH_VIRTUAL_INPUT_FRAME neutral
START_BRIDGE
```

The virtual Flight Pack Xbox mapping under test:

- stick -> XInput left stick
- RJ12 rudder -> XInput right stick X
- left toe -> left trigger
- right toe -> right trigger
- TWCS throttle intentionally unmapped for this Xbox practical profile

The witness captured 139 XInput samples. XInput slot 0 stayed connected
throughout the run.

| Virtual scenario | XInput observation |
| --- | --- |
| `neutral` | buttons `0`, triggers `0/0`, sticks near neutral |
| `stick_left` | left thumb X reached `-32768` |
| `stick_right` | left thumb X reached `32767` |
| `stick_forward` | left thumb Y reached `32767` |
| `stick_back` | left thumb Y reached `-32768` |
| `rudder_left` | right thumb X reached `32767` |
| `rudder_right` | right thumb X reached `-32768` |
| `left_toe_pressed` | left trigger reached `255` |
| `left_toe_released` | left trigger returned to `0` |
| `right_toe_pressed` | right trigger reached `255` |
| `right_toe_released` | right trigger returned to `0` |

After the virtual mapping sequence, the helper stopped the bridge and used
deterministic Xbox reports for menu-style controls:

| Deterministic report | XInput observation |
| --- | --- |
| `button_a` | buttons included `4096` |
| `button_b` | buttons included `8192` |
| `hat_up` | buttons included `1` |
| `hat_down` | buttons included `2` |
| `hat_left` | buttons included `4` |
| `hat_right` | buttons included `8` |

Overall XInput ranges from the run:

```text
left_thumb_x_min=-32768
left_thumb_x_max=32767
left_thumb_y_min=-32768
left_thumb_y_max=32767
right_thumb_x_min=-32768
right_thumb_x_max=32767
left_trigger_max=255
right_trigger_max=255
buttons_observed=0,1,2,4,8,4096,8192
```

Bridge status after the run was healthy:

```text
BRIDGE_STATUS:enabled=false;persona=xbox_wireless_controller;rate_hz=50;last_publish_ms=4851933;published=245;skipped_duplicate=1251;skipped_rate=0;skipped_not_connected=0;skipped_not_ready=0;last_error=none;
```

## App Observation

Alex's operator observation:

```text
Alex observed the controls moving around and different menu items being selected during the virtual Xbox/XInput witness sequence.
```

This is the app-visible part of the witness. The serial and XInput artifacts
show that USB2BLE was publishing virtual Xbox-path input at the same time, and
the process snapshots show Spyro remained running before and after the sequence.

## Artifacts

- `target/windows-game-compatibility/windows_xbox_game_20260604_145314/repo_state.txt`
- `target/windows-game-compatibility/windows_xbox_game_20260604_145314/branch_state.txt`
- `target/windows-game-compatibility/windows_xbox_game_20260604_145314/ci_status.txt`
- `target/windows-game-compatibility/windows_xbox_game_20260604_145314/phase1_local_validation.txt`
- `target/windows-game-compatibility/windows_xbox_game_20260604_145314/serial_discovery.txt`
- `target/windows-game-compatibility/windows_xbox_game_20260604_145314/target_baseline.txt`
- `target/windows-game-compatibility/windows_xbox_game_20260604_145314/usb_topology.txt`
- `target/windows-game-compatibility/windows_xbox_game_20260604_145314/xinput_baseline/`
- `target/windows-game-compatibility/windows_xbox_game_20260604_145314/target_discovery/`
- `target/windows-game-compatibility/spyro_reignited_trilogy_20260604_150634/launch_log.txt`
- `target/windows-game-compatibility/spyro_reignited_trilogy_20260604_150634/pre_witness_process_state.txt`
- `target/windows-game-compatibility/spyro_reignited_trilogy_20260604_150634/spyro_virtual_witness_console.txt`
- `target/windows-game-compatibility/spyro_reignited_trilogy_20260604_150634/post_witness_process_state.txt`
- `target/windows-game-compatibility/spyro_reignited_trilogy_20260604_150634/host_version_and_final_target_status.txt`
- `target/windows-game-compatibility/spyro_reignited_trilogy_20260604_150634/operator_observation.md`
- `target/windows-game-compatibility/spyro_reignited_trilogy_20260604_150634/virtual_xbox_sequence/windows_xbox_app_witness_20260604T210829Z/summary.json`
- `target/windows-game-compatibility/spyro_reignited_trilogy_20260604_150634/virtual_xbox_sequence/windows_xbox_app_witness_20260604T210829Z/serial_transcript.json`
- `target/windows-game-compatibility/spyro_reignited_trilogy_20260604_150634/virtual_xbox_sequence/windows_xbox_app_witness_20260604T210829Z/xinput_samples.jsonl`

## Conclusion

For the single-persona Xbox BLE-compatible path on Alex's Windows PC:

- Spyro Reignited Trilogy launched and stayed running during the witness.
- USB2BLE remained connected as `xbox_wireless_controller` at
  `CB:B3:AE:FA:FC:EF`.
- Windows XInput slot 0 stayed connected through the sequence.
- Virtual Flight Pack Xbox mapping drove left stick, right stick X, and trigger
  changes through XInput while Spyro was open.
- Deterministic Xbox reports drove A, B, and D-pad values through XInput while
  Spyro was open.
- Alex observed controls moving and menu items being selected in Spyro during
  the virtual sequence.

This is an installed-game compatibility data point for Spyro Reignited Trilogy
on this one Windows PC. It is not a broad game compatibility claim.

## Limitations

- Evidence is from Alex's Windows PC only.
- Spyro observation was operator-reported because Computer Use automation was
  unavailable; no automated screenshot capture is included.
- No physical HOTAS controls were moved.
- Virtual input evidence does not prove physical Flight Pack movement in Spyro.
- The run does not prove final calibration quality, deadzone feel, or gameplay
  usability.
- Manual Windows pairing/cache setup had been required in the preceding Xbox
  witness; this run does not prove BLE bond persistence or reconnect behavior.
- The explicit `persona_static_random_experimental` strategy remains
  experimental and non-default.
- Xbox console compatibility and proprietary Xbox Wireless compatibility are
  not claimed.
- Broad Windows compatibility and broad game compatibility are not claimed.
