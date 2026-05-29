# iPhone Safari Generic Gamepad Failure Witness - 2026-05-29

Status: **failure/diagnostic evidence; iPhone compatibility remains unproven.**

## Summary

This run attempted the first iPhone/Safari compatibility exploration for the
refined Generic Flight Pack profile after adding a public iPhone-compatible
Gamepad API check page.

The target was reachable over serial, had the persisted refined Generic runtime
config loaded, and reported the Generic BLE persona in `Advertising` state after
macOS disconnected from `USB2BLE Gamepad`. Alex checked iPhone Bluetooth
settings and reported that `USB2BLE Gamepad` was not visible. The same result
was observed after `FORGET_BLE_BONDS` and after an actual ESP32-S3 reset followed
by `START_CONFIGURED`.

Conclusion: this is a useful failure. It does not prove iPhone/Safari Gamepad API
behavior because the iPhone did not reach pairing/connection. It does show that,
in this run, the iPhone did not discover the advertised USB2BLE Generic BLE HID
device.

## Context

- Date/time: 2026-05-29 around 07:08 UTC.
- Evidence commit: `4bdc7b04ae3eb9a790fd59c85b5c97bb6caf0d8f`.
- Selected serial port: `/dev/cu.usbmodem5B5E0200881`.
- Host used for serial/diagnostics: macOS 12.7.5.
- iPhone model/iOS version: not captured.
- iPhone browser context: Safari intended, but the test page was not reached as
  a paired Gamepad API witness because Bluetooth discovery failed.
- Public test page: <https://alexoviedo.github.io/T2/iphone-compat.html>.
- Target artifact directory:
  `target/iphone-compat/iphone_safari_generic_20260529T070819Z`.

## Hardware Topology

- ESP32-S3 running USB2BLE.
- HooToo SHUTTLE HT-UC001 powered hub on the ESP32-S3 USB host path.
- T.16000M stick USB connected through the hub.
- TWCS throttle USB connected through the hub.
- TFRP pedals connected to TWCS through RJ12.

Target USB identity in the final diagnostic artifact:

```text
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b10a|id=3,vid=044f,pid=b687
```

## Commands And Actions

Baseline and deployment work:

```bash
./scripts/validate_no_hardware.sh
./scripts/check_target_build.sh
python3 tools/check_evidence_docs.py --verbose
python3 tools/check_launch_readiness.py --verbose
python3 tools/check_release_candidate.py --verbose
cd web && npm test && npm run build
python3 -m py_compile tools/iphone_compat_witness.py
```

Target/iPhone attempt:

```bash
python3 tools/serial_command.py --port /dev/cu.usbmodem5B5E0200881 --timeout 3 \
  GET_INFO GET_STATUS GET_USB_STATUS LIST_USB_DEVICES GET_CONFIG_STATUS GET_BRIDGE_STATUS

python3 tools/serial_command.py --port /dev/cu.usbmodem5B5E0200881 --timeout 3 \
  GET_STATUS GET_BRIDGE_STATUS FORGET_BLE_BONDS GET_STATUS START_CONFIGURED GET_STATUS GET_BRIDGE_STATUS

espflash reset --chip esp32s3 --port /dev/cu.usbmodem5B5E0200881 --non-interactive

python3 tools/serial_command.py --port /dev/cu.usbmodem5B5E0200881 --timeout 3 \
  GET_INFO GET_STATUS GET_CONFIG_STATUS START_CONFIGURED GET_STATUS GET_BRIDGE_STATUS

python3 tools/iphone_compat_witness.py --port /dev/cu.usbmodem5B5E0200881 --skip-iphone --poll-seconds 20
```

Human-visible iPhone observations:

- Alex first did not see `USB2BLE Gamepad` on the iPhone while the Mac was still
  connected.
- macOS Bluetooth then showed `USB2BLE Gamepad` disconnected.
- With the target reporting `Advertising`, Alex again reported that the iPhone
  still did not show `USB2BLE Gamepad`.
- After `FORGET_BLE_BONDS` and an ESP32-S3 reset plus `START_CONFIGURED`, Alex
  again reported `still not visible`.

## Transcript Excerpts

After disconnecting macOS:

```text
STATUS:ble=Advertising;profile=none;persona=generic_gamepad;bonds=false;
BRIDGE_STATUS:enabled=true;persona=generic_gamepad;rate_hz=50;last_publish_ms=23598735;published=16431;skipped_duplicate=16275;skipped_rate=0;skipped_not_connected=56;skipped_not_ready=0;last_error=not_connected;
```

After `FORGET_BLE_BONDS`:

```text
BLE_ACTION:action=forget_bonds;state=Advertising;
STATUS:ble=Advertising;profile=none;persona=generic_gamepad;bonds=false;
```

After ESP32-S3 reset and `START_CONFIGURED`:

```text
INFO:version=1;name=usb2ble;persona=none;
STATUS:ble=Idle;profile=none;persona=none;bonds=false;
CONFIG_STATUS:valid=true;source=loaded;persona=generic_gamepad;profile=custom_runtime;mappings=6;import_active=false;last_error=none;
CONFIG_ACTION:action=start_configured;state=ok;detail=persona=generic_gamepad;bridge=true;;
STATUS:ble=Advertising;profile=none;persona=generic_gamepad;bonds=false;
```

Final diagnostic artifact summary:

```json
{
  "iphone_safari_generic_gamepad_passed": false,
  "iphone_evidence_present": false,
  "iphone_gamepad_connected": null,
  "published_delta": 0,
  "skipped_not_connected_delta": 22,
  "last_error_values": ["not_connected"]
}
```

## Limitations

- This does not prove iPhone compatibility.
- This does not prove iPhone incompatibility across all models, iOS versions, or
  BLE cache states.
- This does not prove Safari Gamepad API behavior because the iPhone did not pair
  or connect to the controller.
- This does not test a native iOS app or App Store game.
- This does not prove BLE bond persistence, reconnect robustness, broad host
  support, or final Flight Pack calibration quality.

## Recommended Next Diagnostic Step

Run a focused BLE advertising compatibility investigation before repeating the
iPhone Safari page:

- Capture raw BLE advertisements for `USB2BLE Gamepad` from an independent BLE
  scanner while the target reports `Advertising`.
- Compare Generic HID advertising flags, appearance, service UUIDs, bonding
  requirements, and device name against what iOS expects for Bluetooth game
  controllers.
- If advertising shape changes are made, rerun this iPhone witness from a clean
  iPhone Bluetooth state and only then update compatibility status.
