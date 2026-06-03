# Windows USB Host Topology Witness - 2026-06-03

Status: Windows target USB host topology recovery witness. This evidence proves
that Alex's Windows build/flash path can produce firmware that enumerates the
HooToo hub plus the practical RJ12 Flight Pack downstream devices on the
ESP32-S3 USB host path. It does not prove Windows controller compatibility,
game/app compatibility, physical HOTAS movement, BLE bond persistence, broad
host support, or final Flight Pack calibration.

## Summary

Codex autodetected the ESP32-S3 serial/programming device as `COM3` from
Windows PnP (`USB-Enhanced-SERIAL CH343 (COM3)`,
`USB\VID_1A86&PID_55D3\5B5E020088`, manufacturer `wch.cn`) and confirmed that
the USB2BLE control plane responded.

The baseline firmware on the target reported ESP-IDF `v5.2.3` and enumerated
only the HooToo hub (`2109:2813`). A clean Windows target build was then run
with `ESP_IDF_VERSION=v5.5.3` and the checked-in `sdkconfig.defaults`, producing
a generated sdkconfig with USB hub support enabled. After flashing that build,
the ESP32-S3 enumerated the expected practical RJ12 topology:

```text
USB_STATUS:devices=3;interfaces=2;
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b10a|id=3,vid=044f,pid=b687
```

No manual physical cable, hub power, or HOTAS control movement action was
requested for this recovery.

## Context

- Date/time: 2026-06-03T22:51Z through 2026-06-03T23:05Z
- Commit at run start: `5bd7e21477e2723fc094a856b9f7c39bbdda6de2`
- Host OS report: `WindowsProductName=Windows 10 Home`, `WindowsVersion=2009`,
  `OsBuildNumber=26200`, `OsHardwareAbstractionLayer=10.0.26100.1`
- Selected serial port: `COM3`
- Serial device evidence: `USB-Enhanced-SERIAL CH343 (COM3)`,
  `USB\VID_1A86&PID_55D3\5B5E020088`, `wch.cn`
- ESP32-S3 MAC from flash transcript: `90:70:69:07:0d:7c`
- Recovery firmware image:
  `C:\t2t_v553\xtensa-esp32s3-espidf\debug\usb2ble-fw`
- Artifact directory:
  `target/windows-usb-host-recovery/usb_host_recovery_20260603_165146`

## Commands And Artifacts

Representative commands:

```text
[System.IO.Ports.SerialPort]::GetPortNames()
Get-CimInstance Win32_SerialPort
Get-PnpDevice -Class Ports
python tools\serial_command.py --port COM3 --timeout 5 GET_INFO GET_STATUS GET_USB_STATUS LIST_USB_DEVICES GET_BRIDGE_STATUS GET_CONFIG_STATUS
espflash monitor --port COM3 --chip esp32s3 --non-interactive --log-format serial
bash ./scripts/verify_cloud_equivalent.sh
cargo +esp build -Z build-std=std,panic_abort --locked --package usb2ble-fw --target xtensa-esp32s3-espidf
espflash flash --port COM3 --non-interactive C:\t2t_v553\xtensa-esp32s3-espidf\debug\usb2ble-fw
python tools\serial_command.py --port COM3 --timeout 8 GET_INFO GET_STATUS GET_USB_STATUS LIST_USB_DEVICES GET_INPUT_CATALOG "GET_HID_SUMMARY 2:0" "GET_HID_SUMMARY 3:0" "GET_NORMALIZED_INPUT 2:0" "GET_NORMALIZED_INPUT 3:0" "GET_LAST_USB_REPORT 2:0" "GET_LAST_USB_REPORT 3:0"
python tools\serial_command.py --port COM3 --timeout 8 START_VIRTUAL_INPUT "PUBLISH_VIRTUAL_INPUT_FRAME neutral" GET_VIRTUAL_INPUT_STATUS GET_GENERIC_GAMEPAD_MAPPING GET_GENERIC_GAMEPAD_REPORT STOP_VIRTUAL_INPUT
```

Key artifacts:

- `serial_port_discovery.txt`
- `baseline_target_status.txt`
- `baseline_usb_devices.txt`
- `boot_usb_enumeration_log.txt`
- `post_reset_usb_devices.txt`
- `verify_cloud_equivalent_before_esp_idf_wiring.txt`
- `target_build_v553_after_patch.txt`
- `flash_v553_output.txt`
- `boot_usb_enumeration_log_v553.txt`
- `post_v553_flash_status.txt`
- `topology_recovered_witness.txt`
- `target_virtual_sanity_after_recovery.txt`
- `known_good_vs_windows_current.md`

## Baseline Failure

Before recovery, the target control plane was healthy but the USB host reported
only the hub:

```text
INFO:version=1;name=usb2ble;persona=xbox_wireless_controller;
USB_STATUS:devices=1;interfaces=0;
USB_DEVICES:id=2,vid=2109,pid=2813
```

The boot log for the baseline firmware reported ESP-IDF `v5.2.3` and only the
hub attach:

```text
ESP-IDF:          v5.2.3
[USB_IFACE] Device: ID=1, IFACE=0, CLASS=09, SUBCLASS=00, PROTOCOL=00
[ATTACH] Device: ID=1, VID=2109, PID=2813
```

