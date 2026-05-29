# iPhone BLE Advertising Diagnostic - 2026-05-29

Status: useful failure / diagnostic evidence. This does not prove iPhone compatibility.

## Summary

The ESP32-S3 was flashed with a diagnostic build that adds `GET_BLE_ADVERTISING_INFO`, then the current persisted refined Generic profile was started with `START_CONFIGURED`. The target reported that it was advertising the Generic BLE HID gamepad identity, but iPhone Bluetooth discovery still did not show `USB2BLE Gamepad`.

This narrows the current blocker to BLE discoverability / host filtering / advertisement or GATT compatibility before Safari/Gamepad API can be tested.

## Context

- Date/time: 2026-05-29T07:42:01Z
- Base commit recorded by the artifact: `5f4a520c8831e8798e822cd9a8a234c08172f9ba`
- Note: the target was flashed from the working tree that adds the diagnostic `GET_BLE_ADVERTISING_INFO` command and witness tooling in this chunk.
- Serial port: `/dev/cu.usbmodem5B5E0200881`
- Hardware topology observed by serial:
  - HooToo hub: `2109:2813`
  - T.16000M stick: `044f:b10a`
  - TWCS/RJ12: `044f:b687`
- Active config: `persona=generic_gamepad`, `profile=custom_runtime`, `mappings=6`

## Commands Run

```text
GET_INFO
GET_STATUS
GET_USB_STATUS
LIST_USB_DEVICES
GET_CONFIG_STATUS
FORGET_BLE_BONDS
START_CONFIGURED
GET_STATUS
GET_BRIDGE_STATUS
GET_BLE_ADVERTISING_INFO
```

The macOS best-effort scanner was also run through:

```text
python3 tools/ble_advertising_probe.py --duration-seconds 20 --name "USB2BLE Gamepad"
```

## Transcript Excerpts

```text
CONFIG_STATUS:valid=true;source=loaded;persona=generic_gamepad;profile=custom_runtime;mappings=6;import_active=false;last_error=none;
BLE_ACTION:action=forget_bonds;state=Advertising;
CONFIG_ACTION:action=start_configured;state=ok;detail=persona=generic_gamepad;bridge=true;;
STATUS:ble=Advertising;profile=none;persona=generic_gamepad;bonds=false;
```

```text
BLE_ADVERTISING_INFO:persona=generic_gamepad;state=Advertising;device_name=USB2BLE Gamepad;appearance=0x03c4;advertised_uuids=1812;adv_name=false;scan_rsp_name=true;flags=0x06;adv_type=ADV_TYPE_IND;own_addr_type=public;security=bond;io_capability=none;bonds=false;
```

## Result

| Variant | Target Advertising Active | Target Name | Appearance | HID UUID | Name Placement | Mac CLI Probe | iPhone Bluetooth |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Current Generic | yes | `USB2BLE Gamepad` | `0x03c4` | `1812` | scan response | not observed by stock macOS CLI summaries | not visible |

The macOS probe recorded that stock macOS command-line tools did not expose raw advertisement bytes, RSSI, or service UUIDs. It therefore does not prove the device was absent over the air; it only says the best-effort stock CLI summary did not list the searched name.

## Artifacts

- `target/iphone-compat/advertising_diagnostic_20260529T074201Z/summary.json`
- `target/iphone-compat/advertising_diagnostic_20260529T074201Z/serial_transcript.txt`
- `target/iphone-compat/advertising_diagnostic_20260529T074201Z/variant_results.jsonl`
- `target/iphone-compat/advertising_diagnostic_20260529T074201Z/mac_ble_probe_current_generic/summary.json`
- `target/ble-compat/implementation_snapshot_20260529T073152Z/implementation_snapshot.md`

## Limitations

- This is failure/diagnostic evidence only.
- It does not prove iPhone compatibility, iOS Safari Gamepad API behavior, native app compatibility, broad iOS support, BLE bond persistence, or final calibration quality.
- No raw BLE advertisement bytes were captured on this Mac.
- No experimental advertisement-layout variant was tested in this run. The next step is to add an explicit experimental variant, ideally informed by raw scanner output.
