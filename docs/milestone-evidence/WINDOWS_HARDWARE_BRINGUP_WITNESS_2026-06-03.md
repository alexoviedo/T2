# Windows Hardware Bring-Up Witness - 2026-06-03

Status: partial Windows hardware bring-up and host-visibility diagnostic. This
evidence proves Windows serial discovery, ESP32-S3 flashing, target control-plane
health, target-side virtual Generic/Xbox report publication, and a negative
Windows host-visible probe for this run. It does not prove Windows
compatibility, game compatibility, physical HOTAS movement, BLE bond
persistence, or complete USB host topology.

## Summary

Codex ran the first Windows hardware evidence chunk on Alex's Windows PC with
the ESP32-S3, HooToo hub, T.16000M, TWCS, and TFRP physically connected. The
ESP32-S3 serial/programming port was autodetected as `COM3` from Windows PnP:
`USB-Enhanced-SERIAL CH343 (COM3)`, `USB\VID_1A86&PID_55D3`, manufacturer
`wch.cn`.

Firmware was built with the Espressif Rust toolchain and flashed successfully
with `espflash` to `COM3`. The target control plane responded after flashing.
The target reported only the HooToo hub (`2109:2813`) on its USB host side; it
did not report the expected downstream T.16000M (`044f:b10a`) or TWCS/RJ12
(`044f:b687`) devices in this Windows run.

Generic default, Generic unsigned six-axis, and Xbox virtual-input bridge runs
all published deterministic target-side reports while the target reported BLE
connected. Windows PnP, Raw Input, XInput, and Chrome Gamepad API probes did not
surface a connected USB2BLE gamepad for Generic or Xbox personas in this run.

## Context

- Date/time: 2026-06-03T22:14Z through 2026-06-03T22:31Z
- Commit under test: `d9b60b0ad1e8d6f9ff93f68652468020cff84058`
- Host OS report: `WindowsProductName=Windows 10 Home`, `WindowsVersion=2009`,
  `OsBuildNumber=26200`, `OsHardwareAbstractionLayer=10.0.26100.1`
- Selected serial port: `COM3`
- Serial device evidence: `USB-Enhanced-SERIAL CH343 (COM3)`,
  `USB\VID_1A86&PID_55D3\5B5E020088`, `wch.cn`
- Firmware image: `C:\t2t\xtensa-esp32s3-espidf\debug\usb2ble-fw`
- ESP32-S3 MAC from flash transcript: `90:70:69:07:0d:7c`

## Commands Run

```text
git status --short
git fetch origin --prune
Select-String ... generic_unsigned_6axis ...
[System.IO.Ports.SerialPort]::GetPortNames()
Get-CimInstance Win32_SerialPort
Get-PnpDevice -Class Ports
python tools\serial_command.py --port COM3 --timeout 3 GET_INFO GET_STATUS
cargo install espup --locked
cargo install ldproxy --locked
espup install --targets esp32s3 --std
cargo +esp build -Z build-std=std,panic_abort --locked --package usb2ble-fw --target xtensa-esp32s3-espidf
espflash flash --port COM3 --non-interactive C:\t2t\xtensa-esp32s3-espidf\debug\usb2ble-fw
python tools\serial_command.py --port COM3 --timeout 5 GET_INFO GET_STATUS LIST_BLE_COMPAT_VARIANTS GET_CONFIG_STATUS GET_USB_STATUS LIST_USB_DEVICES
python tools\windows_gamepad_probe.py
python tools\virtual_input_bridge_witness.py --port COM3 --persona generic --variant generic_default --no-browser --assume-bluetooth-connected --no-human --no-physical-input ...
python tools\windows_gamepad_probe.py --browser chrome ...
python tools\virtual_input_bridge_witness.py --port COM3 --persona generic --variant generic_unsigned_6axis --no-browser --assume-bluetooth-connected --no-human --no-physical-input ...
python tools\virtual_input_bridge_witness.py --port COM3 --persona xbox --no-browser --assume-bluetooth-connected --no-human --no-physical-input ...
```

## Flash And Control Plane

`espflash` identified the board as ESP32-S3 revision `v0.2`, reported 16 MB
flash, and completed flashing the built firmware image to `COM3`.

Post-flash serial control-plane excerpts:

```text
INFO:version=1;name=usb2ble;persona=none;
STATUS:ble=Idle;profile=none;persona=none;bonds=false;
CONFIG_STATUS:valid=true;source=loaded;persona=generic_gamepad;profile=custom_runtime;mappings=6;import_active=false;last_error=none;
```

The target reported implemented BLE compatibility variants:

```text
generic_default
generic_hogp_strict
generic_unsigned_6axis
xbox_compatibility
```

## USB Host Topology

Expected topology:

| Device | Expected VID:PID | Result |
| --- | --- | --- |
| HooToo hub | `2109:2813` | Seen |
| T.16000M stick | `044f:b10a` | Not reported |
| TWCS with TFRP by RJ12 | `044f:b687` | Not reported |

