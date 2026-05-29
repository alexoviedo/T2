# BLE Scanner Workflow

Status: operator workflow for raw BLE advertisement and GATT evidence. This is not compatibility evidence by itself.

## Why This Exists

Stock macOS command-line tools on the current Mac can report paired/recent Bluetooth devices, but they do not reliably expose raw BLE advertisement bytes, primary-versus-scan-response fields, service UUIDs, appearance, address, or RSSI. USB2BLE therefore treats macOS CLI scans as weak supporting diagnostics only.

For compatibility work, prefer an independent scanner export that can be normalized by:

```bash
python3 tools/ble_advertising_probe.py \
  --manual-scan-file <scanner-export.json-or.txt> \
  --name "USB2BLE Gamepad"
```

## Recommended Scanner Sources

### nRF Connect

Use nRF Connect on iPhone or Android if available:

1. Start scanning.
2. Look for `USB2BLE Gamepad` or the variant's advertised name.
3. Save/share the advertisement details as JSON or text if the app supports it.
4. Import the export with `tools/ble_advertising_probe.py --manual-scan-file`.

If iPhone Settings does not show the controller but nRF Connect sees it, that is a strong hint that the advertisement exists over the air and iOS Game Controller acceptance is filtering it.

### LightBlue Explorer

Use LightBlue on macOS/iOS for advertisement and GATT details:

1. Scan for USB2BLE.
2. Capture advertised name, address, RSSI, service UUIDs, appearance, and raw data if shown.
3. If connected, capture discovered GATT services and characteristics.
4. Import any text/JSON export, or copy the relevant text into a file under `target/`.

### Android BLE Scanner

Android scanner apps often expose raw advertisement data more directly than iOS Settings:

1. Scan for USB2BLE.
2. Export raw advertisement, scan response, RSSI, and service UUIDs.
3. Import with `tools/ble_advertising_probe.py`.

### Linux BlueZ

On a Linux host with Bluetooth:

```bash
sudo btmon | tee target/ble-compat/btmon_usb2ble.txt
bluetoothctl scan on
```

Then import the captured text:

```bash
python3 tools/ble_advertising_probe.py \
  --manual-scan-file target/ble-compat/btmon_usb2ble.txt \
  --name "USB2BLE Gamepad"
```

### Future Second ESP32 Scanner

A second ESP32 scanner should eventually:

- perform passive and active BLE scans,
- dump address, address type, RSSI, flags, complete/short local name, service UUIDs, appearance, manufacturer data, service data, primary advertisement bytes, and scan response bytes,
- emit line-delimited JSON that `tools/ble_advertising_probe.py` can import.

This is the preferred future path for repeatable raw advertisement evidence without depending on phone-app export formats.

## Evidence Rules

- Raw scanner output is still not proof of pairing, Gamepad API exposure, or app compatibility.
- If a scanner sees a variant but iPhone Settings does not, record that as a discovery/filtering diagnostic.
- If iPhone Settings sees a variant, run the iPhone Safari page only after pairing succeeds.
- Keep generated scanner exports under `target/` unless summarized into a reviewed evidence document.
