# BLE Compatibility Lab v1 - 2026-05-29

Status: diagnostic/platform evidence. This does not prove new host compatibility.

## Summary

BLE Compatibility Lab v1 adds a repeatable compatibility framework around the existing BLE HID personas:

- source-defined BLE compatibility variants,
- richer target-side profile diagnostics,
- HOGP/HIDS-adjacent profile checking,
- normalized scanner-import tooling,
- compatibility reset workflow,
- profile snapshots,
- target witness artifacts for `generic_default` and `generic_hogp_strict`.

The current default Generic behavior remains the proven default path. The new `generic_hogp_strict` variant is experimental and was shown to start advertising on target, but no iPhone/iOS compatibility is claimed.

## Target Context

- Date/time: 2026-05-29T08:52:41Z
- Serial port: `/dev/cu.usbmodem5B5E0200881`
- Hardware observed by serial:
  - HooToo hub: `2109:2813`
  - T.16000M stick: `044f:b10a`
  - TWCS/RJ12: `044f:b687`
- Firmware was rebuilt and flashed from the local BLE Compatibility Lab v1 working tree.
- Persisted runtime config still reported `persona=generic_gamepad`, `profile=custom_runtime`, `mappings=6`.

## Variants Inspected

| Variant | Implementation State | Target Result | Profile Checker |
| --- | --- | --- | --- |
| `generic_default` | implemented, default | `Advertising`; HID UUID in primary advertisement, name in scan response | 16 pass, 8 unknown, 0 fail |
| `generic_hogp_strict` | implemented, experimental | `Advertising`; complete local name in primary advertisement, HID UUID in scan response | 16 pass, 8 unknown, 0 fail |
| `ios_keyboard_icade_fallback` | source-defined stub only | not target-started | source snapshot: 4 pass, 20 unknown, 0 fail |
| `xbox_compatibility` | implemented existing persona | not target-started in this lab run | source snapshot: 16 pass, 8 unknown, 0 fail |

Unknown profile-check fields are intentional for stack-hidden details such as HID Information, HID Control Point, Protocol Mode, Report Reference descriptors, CCCD/notify shape, Device Information Service, Battery Service, raw advertisement bytes, BLE address, and last bonded host.

## Target Transcript Excerpts

Default Generic:

```text
BLE_ADVERTISING_INFO:persona=generic_gamepad;state=Advertising;variant=generic_default;device_name=USB2BLE Gamepad;appearance=0x03c4;advertised_uuids=1812;scan_rsp_uuids=;adv_name=false;scan_rsp_name=true;flags=0x06;adv_type=ADV_TYPE_IND;own_addr_type=public;security=bond;io_capability=none;bonds=false;raw_adv_bytes=false;
```

Experimental HOGP-strict Generic:

```text
BLE_ADVERTISING_INFO:persona=generic_gamepad;state=Advertising;variant=generic_hogp_strict;device_name=USB2BLE Gamepad;appearance=0x03c4;advertised_uuids=;scan_rsp_uuids=1812;adv_name=true;scan_rsp_name=false;flags=0x06;adv_type=ADV_TYPE_IND;own_addr_type=public;security=bond;io_capability=none;bonds=false;raw_adv_bytes=false;
```

Reset workflow:

```text
STOP_BRIDGE
FORGET_BLE_BONDS
espflash reset --chip esp32s3 --port /dev/cu.usbmodem5B5E0200881 --non-interactive
START_BLE_GENERIC_GAMEPAD_VARIANT generic_hogp_strict
GET_BLE_COMPAT_PROFILE
```

## Scanner / Import Support

`tools/ble_advertising_probe.py` still records stock macOS CLI Bluetooth summaries, but now also imports scanner text/JSON exports and normalizes:

- device name,
- address,
- RSSI,
- flags,
- service UUIDs,
- appearance,
- manufacturer data,
- service data,
- raw bytes when exported.

Fixture tests cover nRF Connect-style JSON and BlueZ `btmon`-style text. No real raw scanner export was captured in this lab run.

## Artifacts

- `target/ble-compat/lab_v1_20260529T085241Z/reset_20260529T085245Z`
- `target/ble-compat/lab_v1_20260529T085241Z/variant_witness_20260529T085305Z`
- `target/ble-compat/lab_v1_20260529T085241Z/profile_snapshots_20260529T085330Z`

## Limitations

- This does not prove iPhone, Android, Windows, Linux, Xbox host-visible refined mapping, BLE bond persistence, reconnect hardening, or broad host support.
- No iPhone manual discovery result was captured for `generic_hogp_strict` in this lab run.
- No raw over-the-air advertisement bytes were captured from a scanner in this lab run.
- GATT/HIDS details constructed inside ESP-IDF `esp_hidd_dev_init` remain target-intended or unknown until a host/scanner captures them.
- `ios_keyboard_icade_fallback` is a source-defined stub only; it is not implemented or tested as input behavior.
