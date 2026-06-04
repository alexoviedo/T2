# Minimal BLE Advertising Isolation

This lab target builds `usb2ble-fw`'s standalone `minimal_ble_adv` binary. It
is not production firmware and does not initialize USB2BLE USB host, HID,
persona, mapping, bridge, or storage code.

The binary uses the repo's existing ESP-IDF v5.5.3 Windows build path and does
only:

- NVS init,
- BLE-only controller init/enable,
- Bluedroid init/enable,
- one GAP callback,
- one raw legacy advertisement payload named `BLE_SMOKE`.

## Build

```powershell
.\tools\minimal_ble_adv\build.ps1
```

## Flash

```powershell
.\tools\minimal_ble_adv\flash.ps1 -Port COM3
```

If `-Port` is omitted, the script uses the first visible `COM*` port. For lab
runs, prefer the COM port selected by serial autodetection artifacts.

## Expected Serial Markers

```text
--- MINIMAL BLE ADV BOOT ---
MIN_ADV:config_raw_return=0
MIN_ADV:adv_raw_config_complete_status=0
MIN_ADV:start_return=0
MIN_ADV:adv_start_complete_status=0
MIN_ADV:status ... started=1 ...
```

Windows BLE watcher should see the local name `BLE_SMOKE` if advertising starts
and RF/scanner paths are healthy.
