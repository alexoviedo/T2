# BLE Advertising Start Diagnostic - 2026-06-03

Status: diagnostic evidence from Alex's Windows PC. This run did not fix BLE
advertising start. It narrowed the blocker to ESP-IDF/Bluedroid GAP advertising
start completion reporting status `13`, which the local ESP-IDF bindings define
as `ESP_BT_STATUS_PENDING`. The limitations are listed in the conclusion.

## Context

- Date/time: 2026-06-03 evening Mountain time
- Commit at run start: `77269828cebbeb13b72e444aa5d909a030406e93`
- Host OS report: `WindowsProduct=Windows 10 Home`,
  `DisplayVersion=25H2`, `CurrentBuildNumber=26200`
- Selected serial port: `COM3`
- Serial device: `USB-Enhanced-SERIAL CH343 (COM3)`,
  `USB\VID_1A86&PID_55D3\5B5E020088`
- ESP32-S3 MAC from flash transcript: `90:70:69:07:0d:7c`
- Firmware image:
  `C:\t2t_v553\xtensa-esp32s3-espidf\debug\usb2ble-fw`
- Artifact directory:
  `target/ble-advertising-start-fix/ble_adv_start_fix_20260603_212610`

## Baseline

The ESP32-S3 serial control plane was autodetected on `COM3`. After flash and a
short USB host settle period, the target-side practical RJ12 topology was
healthy:

```text
USB_STATUS:devices=3;interfaces=2;
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b10a|id=3,vid=044f,pid=b687
```

## Status 13 Analysis

Local generated ESP-IDF bindings identify callback status value `13` as:

```text
C:\t2t_v553\xtensa-esp32s3-espidf\debug\build\esp-idf-sys-b0655a4f0869dbee\out\bindings.rs
pub const esp_bt_status_t_ESP_BT_STATUS_PENDING: esp_bt_status_t = 13;
```

This corrects the prior shorthand interpretation. The target callback is not
reporting HCI command-disallowed; it is reporting `ESP_BT_STATUS_PENDING`.

## Changes Tested

Diagnostic-only target changes were made to the raw GAP smoke path:

- raw advertisement payload configuration with
  `esp_ble_gap_config_adv_data_raw`;
- callback-driven wait for raw advertising config completion before start;
- skip unnecessary idle `esp_ble_gap_stop_advertising` before start;
- extra GAP diagnostics for immediate API returns, callback statuses, owner,
  smoke state, advertisement parameters, and last GAP event/status;
- three raw smoke modes selected by diagnostic smoke-test name:
  connectable primary-only, scan-response name, and non-connectable
  primary-only;
- a final experiment moving the actual start request out of the GAP callback
  path and into the firmware task/control-plane status path.

`tools/ble_advertising_start_diagnosis.py` was added to autodetect the serial
port, start raw smoke advertising, poll target diagnostics, run the native
Windows BLE watcher, stop the smoke advertisement, and write a summary.

## Experiment Matrix

| Attempt | Mode | Config result | Start immediate return | Start callback status | Windows watcher | Result |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | connectable raw, callback-driven start | raw config status `0` | `0` | `13` | 1315 advertisements, 0 USB2BLE matches | fail |
| 2 | connectable raw, idle stop skipped | raw config status `0` | `0` | `13` | 1303 advertisements, 0 USB2BLE matches | fail |
| 3 | connectable primary-only | raw config status `0` | `0` | `13` | 1055 advertisements, 0 USB2BLE matches | fail |
| 4 | scannable, flags primary + name scan response | raw config status `0`, scan response status `0` | `0` | `13` | 1116 advertisements, 0 USB2BLE matches | fail |
| 5 | non-connectable primary-only | raw config status `0` | `0` | `13` | 1100 advertisements, 0 USB2BLE matches | fail |
| 6 | connectable raw, start outside GAP callback | raw config status `0` | `0` | `13` | 1253 advertisements, 0 USB2BLE matches | fail |

Representative target output from attempt 6:

```text
BLE_ADVERTISING_EVENTS_JSON:{"owner":"raw_smoke","smoke_mode":"connectable","adv_raw_config_done":1,"adv_start_complete":1,"last_adv_raw_config_status":0,"last_adv_start_return":0,"last_adv_start_status":13,"smoke_state":"starting","state":"Error",...}
```

Representative Windows watcher result:

```text
"scanner": "windows_winrt_bluetooth_le_advertisement_watcher"
"total_advertisements": 1253
"unique_addresses": 44
"usb2ble_seen": false
"hid_service_seen": false
"watcher_final_status": "STOPPED"
```

## Interpretation

The blocker remains `target_ble_stack_start`:

- raw GAP payload configuration succeeds;
- the immediate `esp_ble_gap_start_advertising` return is `ESP_OK`;
- the asynchronous advertising-start completion status is consistently `13`
  (`ESP_BT_STATUS_PENDING`);
- the failure occurs before HID persona advertising, pairing, Windows HID,
  XInput, browser Gamepad API, or game/app testing can be meaningful;
- Windows BLE scanning is alive because every run captured more than 1000
  ambient advertisements.

The HID persona matrix was not rerun in this chunk because raw GAP smoke
advertising never reached successful start.

## Artifacts

Key artifacts under
`target/ble-advertising-start-fix/ble_adv_start_fix_20260603_212610`:

- `repo_state.txt`
- `environment_summary.json`
- `status_13_analysis.md`
- `esp_target_build_after_fix.txt`
- `flash_after_fix.txt`
- `post_flash_target_probe.txt`
- `esp_target_build_smoke_modes.txt`
- `flash_smoke_modes.txt`
- `usb_topology_repoll_after_smoke_modes_flash.txt`
- `esp_target_build_start_outside_gap_cb.txt`
- `flash_start_outside_gap_cb.txt`
- `post_start_outside_gap_cb_probe.txt`
- `raw_smoke_attempt_1/raw_smoke_summary.json`
- `raw_smoke_attempt_2/raw_smoke_summary.json`
- `raw_smoke_attempt_3/raw_smoke_summary.json`
- `raw_smoke_attempt_4/raw_smoke_summary.json`
- `raw_smoke_attempt_5/raw_smoke_summary.json`
- `raw_smoke_attempt_6/raw_smoke_summary.json`

## Conclusion

Result: fail/blocked at `target_ble_stack_start`.

The next chunk should inspect ESP-IDF/Bluedroid controller and GAP state around
advertising start, with focus on why the async start-complete event reports
`ESP_BT_STATUS_PENDING` after successful raw payload config and immediate start
return. Pairing, Gamepad API, XInput, browser, and game/app tests should still
wait until raw GAP advertising starts successfully.
