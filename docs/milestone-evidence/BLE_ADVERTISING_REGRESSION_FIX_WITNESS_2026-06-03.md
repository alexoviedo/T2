# BLE Advertising Regression Fix Witness - 2026-06-03

Status: fix witness from Alex's Windows PC. This run isolated and fixed the
post-`v0.1.0-alpha` BLE advertising regression that prevented current firmware
advertisements from appearing over the air.

## Context

- Date/time: 2026-06-03 late evening Mountain time
- Commit at run start: `3e32cd64d2774672acb662ff38dde5d863ddd63d`
- Host OS report: `WindowsProduct=Windows 10 Home`,
  `DisplayVersion=25H2`, `CurrentBuildNumber=26200`
- Selected serial port: `COM3`
- Serial device: `USB-Enhanced-SERIAL CH343 (COM3)`,
  `USB\VID_1A86&PID_55D3\5B5E020088`
- Artifact directory:
  `target/ble-advertising-regression/ble_adv_regression_20260603_232730`

## Baseline

The target serial control plane was available on `COM3`. Before the fix, the
current firmware still had healthy target-side practical RJ12 USB topology but
was stuck in BLE error state:

```text
STATUS:ble=Error;profile=none;persona=generic_gamepad;bonds=false;
USB_STATUS:devices=3;interfaces=2;
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b10a|id=3,vid=044f,pid=b687
```

The previous firmware provenance diagnostic had already shown that the
published `v0.1.0-alpha` binary advertises on this same board and Windows BLE
watcher.

## Regression Isolation

A self-contained external hardware harness was created under:

```text
target/ble-advertising-regression/bisect_harness/ble_advertising_regression_test.py
```

The harness built a checked-out revision, flashed the ESP32-S3, sent
`START_BLE_GENERIC_GAMEPAD`, ran a native Windows BLE advertisement scan, and
classified the revision as:

- `0`: advertisement visible;
- `1`: advertisement not visible;
- `125`: skipped build/unsupported revision.

The source tag `v0.1.0-alpha` was checked out in a detached worktree at commit
`4b0020bb59dceae6a2fbfcf93555e77f7b7869bb`, matching the release manifest's
short `git_rev=4b0020b`. A source-built alpha firmware was built locally with
ESP-IDF v5.5.3, flashed, and tested:

```text
revision: 4b0020bb59dceae6a2fbfcf93555e77f7b7869bb
result: good_advertisement_visible
name: USB2BLE Gamepad
address: 90:70:69:07:0D:7E
hid_service_seen: true
total_advertisements: 2021
```

This proved the regression is in post-alpha source/config, not only in release
artifact provenance.

## Bisect Result

A path-constrained bisect covered firmware/platform/control/build paths between
`v0.1.0-alpha` and `3e32cd64d2774672acb662ff38dde5d863ddd63d`.

Key hardware results:

| Revision | Commit | Build | BLE watcher result |
| --- | --- | --- | --- |
| `4b0020b` | `docs: prepare v0.1.0-alpha release` | pass | good: `USB2BLE Gamepad` visible |
| `4d483c4` | `feat: Xbox` | pass | good: `USB2BLE Gamepad` visible |
| `2abc6ca` | `feat: Host-Compatible Axis Variant` | pass | good: `USB2BLE Gamepad` visible |
| `5bd7e21` | `chore: record Windows hardware bring-up diagnostic` | skip | unbuildable locally against ESP-IDF v5.5.3 because ESP-IDF struct fields were omitted |
| `fe3a4f5` | `fix: restore Windows USB host hub enumeration` | pass | bad: no `USB2BLE Gamepad` advertisement |

The first buildable bad commit was `fe3a4f5`. The causal regression was narrowed
to the preceding unbuildable/build-repair pair:

- `5bd7e21` removed explicit ESP Bluetooth controller config fields including
  `adv_en`, `connect_en`, `scan_en`, and related feature flags.
- `fe3a4f5` restored compilation by using `Default::default()` for the remaining
  ESP-IDF v5.5.3 struct fields, which left those feature fields at false/zero.