Observed target output after replug:

```text
USB_STATUS:devices=1;interfaces=0;
USB_DEVICES:id=1,vid=2109,pid=2813
```

Conclusion: this run proves the target USB host path sees the hub, but it does
not prove downstream Flight Pack enumeration on Windows.

## Windows Baseline Inventory

`tools\windows_gamepad_probe.py` exited 0. It reported:

```text
PnP controller-like devices: 4
Raw Input controller-like count: 0
XInput connected_count: 0
Chrome browser Gamepad API: no connected gamepad observations in persona probes
```

Windows PnP included an existing `Xbox Wireless Controller` Bluetooth entry and
Virtual Desktop/Oculus virtual gamepad buses. This witness does not treat those
background devices as USB2BLE host-visible evidence.

## Generic Default Virtual Run

Target-side Generic default virtual replay completed successfully:

```text
persona=generic
variant=generic_default
target_ble_connected=true
virtual_bridge_witness_passed=true
published_delta=45
```

Representative target report excerpt:

```text
BRIDGE_STATUS:enabled=true;persona=generic_gamepad;rate_hz=50;published=189;last_error=none;
ENCODED_REPORT:persona=generic_gamepad;report_id=1;bytes=000008ff7f00000180000001800180;
```

Windows visibility after the run:

```text
Raw Input controller-like count: 0
XInput connected_count: 0
Chrome connected_gamepad_observations: 0
```

Conclusion: target-side Generic default virtual report publication is proven for
this run; Windows host-visible Generic input is not proven.

## Generic Unsigned Variant A/B

`generic_unsigned_6axis` existed in the clone and was reported by the target in
`LIST_BLE_COMPAT_VARIANTS`, so the Windows A/B diagnostic was run.

Target-side unsigned six-axis virtual replay completed successfully:

```text
persona=generic
variant=generic_unsigned_6axis
target_ble_connected=true
virtual_bridge_witness_passed=true
published_delta=45
```

Windows visibility remained unchanged:

```text
Raw Input controller-like count: 0
XInput connected_count: 0
Chrome connected_gamepad_observations: 0
```

Conclusion: the unsigned six-axis variant did not improve Windows host-visible
exposure in this run. It remains experimental and non-default.

## Xbox Virtual Run

Target-side Xbox virtual replay completed successfully after an automated reset
from Generic to Xbox persona:

```text
persona=xbox
persona_id=xbox_wireless_controller
target_ble_connected=true
virtual_bridge_witness_passed=true
published_delta=42
```

Representative target report excerpt:

```text
XBOX_GAMEPAD_MAPPING:profile=custom_runtime;persona=xbox_wireless_controller;entries=6;...
ENCODED_REPORT:persona=xbox_wireless_controller;report_id=1;bytes=00800080008000800000000000000000;
BRIDGE_STATUS:enabled=true;persona=xbox_wireless_controller;rate_hz=50;published=46;last_error=none;
```

Windows visibility after the run:

```text
Raw Input controller-like count: 0
XInput connected_count: 0
Chrome connected_gamepad_observations: 0
```

Conclusion: target-side Xbox virtual report publication is proven for this run;
Windows host-visible Xbox input is not proven.

## Artifacts

- `target/windows-hardware-bringup/windows_hw_20260603_154842`
- `target/windows-gamepad-probe/windows_gamepad_probe_20260603_162255`
- `target/windows-host-witness/generic_default_virtual_nobrowser_20260603_162626`
- `target/windows-host-witness/generic_default_windows_visibility_20260603_162750`
- `target/windows-host-witness/generic_variant_ab_20260603_162820`
- `target/windows-host-witness/xbox_virtual_20260603_162959`

## Conclusion

This is a useful but partial Windows diagnostic:

- PASS: COM port autodetection without operator-supplied port.
- PASS: firmware build and flash to ESP32-S3.
- PASS: target serial/control plane after flash.
- PARTIAL: target USB topology sees HooToo hub only.
- PASS: target-side Generic default virtual report publication.
- PASS: target-side Generic unsigned six-axis virtual report publication.
- PASS: target-side Xbox virtual report publication.
- FAIL/NOT PROVEN: Windows host-visible Generic or Xbox controller exposure via
  PnP/Raw Input/XInput/Chrome Gamepad API.
- NOT RUN: game target test, because no persona became Windows host-visible.

## Limitations

- No physical HOTAS movement was requested or captured.
- The T.16000M and TWCS/RJ12 downstream USB devices were not reported by the
  target in this run.
- Browser witness automation on Windows needed follow-up portability work; the
  final host visibility results above are from `tools\windows_gamepad_probe.py`.
- BLE bond persistence and reconnect behavior are not proven.
- No Windows/game/native app compatibility, broad host compatibility, Xbox
  console compatibility, or proprietary Xbox Wireless compatibility is proven.
