# Minimal BLE Advertising Isolation - 2026-06-03

Status: diagnostic failure evidence from Alex's Windows PC. A standalone
ESP32-S3 firmware target that initializes only NVS, BLE controller, Bluedroid,
one GAP callback, and one raw advertisement reproduced the same asynchronous
GAP advertising-start status `13` seen in the full USB2BLE firmware. Local
ESP-IDF v5.5.3 bindings identify status `13` as `ESP_BT_STATUS_PENDING`.

## Context

- Date/time: 2026-06-03 evening Mountain time
- Commit at run start: `fe0b6ad772f424b168ab63f243262a69484d4433`
- Host OS report: `WindowsProduct=Windows 10 Home`, build `26200`
- ESP-IDF version: `v5.5.3`
- Selected serial port: `COM3`
- Serial device: `USB-Enhanced-SERIAL CH343 (COM3)`,
  `USB\VID_1A86&PID_55D3\5B5E020088`
- ESP32-S3 MAC from flash transcript: `90:70:69:07:0d:7c`
- Artifact directory:
  `target/minimal-ble-advertising/minimal_ble_adv_20260603_222021`

## Baseline

Before flashing the minimal firmware, the normal USB2BLE firmware responded on
`COM3` and reported the expected target-side practical RJ12 topology:

```text
USB_STATUS:devices=3;interfaces=2;
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b10a|id=3,vid=044f,pid=b687
```

The existing USB2BLE BLE diagnostic still showed the previous raw-smoke
advertising failure state:

```text
last_adv_raw_config_status=0
last_adv_start_return=0
last_adv_start_status=13
```

## Minimal Firmware

A standalone diagnostic binary was added:

```text
crates/usb2ble-fw/src/bin/minimal_ble_adv.rs
```

This binary does not initialize USB2BLE USB host, storage, runtime config,
mapping, bridge, personas, or `esp_hidd_dev_init`. It uses the same ESP-IDF
v5.5.3 Windows build path and performs only:

1. NVS init.
2. Classic BT memory release.
3. BLE controller init/enable.
4. Bluedroid init/enable.
5. GAP callback registration.
6. Raw advertising payload config.
7. Advertising start from the firmware task loop after raw config callback
   success.

Payload:

```text
Flags: 0x06
Complete Local Name: BLE_SMOKE
```

## Minimal Result

The minimal binary built and flashed successfully:

```text
Image: C:\t2t_v553\xtensa-esp32s3-espidf\debug\minimal_ble_adv
App/part. size: 1,630,000/16,384,000 bytes, 9.95%
```

Representative serial status over the 30-second capture:

```text
MIN_ADV:status config_ready=1 start_requested=1 started=0 failed=1 config_done=1 start_done=1 last_event=6 set_name_ret=0 config_ret=0 start_ret=0 config_status=0 start_status=13 controller=2 bluedroid=2
```

Interpretation:

- BLE controller reached enabled state.
- Bluedroid reached enabled state.
- Raw advertising config returned `0` and callback status `0`.
- `esp_ble_gap_start_advertising` immediate return was `0`.
- Async GAP advertising-start completion status was `13`.
- The status stayed failed for the serial capture window.

## Windows Watcher

The native Windows BLE watcher remained active:

```text
total_advertisements=1533
unique_addresses=47
BLE_SMOKE local name seen=false
BLE_SMOKE raw name bytes seen=false
```

The scanner saw ambient BLE traffic but did not see `BLE_SMOKE`.

## Restored USB2BLE Check

After the minimal run, full USB2BLE firmware was rebuilt and flashed back to the
board. USB2BLE serial control and target USB topology recovered:

```text
USB_STATUS:devices=3;interfaces=2;
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b10a|id=3,vid=044f,pid=b687
```

A short restored-firmware raw smoke confirmation with `BLE_SMOKE` reproduced the
same pattern:

```text
adv_config_complete_status=0
adv_start_return=0
adv_start_complete_status=13
windows_watcher_seen=false
```

## Classification

Result: fail at `target_ble_stack_start`, below USB2BLE app, HID, persona,
mapping, bridge, and Windows controller API layers.

This run narrows away:

- USB2BLE USB host initialization/state ownership.
- USB2BLE bridge/persona/mapping behavior.
- `esp_hidd_dev_init` or HIDD advertising ownership.
- Generic/Xbox descriptor or report layout.
- Windows pairing, XInput, browser Gamepad API, or app behavior.

Remaining plausible layers:

- ESP-IDF v5.5.3 Bluedroid/controller advertising-start behavior or sdkconfig.
- Rust `esp-idf-sys` FFI/binding usage for this API path.
- ESP32-S3 board/radio/controller state.
- A still-unresolved `ESP_BT_STATUS_PENDING` path that did not transition to
  success during the observed window.

## Artifacts

Key artifacts under
`target/minimal-ble-advertising/minimal_ble_adv_20260603_222021`:

- `repo_state.txt`
- `environment_summary.txt`
- `serial_port_discovery.txt`
- `port_probe_results.txt`
- `usb2ble_ble_state_before_minimal.txt`
- `minimal_firmware_build_clean.txt`
- `minimal_firmware_flash.txt`
- `minimal_smoke/serial_log.txt`
- `minimal_smoke/windows_ble_scan/scan_all.jsonl`
- `minimal_smoke/windows_ble_scan/scan_summary.json`
- `minimal_smoke/ble_smoke_scan_check.json`
- `minimal_smoke/summary.md`
- `minimal_vs_usb2ble_diff.md`
- `usb2ble_full_firmware_restore_build.txt`
- `usb2ble_full_firmware_restore_flash.txt`
- `post_restore_usb2ble_probe.txt`
- `raw_smoke_attempt_1/raw_smoke_summary.json`

## Limitations

This is diagnostic failure evidence. It does not establish successful BLE
advertising, pairing, controller API exposure, external app behavior, physical
HOTAS movement, stored-bond behavior, or calibrated Flight Pack behavior.

HID persona advertisement matrix testing was not rerun because raw standalone
advertising did not start successfully.
