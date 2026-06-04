# Firmware Provenance BLE Advertising Diagnostic - 2026-06-03

Status: diagnostic evidence from Alex's Windows PC. This run compared a
published `v0.1.0-alpha` firmware image, the public Pages/current firmware
image, and a freshly rebuilt Windows-local firmware image on the same ESP32-S3
and Windows BLE watcher.

## Context

- Date/time: 2026-06-03 late evening Mountain time
- Commit at run start: `daba7409be5c452a8a2016dfc1d5c4384ee8499f`
- Host OS report: `WindowsProduct=Windows 10 Home`,
  `DisplayVersion=25H2`, `CurrentBuildNumber=26200`
- Selected serial port: `COM3`
- Serial device: `USB-Enhanced-SERIAL CH343 (COM3)`,
  `USB\VID_1A86&PID_55D3\5B5E020088`
- ESP32-S3 MAC from flash transcript: `90:70:69:07:0d:7c`
- Artifact directory:
  `target/firmware-provenance-ble/firmware_provenance_20260603_224817`

## Baseline

The ESP32-S3 serial control plane was autodetected on `COM3`. The current
Windows-local firmware restored target-side practical RJ12 USB topology after
the provenance flashes:

```text
USB_STATUS:devices=3;interfaces=2;
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b10a|id=3,vid=044f,pid=b687
```

The native Windows BLE watcher was active during every scan and captured
between 1517 and 1850 ambient advertisements per 30-second run.

## Firmware Candidates

| Candidate | Source | SHA256 | Flash method | Result |
| --- | --- | --- | --- | --- |
| Published `v0.1.0-alpha` merged image | `https://github.com/alexoviedo/T2/releases/download/v0.1.0-alpha/usb2ble-fw-esp32s3-merged.bin` | `a797999edba2fa38a6909369b187964afa1716cccc48bb1a5bacf08d1afa23a7` | `espflash write-bin --chip esp32s3 --port COM3 0x0 ...` from release manifest | Advertised `USB2BLE Gamepad` after `START_BLE_GENERIC_GAMEPAD` |
| Public Pages/current merged image | `https://alexoviedo.github.io/T2/firmware/usb2ble-fw-esp32s3-merged.bin` via `manifest.json` | `d914ff9cb3cbba62242816565253b34daf37824ce30f8eb00d03301b6e6a40a8` | `espflash write-bin --chip esp32s3 --port COM3 0x0 ...` from Pages manifest | Did not advertise in auto, raw-smoke, or fresh Generic runs |
| Windows-local current ELF | `C:\t2t_v553\xtensa-esp32s3-espidf\debug\usb2ble-fw` | `a73139585864a21af5b1fe6520694bdbb78d0dc17557e7f40f47d1455ffc9611` | `espflash flash --port COM3 ...` after local `cargo +esp build` | Did not advertise in raw-smoke or fresh Generic runs |

GitHub Actions latest artifact metadata was publicly readable for run
`26930957711` on commit `daba7409be5c452a8a2016dfc1d5c4384ee8499f`, and the
`usb2ble-fw-esp32s3-flashable` artifact digest was listed as
`sha256:cae7cbe6f251e73aa0978280375558d3f63f123ec921ee36512d916551629687`.
The artifact archive download returned `401 Unauthorized` without `gh` or
GitHub authentication, so that Actions zip was not flashed in this run. The
public Pages/current firmware was used as the current published comparison.

## Release Result

The release image flashed successfully. It did not auto-advertise while idle,
which is consistent with the target reporting `persona=none`.

After `START_BLE_GENERIC_GAMEPAD`, Windows saw the published alpha Generic
advertisement:

```text
matched_local_names: USB2BLE Gamepad
matched_addresses: 90:70:69:07:0D:7E
matched_service_uuids: 00001812-0000-1000-8000-00805f9b34fb
matched_advertisements: 306
total_advertisements: 1850
unique_addresses: 47
```

The release serial protocol did not support `LIST_BLE_COMPAT_VARIANTS`, which
returned `ERROR:Generic`. That is not treated as a release advertising failure.

## Pages/Current Result

The Pages/current image flashed successfully and responded to the current serial
protocol. The auto scan did not see `BLE_SMOKE`, `USB2BLE Gamepad`,
`USB2BLE Gamepad U6`, or `Xbox Wireless Controller`.

Raw smoke on the Pages/current image reproduced the known current failure:

```text
START_BLE_ADV_SMOKE_TEST BLE_SMOKE
last_adv_raw_config_status: 0
last_adv_start_return: 0
last_adv_start_status: 13
state: Error
```

