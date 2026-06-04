# Windows BLE Advertising Lab - 2026-06-03

Status: BLE advertising isolation diagnostic on Alex's Windows PC. This
evidence proves that Windows' native BLE advertisement watcher was receiving
ambient advertisements and that USB2BLE's raw GAP smoke advertisement plus
Generic/Xbox HID persona advertisement paths all failed at the target GAP
advertising-start layer with status `13` (`0x0d`, command disallowed). It does
not prove Windows controller compatibility, game/app compatibility, physical
HOTAS movement, BLE bond persistence, broad host support, Xbox console support,
proprietary Xbox Wireless support, or final Flight Pack calibration.

## Summary

Codex autodetected the ESP32-S3 serial/programming device as `COM3`
(`USB-Enhanced-SERIAL CH343 (COM3)`,
`USB\VID_1A86&PID_55D3\5B5E020088`) and confirmed the target control plane was
healthy. After the hardware had been unplugged/replugged, the recovered
practical RJ12 topology was still present:

```text
USB_STATUS:devices=3;interfaces=2;
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b10a|id=3,vid=044f,pid=b687
```

A native Windows BLE advertisement watcher was added using
`Windows.Devices.Bluetooth.Advertisement.BluetoothLEAdvertisementWatcher`.
Baseline and per-mode active scans captured ambient BLE traffic, so the Windows
scanner path was alive.

A diagnostic-only raw GAP smoke advertisement mode was also added:

```text
START_BLE_ADV_SMOKE_TEST USB2BLE_ADV_TEST
STOP_BLE_ADV_SMOKE_TEST
GET_BLE_ADV_SMOKE_TEST_STATUS
GET_BLE_ADVERTISING_EVENTS
```

The raw smoke path and all HID persona paths reached GAP advertisement
configuration successfully, then received `adv_start_complete` with status `13`.
Windows scans saw zero USB2BLE, Xbox, gamepad-name, or HID-service matches.

## Context

- Date/time: 2026-06-03T20:44 through 2026-06-03T21:07 Mountain time
- Commit at run start: `802d3adee8ec657c8b9b0b1e81201b9995a8dad3`
- Host OS report: `WindowsProductName=Windows 10 Home`,
  `DisplayVersion=25H2`, `CurrentBuildNumber=26200`
- Selected serial port: `COM3`
- Serial device evidence: `USB-Enhanced-SERIAL CH343 (COM3)`,
  `USB\VID_1A86&PID_55D3\5B5E020088`, manufacturer `wch.cn`
- ESP32-S3 MAC from flash transcript: `90:70:69:07:0d:7c`
- Firmware image:
  `C:\t2t_v553\xtensa-esp32s3-espidf\debug\usb2ble-fw`
- Artifact directory:
  `target/windows-ble-advertising/ble_adv_lab_20260603_204438`

## Tooling Added

`tools/windows_ble_advertising_watcher.py` captures native Windows BLE
advertisement events without filtering by default. It records:

- timestamp and Bluetooth address,
- address type,
- RSSI,
- advertisement type and connectability/scannability flags,
- local name,
- service UUIDs,
- raw data-section bytes,
- manufacturer data,
- USB2BLE/Xbox/gamepad/HID match predicates.

The tool writes:

- `scan_all.jsonl`
- `scan_summary.json`
- `scan_all.txt`

It exits successfully even when USB2BLE is not seen, with summary fields such as
`usb2ble_seen`, `xbox_seen`, `hid_service_seen`, `total_advertisements`, and
`unique_addresses`.

Target diagnostics added for this lab report GAP/HID lifecycle counters and raw
smoke advertisement status. They are diagnostic-only and do not alter the
default Generic/Xbox persona identities or report maps.

## Matrix Result

Final matrix artifacts are under:

```text
target/windows-ble-advertising/ble_adv_lab_20260603_204438/matrix_state_fix
```