The generated sdkconfig for that Windows target build did not include
`CONFIG_USB_HOST_HUBS_SUPPORTED`.

## Build Wiring Recovery

Before changing the shell build scripts, Codex ran
`scripts/verify_cloud_equivalent.sh` as required by `AGENTS.md`. On this Windows
machine's Bash environment it failed before running checks because Bash could
not find Windows `cargo`:

```text
+ cargo fmt --all -- --check
./scripts/verify_cloud_equivalent.sh: line 3: cargo: command not found
```

The recovery build then explicitly used ESP-IDF `v5.5.3` and
`sdkconfig.defaults`. The v5.5.3 generated sdkconfig included:

```text
CONFIG_USB_HOST_HUBS_SUPPORTED=y
CONFIG_USB_HOST_HUB_MULTI_LEVEL=y
```

The BLE initialization structs were made tolerant of the v5.5.3 binding shape
with Rust `Default` fill-in for new fields. The shell build scripts now default
`ESP_IDF_VERSION` to `v5.5.3`, matching the firmware crate metadata and the
hub-capable build used for this witness.

## Flash Result

`espflash` identified the target and flashed the recovery build:

```text
Chip type:         esp32s3 (revision v0.2)
Flash size:        16MB
Features:          WiFi, BLE, Embedded Flash
MAC address:       90:70:69:07:0d:7c
App/part. size:    2,605,664/16,384,000 bytes, 15.90%
```

The flashed app boot log reported ESP-IDF `v5.5.3`.

## Recovered USB Host Topology

The v5.5.3 boot log showed all expected attach events:

```text
ESP-IDF:          v5.5.3
[ATTACH] Device: ID=1, VID=2109, PID=2813
[ATTACH] Device: ID=2, VID=044f, PID=b10a
[ATTACH] Device: ID=3, VID=044f, PID=b687
```

Post-flash control-plane output:

```text
INFO:version=1;name=usb2ble;persona=none;
STATUS:ble=Idle;profile=none;persona=none;bonds=false;
USB_STATUS:devices=3;interfaces=2;
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b10a|id=3,vid=044f,pid=b687
CONFIG_STATUS:valid=true;source=loaded;persona=generic_gamepad;profile=custom_runtime;mappings=6;import_active=false;last_error=none;
```

Observed topology:

| Device | VID:PID | Result |
| --- | --- | --- |
| HooToo hub | `2109:2813` | Seen |
| T.16000M stick | `044f:b10a` | Seen |
| TWCS with TFRP by RJ12 | `044f:b687` | Seen |

## Static Target-Side Input Evidence

After topology recovery, target diagnostics exposed HID summaries and static
normalized input for both downstream devices:

```text
HID_SUMMARY:axes=4;buttons=16;hats=1;report_ids=0;axis_usages=01:30,01:31,01:35,01:36;button_usages=1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16;hat_usages=01:39;
HID_SUMMARY:axes=8;buttons=14;hats=1;report_ids=1,0;axis_usages=01:30,01:31,01:35,01:33,01:34,01:36,01:37,01:32;button_usages=1,2,3,4,5,6,7,8,9,10,11,12,13,14;hat_usages=01:39;
```

`GET_INPUT_CATALOG` labeled device `2` as `Thrustmaster T.16000M` and device
`3` as `Thrustmaster TWCS/RJ12`. This is static target evidence only; no
operator movement was requested or captured.

## Target Virtual Sanity

After recovery, a small target-only virtual sanity check completed:

```text
START_VIRTUAL_INPUT
PUBLISH_VIRTUAL_INPUT_FRAME neutral
GET_VIRTUAL_INPUT_STATUS
GET_GENERIC_GAMEPAD_MAPPING
GET_GENERIC_GAMEPAD_REPORT
STOP_VIRTUAL_INPUT
```

Representative report output:

```text
GENERIC_GAMEPAD_MAPPING:profile=custom_runtime;persona=generic_gamepad;entries=6;...
ENCODED_REPORT:persona=generic_gamepad;report_id=1;bytes=000008000000000180000001800180;
```

This verifies that the firmware control-plane and virtual report path remained
healthy after USB host recovery. It is not Windows host-visible evidence.

## Conclusion

- PASS: COM port autodetected without operator-supplied port.
- PASS: target serial/control plane responded.
- PASS: baseline failure captured with only HooToo hub present.
- PASS: ESP-IDF v5.5.3 build/flash completed on Windows.
- PASS: downstream target USB host enumeration recovered for HooToo, T.16000M,
  and TWCS/RJ12.
- PASS: static HID summary, normalized-input, and last-report diagnostics were
  captured for T.16000M and TWCS/RJ12.
- PASS: target-only Generic virtual sanity check completed after recovery.
- NOT RUN: Windows BLE/Gamepad/XInput/browser/game compatibility, because this
  chunk was scoped to USB host topology recovery.

## Limitations

- No physical HOTAS movement was requested or captured.
- No Windows controller compatibility, game/app compatibility, broad host
  support, BLE bond persistence, final Flight Pack calibration, Xbox console
  compatibility, or proprietary Xbox Wireless compatibility is proven.
- The evidence is target-side USB topology and control-plane evidence on Alex's
  Windows PC.
