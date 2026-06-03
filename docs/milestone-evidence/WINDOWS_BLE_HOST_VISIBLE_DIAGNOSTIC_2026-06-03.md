# Windows BLE Host-Visible Diagnostic - 2026-06-03

Status: Windows BLE host-visible diagnostic with recovered target USB topology.
This evidence does not prove Windows controller compatibility. It records that
the ESP32-S3 target could see the practical RJ12 Flight Pack USB topology and
reported BLE persona advertising intent, while Windows Bluetooth scanning,
PnP/HID, Raw Input, XInput, and Edge Gamepad API did not expose a USB2BLE
controller.

## Summary

After the Windows USB host topology recovery, Codex reverified the ESP32-S3
control plane on `COM3` and confirmed the target USB host still saw:

```text
USB_STATUS:devices=3;interfaces=2;
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b10a|id=3,vid=044f,pid=b687
```

Codex then tested Generic default, `generic_hogp_strict`,
`generic_unsigned_6axis`, and Xbox BLE-compatible personas. In each case the
target-side control plane reported `Advertising`, but Windows active BLE scans
found no USB2BLE, Xbox, gamepad, or HID-service match. Alex also reported that
`USB2BLE Gamepad` was not visible in Windows Bluetooth settings.

The run therefore stops at the BLE advertisement/host discovery layer. No
physical HOTAS movement, BLE connection, Gamepad API movement, XInput movement,
game/app behavior, or broad Windows compatibility is proven.

## Context

- Date/time: 2026-06-03T23:19Z through 2026-06-03T23:56Z
- Commit at run start: `fe3a4f51978a44b31f90288ff004cee0fa228089`
- Host OS report: `WindowsProductName=Windows 10 Home`, `WindowsVersion=2009`,
  `OsBuildNumber=26200`, `OsHardwareAbstractionLayer=10.0.26100.1`
- Selected serial port: `COM3`
- Serial device evidence: `USB-Enhanced-SERIAL CH343 (COM3)`,
  `USB\VID_1A86&PID_55D3\5B5E020088`, manufacturer `wch.cn`
- ESP32-S3 MAC from flash transcript: `90:70:69:07:0d:7c`
- Firmware build path used during diagnostics:
  `C:\t2t_v553\xtensa-esp32s3-espidf\debug\usb2ble-fw`
- Artifact directory:
  `target/windows-host-visible/windows_host_visible_20260603_171900`

## Target Topology

The selected `COM3` port responded with USB2BLE control-plane output. The
post-flash target topology was healthy before persona tests:

```text
INFO:version=1;name=usb2ble;persona=none;
STATUS:ble=Idle;profile=none;persona=none;bonds=false;
USB_STATUS:devices=3;interfaces=2;
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b10a|id=3,vid=044f,pid=b687
```

After restoring and reflashing the checked-in baseline firmware at the end of
the diagnostic, the first immediate poll briefly saw only the hub, then the
first retry reported the full practical topology again:

```text
USB_STATUS:devices=3;interfaces=2;
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b10a|id=3,vid=044f,pid=b687
```

## BLE Visibility Matrix

The target exposed `generic_default`, `generic_hogp_strict`,
`generic_unsigned_6axis`, and `xbox_compatibility` in
`LIST_BLE_COMPAT_VARIANTS`.

Codex reset the target between persona cases, cleared BLE bonds, started the
persona, captured serial status/profile output, and ran a Windows active Bleak
scan.

| Persona or Variant | Target Result | Windows BLE Scan Result | Host-Visible Result |
| --- | --- | --- | --- |
| `generic_default` | `BLE_ACTION:action=start_generic_gamepad;state=Advertising;` | 49 advertisers, 0 USB2BLE/HID matches | Not visible |
| `generic_hogp_strict` | `BLE_ACTION:action=start_generic_gamepad_variant;state=Advertising;` | 52 advertisers, 0 USB2BLE/HID matches | Not visible |
| `generic_unsigned_6axis` | `BLE_ACTION:action=start_generic_gamepad_variant;state=Advertising;` | 48 advertisers, 0 USB2BLE/HID matches | Not visible |
| `xbox_compatibility` | `BLE_ACTION:action=start_xbox_controller;state=Advertising;` | 53 advertisers, 0 Xbox/gamepad/HID matches | Not visible |

Representative target-side Generic default profile excerpt:

```text
STATUS:ble=Advertising;profile=none;persona=generic_gamepad;bonds=false;
device_name: USB2BLE Gamepad
service_uuid: 1812
active_variant: generic_default
```

Representative target-side Xbox profile excerpt:

```text
STATUS:ble=Advertising;profile=none;persona=xbox_wireless_controller;bonds=false;
device_name: Xbox Wireless Controller
service_uuid: 1812
active_variant: xbox_compatibility
```

The raw serial transcripts also captured a repeated ESP-IDF Bluetooth-controller
line during stack initialization:

```text
BT_HCI: read_command_complete_header failed: opcode 0xfd09, status 0x0c
```

That line is diagnostic context only; this witness does not prove the root cause.

## Windows Host Layers

`tools/windows_gamepad_probe.py` was run after the persona visibility tests.
The Edge browser witness started and sampled the Gamepad API, but saw no
connected gamepad observations:

```text
connected_gamepad_observations: 0
gamepad_visible: false
sample_count: 46
```

Windows host layer summary:

- PnP/controller-like inventory: only Virtual Desktop and Oculus virtual
  gamepad emulation buses were present in the final probe.
- Raw Input: available, but `controller_like_count=0`.
- XInput: available through `xinput1_4`, but slots 0-3 all returned not
  connected.
- Edge Gamepad API: no gamepads observed.
- GameInput DLLs were present, but GameInput was not exercised by this
  lightweight probe.
- `joy.cpl` was not used because no host-visible controller baseline existed.

## Code Experiment Hygiene

During the diagnostic, Codex tested a narrow ESP-IDF BLE advertising sequencing
experiment locally. The experiment did not produce over-the-air Windows BLE
visibility, so it was not committed. The source tree was restored to the
checked-in BLE behavior, rebuilt, and reflashed before ending the run.

## Artifacts

Key artifacts under
`target/windows-host-visible/windows_host_visible_20260603_171900`:

- `repo_state.txt`
- `environment_summary.txt`
- `serial_discovery.txt`
- `target_topology.txt`
- `baseline_windows_probe/`
- `generic_default/`
- `ble_scans/generic_default_delayed_adv_bleak_scan.json`
- `ble_scans/generic_default_hidd_owned_adv_bleak_scan.json`
- `ble_persona_visibility_diagnostics/visibility_summary.json`
- `ble_persona_visibility_diagnostics/*_serial.txt`
- `ble_persona_visibility_diagnostics/*_bleak_scan.json`
- `post_visibility_windows_probe/`
- `firmware_baseline_restore/flash_output.txt`
- `firmware_baseline_restore/post_restore_target_status.txt`
- `firmware_baseline_restore/post_restore_topology_poll.txt`

## Conclusion

Result: fail/blocked at Windows BLE advertisement discovery.

This run proves only that the target USB topology was healthy and that the
target-side BLE persona command path reported advertising intent for Generic,
Generic variants, and Xbox. It does not prove that the ESP32-S3 was actually
advertising over the air in a form Windows could discover, and it does not prove
Windows controller, browser, XInput, game/app, physical movement, BLE bond
persistence, or broad host compatibility.

Recommended next chunk: isolate the BLE advertising layer with raw
over-the-air capture and/or ESP-IDF GAP/HCI diagnostics before retrying Windows
pairing or host-visible Gamepad API tests.