Windows saw 1679 ambient advertisements in that scan, but no `BLE_SMOKE` or
`USB2BLE Gamepad`.

A fresh-flashed Pages/current Generic run returned
`BLE_ACTION:action=start_generic_gamepad;state=Advertising`, but Windows saw
1602 ambient advertisements and zero matching `USB2BLE Gamepad` or
`USB2BLE Gamepad U6` advertisements.

## Windows-Local Result

The Windows-local firmware rebuilt cleanly with the ESP target build path:

```text
cargo +esp build -Z build-std=std,panic_abort --locked --package usb2ble-fw --target xtensa-esp32s3-espidf
Finished `dev` profile [unoptimized + debuginfo]
```

The freshly built ELF flashed successfully. Raw smoke did not appear in the
Windows watcher. A fresh local Generic run also did not appear in the Windows
watcher.

Final target diagnostics after the local Generic run:

```text
GET_STATUS
STATUS:ble=Error;profile=none;persona=generic_gamepad;bonds=false;

GET_BLE_ADVERTISING_EVENTS
last_adv_config_status: 0
last_scan_rsp_config_status: 0
last_adv_start_return: 0
last_adv_start_status: 13
owner: hid
state: Error
```

## Source/Build Comparison

Release-to-current diff artifacts were saved at:

- `target/firmware-provenance-ble/ble_hid_release_to_head.diff`
- `target/firmware-provenance-ble/build_config_release_to_head.diff`

The build script delta is small: current scripts pin
`ESP_IDF_VERSION=v5.5.3` and `ESP_IDF_SDKCONFIG_DEFAULTS=sdkconfig.defaults`;
`sdkconfig.defaults` itself did not appear in that release-to-current build
diff.

The largest functional delta is
`crates/usb2ble-platform-esp32/src/ble_hid.rs`. Since `v0.1.0-alpha`, that file
added compatibility variants, raw smoke diagnostics, richer GAP event tracking,
stop/start ownership state, and additional advertising payload layouts. The
release Generic path used the simpler HIDD start callback plus
`ADV_TYPE_IND` advertising path and is proven visible on this Windows scan.

## Interpretation

This provenance A/B changes the failure classification:

- the ESP32-S3 BLE radio and antenna can advertise on this board;
- the Windows BLE watcher can see USB2BLE advertisements from this board;
- flashing published firmware from Windows works;
- the current Pages/current and Windows-local firmware do not advertise for the
  tested raw-smoke or Generic paths;
- the current blocker is therefore a post-alpha firmware code/config regression
  or current build provenance issue, not a board/radio failure and not a Windows
  scanner failure.

The C ESP-IDF minimal example was not needed in this chunk because the
published alpha image already provided a known-good over-the-air advertiser on
the same board and scanner.

## Artifacts

Key artifacts under
`target/firmware-provenance-ble/firmware_provenance_20260603_224817`:

- `repo_state.txt`
- `environment_summary.txt`
- `serial_port_discovery.txt`
- `port_probe_results.txt`
- `firmware_artifacts/release_api.txt`
- `firmware_artifacts/release_v0.1.0-alpha_manifest.txt`
- `firmware_artifacts/pages_manifest.txt`
- `firmware_artifacts/actions_latest_artifacts.json`
- `firmware_artifacts/download_failures.txt`
- `firmware_artifacts/artifact_hashes_all.json`
- `release_v0.1.0_alpha_auto/summary.json`
- `release_v0.1.0_alpha_start_generic/summary.json`
- `pages_latest_auto/summary.json`
- `pages_latest_raw_smoke/summary.json`
- `pages_latest_start_generic_fresh/summary.json`
- `local_windows_build.txt`
- `local_windows_raw_smoke/summary.json`
- `local_windows_start_generic_fresh/summary.json`
- `final_local_target_probe.txt`
- `firmware_provenance_summary.json`
- `firmware_provenance_summary.md`

## Conclusion

Result: diagnostic pass for provenance isolation.

The next chunk should bisect or surgically compare the post-alpha BLE
advertising path against `v0.1.0-alpha`, starting with
`crates/usb2ble-platform-esp32/src/ble_hid.rs` advertising ownership/state and
the release-proven HIDD `ADV_TYPE_IND` start path. Pairing, controller API,
XInput, browser Gamepad API, and external app tests should still wait until
current firmware advertisements are visible over the air.

Limitations: this evidence proves advertisement visibility for the published
alpha Generic path on this PC and negative advertisement results for the tested
current images. It does not prove controller pairing, host input delivery,
physical HOTAS input movement, external app behavior, stored bond behavior, or
calibration quality.