That explains the observed symptom: raw and HID advertisement payload
configuration returned success, but the controller never completed advertising
start successfully over the air.

## Fix

`crates/usb2ble-platform-esp32/src/ble_hid.rs` was changed to restore the
explicit ESP-IDF controller feature fields from the last known-good path while
keeping the newer USB host recovery, diagnostics, and persona code intact.

The fix restores explicit values for:

- `ble_llcp_disc_flag`;
- `run_in_flash`;
- `dtm_en`;
- `enc_en`;
- `qa_test`;
- `connect_en`;
- `scan_en`;
- `ble_aa_check`;
- `adv_en`.

It also explicitly keeps `sc_en: false` in the Bluedroid config instead of
leaving that field only to the default initializer.

## Fix Verification

The fixed current firmware built successfully using the Windows ESP32-S3 target
build path:

```text
cargo +esp build -Z build-std=std,panic_abort --locked --package usb2ble-fw --target xtensa-esp32s3-espidf
Finished `dev` profile [unoptimized + debuginfo]
```

Fixed ELF:

```text
path: C:\t2bis\bisect\xtensa-esp32s3-espidf\debug\usb2ble-fw
sha256: 7de415c65f39665ad443340b4074a8d004b84ff2a8cca1edaf0c38f7558d995d
```

Raw smoke verification:

```text
START_BLE_ADV_SMOKE_TEST BLE_SMOKE
BLE_SMOKE seen: true
address: 90:70:69:07:0D:7E
matched count: 208
total advertisements: 1809
```

Generic default verification:

```text
START_BLE_GENERIC_GAMEPAD
USB2BLE Gamepad seen: true
address: 90:70:69:07:0D:7E
matched count: 127
matched HID UUID: 00001812-0000-1000-8000-00805f9b34fb
total advertisements: 1792
```

Xbox persona advertisement verification:

```text
START_BLE_XBOX_CONTROLLER
Xbox Wireless Controller seen: true
address: 90:70:69:07:0D:7E
matched count: 129
matched HID UUID: 00001812-0000-1000-8000-00805f9b34fb
total advertisements: 1943
```

Final target probe:

```text
STATUS:ble=Advertising;profile=none;persona=xbox_wireless_controller;bonds=false;
USB_STATUS:devices=3;interfaces=2;
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b10a|id=3,vid=044f,pid=b687
last_adv_config_status: 0
last_scan_rsp_config_status: 0
last_adv_start_return: 0
last_adv_start_status: 0
state: Advertising
```

## Artifacts

Key artifacts under
`target/ble-advertising-regression/ble_adv_regression_20260603_232730`:

- `repo_state.txt`
- `baseline_serial_probe.txt`
- `source_v0.1.0-alpha_sourcebuilt_scan/result.json`
- `bisect_run_output.txt`
- `bisect_log.txt`
- `bisect/3e32cd6/result.json`
- `bisect/4d483c4/result.json`
- `bisect/5bd7e21/build_output.txt`
- `bisect/fe3a4f5/result.json`
- `bisect/2abc6ca/result.json`
- `fix_current_build_retry_warm_target.txt`
- `fix_verification/raw_smoke/summary.json`
- `fix_verification/generic_default/summary.json`
- `fix_verification/xbox/summary.json`
- `final_fixed_target_probe.txt`
- `ble_advertising_regression_summary.json`
- `ble_advertising_regression_summary.md`

## Conclusion

Result: pass for BLE advertising regression fix.

Current firmware again produces over-the-air advertisements visible to the
native Windows BLE watcher for raw smoke, Generic default, and Xbox persona
advertisement modes. This evidence only covers advertisement visibility and
target serial state. It does not prove controller pairing, host input delivery,
physical HOTAS input movement, external app behavior, stored bond behavior, or
calibration quality.

The next chunk may proceed to Windows Bluetooth pairing and host-visible
controller diagnostics, starting with Generic default and then Xbox, while
continuing to keep compatibility claims bounded by captured evidence.