| Mode | GAP config | GAP start event | Last start status | Windows watcher | Failure layer |
| --- | --- | --- | --- | --- | --- |
| raw smoke `USB2BLE_ADV_TEST` | `last_adv_config_status=0` | seen | `13` | 1536 advertisements, 48 unique addresses, 0 USB2BLE/HID matches | `target_ble_stack_start` |
| `generic_default` | `last_adv_config_status=0`, `last_scan_rsp_config_status=0` | seen | `13` | 1349 advertisements, 39 unique addresses, 0 matches | `target_ble_stack_start` |
| `generic_hogp_strict` | `last_adv_config_status=0`, `last_scan_rsp_config_status=0` | seen | `13` | 1387 advertisements, 42 unique addresses, 0 matches | `target_ble_stack_start` |
| `generic_unsigned_6axis` | `last_adv_config_status=0`, `last_scan_rsp_config_status=0` | seen | `13` | 1388 advertisements, 44 unique addresses, 0 matches | `target_ble_stack_start` |
| `xbox_compatibility` | `last_adv_config_status=0`, `last_scan_rsp_config_status=0` | seen | `13` | 1444 advertisements, 42 unique addresses, 0 matches | `target_ble_stack_start` |

Representative raw smoke target output:

```text
BLE_ADV_SMOKE_TEST_STATUS_JSON:{"active":false,...,"last_adv_config_status":0,"last_adv_start_status":13,...}
BLE_ADVERTISING_EVENTS_JSON:{"adv_config_done":1,"adv_start_complete":1,"last_adv_config_status":0,"last_adv_start_status":13,"state":"Error"}
```

Representative Generic default target output:

```text
BLE_ACTION:action=start_generic_gamepad;state=Error;
BLE_ADVERTISING_INFO:persona=generic_gamepad;state=Error;variant=generic_default;device_name=USB2BLE Gamepad;...
BLE_ADVERTISING_EVENTS_JSON:{"adv_config_done":1,"scan_rsp_config_done":1,"adv_start_complete":1,"last_adv_config_status":0,"last_scan_rsp_config_status":0,"last_adv_start_status":13,"state":"Error"}
```

## Interpretation

The blocker is below HID descriptor layout and below Windows Bluetooth Settings
UI filtering:

- Windows native scanning is alive because each scan captured 1349-1536 ambient
  advertisements.
- The raw smoke advertisement bypassed HID/persona setup and still failed with
  GAP advertising-start status `13`.
- Generic default, Generic HOGP-strict, Generic unsigned six-axis, and Xbox all
  failed at the same GAP advertising-start layer.
- Windows did not see USB2BLE because the target did not successfully start
  advertising over the air.

An iPhone/manual scanner step was not requested because independent scanner
evidence is not useful until the target reports successful raw GAP advertising
start.

## Artifacts

Key artifacts under
`target/windows-ble-advertising/ble_adv_lab_20260603_204438`:

- `repo_state.txt`
- `environment_summary.txt`
- `serial_discovery.txt`
- `target_status.txt`
- `windows_bluetooth_state.txt`
- `windows_ble_scan_baseline/scan_summary.json`
- `target_build_ble_adv_lab_xtensa.txt`
- `flash_diagnostic_firmware_xtensa/flash_output.txt`
- `post_diagnostic_flash_recheck/target_status_topology_poll.txt`
- `matrix_state_fix/matrix_summary.json`
- `matrix_state_fix/<mode>/serial_transcript_start.txt`
- `matrix_state_fix/<mode>/serial_transcript_after_scan.txt`
- `matrix_state_fix/<mode>/windows_ble_scan/scan_all.jsonl`
- `matrix_state_fix/<mode>/windows_ble_scan/scan_summary.json`
- `ble_advertising_lab_summary.json`
- `ble_advertising_lab_summary.md`

## Conclusion

Result: fail/blocked at `target_ble_stack_start`.

The next chunk should investigate why ESP-IDF/Bluedroid returns GAP advertising
start complete status `13` for both raw GAP and HID persona advertising on this
Windows-flashed ESP32-S3 image. Pairing, Gamepad API, XInput, browser, and
game/app tests should wait until raw GAP advertising starts successfully.
