# Config Persistence Witness - 2026-05-28

## Summary

Real ESP32-S3 target evidence proves runtime configuration import/export,
`SAVE_CONFIG`, command-path `LOAD_CONFIG`, actual board reset, post-reboot
`LOAD_CONFIG`, and `START_CONFIGURED` command behavior for a Generic Gamepad
runtime config.

This is CLI serial protocol evidence for the Web Serial-compatible config path.
It is not browser Web Serial UI evidence, BLE/gamepad compatibility, game/app
compatibility, BLE bond persistence, or final Flight Pack calibration evidence.

## Environment

- Date/time UTC: `20260528T223355Z`
- Commit SHA: `556f2fb898eebd68ec148db3bb618ef5fdb132e6`
- Git dirty during run: `false`
- Serial port: `/dev/cu.usbmodem5B5E0200881`
- Persona/profile: `generic` / `flight-pack`
- Reset command: `espflash reset --chip esp32s3 --port /dev/cu.usbmodem5B5E0200881 --non-interactive`
- Generated artifacts: `target/config-persistence-witness/config_persistence_20260528T223355Z`

## Hardware Topology

- ESP32-S3 serial/programming USB connected to the computer.
- HooToo SHUTTLE HT-UC001 powered hub on the ESP32-S3 USB host/OTG path.
- T.16000M stick USB and TWCS throttle USB connected through the hub.
- TFRP pedals connected to TWCS via RJ12 when present.

The transcript baseline reported the HooToo hub as `2109:2813` and a
Thrustmaster T.16000M as `044f:b10a`; the input catalog also included
`Thrustmaster TWCS/RJ12` controls from `044f:b687`.

## Commands Run

```bash
git status --short
./scripts/validate_no_hardware.sh
python3 -m py_compile tools/config_persistence_witness.py
python3 tools/config_persistence_witness.py --help
./scripts/check_target_build.sh
./scripts/build.sh
./scripts/flash.sh --port /dev/cu.usbmodem5B5E0200881
python3 tools/config_persistence_witness.py --port /dev/cu.usbmodem5B5E0200881 --reboot-after-save
```

## Result Summary

- `imported_matches_export`: `true`
- `loaded_matches_imported`: `true`
- `command_path_persistence_proven`: `true`
- `reboot_persistence_attempted`: `true`
- `reboot_persistence_proven`: `true`
- `reset_command_result.ok`: `true`
- `errors`: `[]`
- `persistence_errors`: `[]`

## Transcript Excerpts

```text
>> GET_INFO
INFO:version=1;name=usb2ble;persona=none;

>> GET_USB_STATUS
USB_STATUS:devices=2;interfaces=1;

>> LIST_USB_DEVICES
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b10a

>> COMMIT_CONFIG_JSON
CONFIG_IMPORT:state=committed;total_chunks=0;received_chunks=0;bytes=980;

>> GET_CONFIG_STATUS
CONFIG_STATUS:valid=true;source=runtime;persona=generic_gamepad;profile=custom_runtime;mappings=4;import_active=false;last_error=none;

## persistence
>> SAVE_CONFIG
CONFIG_ACTION:action=save;state=ok;

## post-reboot
>> GET_INFO
INFO:version=1;name=usb2ble;persona=none;

>> GET_CONFIG_STATUS
CONFIG_STATUS:valid=true;source=loaded;persona=generic_gamepad;profile=custom_runtime;mappings=4;import_active=false;last_error=none;

>> LOAD_CONFIG
CONFIG_ACTION:action=load;state=ok;

>> GET_CONFIG_STATUS
CONFIG_STATUS:valid=true;source=loaded;persona=generic_gamepad;profile=custom_runtime;mappings=4;import_active=false;last_error=none;

>> START_CONFIGURED
CONFIG_ACTION:action=start_configured;state=ok;detail=persona=generic_gamepad;bridge=false;;

>> GET_BRIDGE_STATUS
BRIDGE_STATUS:enabled=false;persona=generic_gamepad;rate_hz=50;last_publish_ms=none;published=0;skipped_duplicate=0;skipped_rate=0;skipped_not_connected=0;skipped_not_ready=0;last_error=none;
```

The generated `imported_config.json` and post-reboot `loaded_config.json` both
contained `selected_persona: generic_gamepad`, `selected_profile:
custom_runtime`, and the same four Flight Pack mappings.

## Limitations

- Browser Web Serial UI smoke is not claimed.
- BLE/gamepad and game/app compatibility are not claimed.
- BLE bond persistence is not claimed.
- Final Flight Pack calibration/deadzone semantics are not claimed.
- `START_CONFIGURED` returned `bridge=false`; no live bridge success is claimed
  from this witness.
