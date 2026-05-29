# Apple BLE Compatibility Notes

Status: diagnostic notes for the post-alpha iPhone discoverability investigation. This document records current facts and hypotheses; it does not claim iPhone compatibility.

## Known External Requirements

- Apple’s public pairing flow starts in Bluetooth settings: the controller must be put into pairing/discoverable mode, then selected from the nearby-device list before apps or Safari can use it.
- Apple’s Game Controller framework is built around supported controller profiles such as Extended, Xbox, DualShock, DualSense, Micro, Directional, and Spatial. Apple documents MFi, console controllers, and platform-specific devices, but does not promise that every generic BLE HID gamepad appears as a Game Controller device.
- Safari/WebKit exposes a Gamepad API surface, but that layer is downstream of OS-level controller acceptance. If iOS never discovers or pairs the BLE controller, the iPhone compatibility page cannot collect Gamepad API evidence.
- Bluetooth SIG assigned numbers identify the HID service as `0x1812` and Gamepad GAP appearance as `0x03c4`.
- ESP-IDF provides a BLE HID Device API and examples for HID over GATT; USB2BLE currently uses ESP-IDF Bluedroid/esp_hid rather than a custom GATT table.
- ESP32-BLE-Gamepad documents that its generic BLE gamepad path does not support iOS and points users toward XInput-capable alternatives. That does not prove USB2BLE cannot work on iOS, but it raises the likelihood that Apple host acceptance depends on more than a generic HOGP gamepad advertisement.

## Current USB2BLE Generic Advertisement Facts

Source inspected on 2026-05-29:

- Generic persona name: `USB2BLE Gamepad`.
- Generic BLE appearance: `0x03c4` (Gamepad).
- Generic advertised service UUID: HID service `0x1812` encoded as a 128-bit Bluetooth base UUID in the primary advertisement.
- Primary advertisement includes flags `0x06` (LE General Discoverable + BR/EDR Not Supported).
- Primary advertisement does not include the complete local name.
- Scan response includes the complete local name.
- Advertising type: connectable undirected (`ADV_TYPE_IND`).
- Own address type: public.
- Security: bonding enabled with Just Works-style IO capability `none`.
- BLE transport initializes the HID service through ESP-IDF `esp_hidd_dev_init`.
- The target now exposes intended advertising state through `GET_BLE_ADVERTISING_INFO`.
- The compatibility model now separates `generic_default` from the experimental `generic_hogp_strict` advertisement variant so Apple/iOS hypotheses can be tested without changing the proven default.

## Working Hypotheses

1. iOS may filter generic BLE HID gamepads before showing them as pairable controllers.
   - Likelihood: high.
   - Evidence: Apple’s public/developer docs discuss supported controller profiles and console/MFi classes. USB2BLE’s Generic HID works on macOS Chrome, but the iPhone did not show it in Bluetooth settings.
   - Test: compare USB2BLE advertisements and GATT HID shape against a controller that iPhone does show. Use nRF Connect/LightBlue/Android scanner or a second ESP32 scanner.

2. Advertisement payload layout may be insufficient for iPhone discovery.
   - Likelihood: medium.
   - Evidence: USB2BLE puts the local name in scan response only. Some hosts behave differently depending on whether name, appearance, and HID UUID appear in primary advertising versus scan response.
   - Test: run `generic_hogp_strict`, which includes Complete Local Name in the primary advertisement and moves the HID service UUID to scan response, then run the variant witness.

3. Companion GATT services or characteristics may differ from Apple-accepted game controllers.
   - Likelihood: medium.
   - Evidence: USB2BLE delegates HID service construction to ESP-IDF `esp_hidd_dev_init`; current diagnostics report intended advertisement settings, not full discovered GATT tables.
   - Test: capture full GATT from macOS/LightBlue/nRF Connect and compare HID Information, Report Map, Protocol Mode, Report characteristics, Battery Service, and Device Information Service.

4. Security/bonding behavior may not match iOS expectations.
   - Likelihood: medium-low for discoverability, higher for pairing.
   - Evidence: USB2BLE uses bonding, IO capability none, encryption and identity keys. The observed blocker is pre-pairing visibility, not pairing failure.
   - Test: once a scanner sees advertisements, try experimental security variants: no-bond, bond-only, and Just Works bond with fresh host/target bond clears.

5. Host cache or another active host connection may suppress advertising.
   - Likelihood: low for the latest failure.
   - Evidence: Alex disconnected the Mac, cleared target bonds, reset the ESP32-S3, and restarted configured Generic advertising before the iPhone still failed to see it.
   - Test: use `GET_BLE_ADVERTISING_INFO`, `GET_STATUS`, Mac scanner output, and iPhone manual discovery in one timestamped diagnostic run.

## Tests To Run

| Test | Proves | Disproves |
| --- | --- | --- |
| `GET_BLE_ADVERTISING_INFO` during `START_CONFIGURED` | Target intends to advertise Generic HID with name, appearance, UUID, security settings | Raw over-the-air advertisement correctness |
| `tools/ble_advertising_probe.py` on macOS | Whether stock macOS summaries currently expose a USB2BLE-like device name | Raw advertisement bytes, UUIDs, RSSI |
| iPhone manual Bluetooth discovery per variant | Whether iOS Settings displays that exact variant | Safari/Gamepad API compatibility |
| `tools/ble_compatibility_variant_witness.py` | Default and experimental variant target diagnostics, Mac scan summaries, and optional iPhone discovery result | Raw advertisement bytes unless a scanner export is ingested |
| nRF Connect/LightBlue/Android scan | Raw advertised name, UUID, appearance, RSSI, address | Whether iOS accepts it as a game controller |
| Full GATT table capture | HID service/report-map/service completeness | Advertisement-layer filtering alone |
| Experimental advertising layout variant | Whether name/appearance/UUID placement affects iPhone visibility | MFi/profile filtering if still invisible |

## Future Scanner Options

- Nordic nRF Connect on iPhone or Android for advertisement and GATT captures.
- LightBlue Explorer on macOS/iOS for advertisement/GATT inspection.
- Android BLE scanner apps, which often expose more raw advertisement fields than iOS Settings.
- A second ESP32 running a passive BLE scanner.
- Dedicated BLE sniffer if over-the-air packet-level evidence becomes necessary.

## References

- Apple Support: [Connect a wireless game controller to your Apple device](https://support.apple.com/en-us/111099)
- Apple Developer: [Discovering game controllers](https://developer.apple.com/documentation/gamecontroller/discovering-game-controllers)
- Apple Developer WebKitJS: [Gamepad](https://developer.apple.com/documentation/webkitjs/gamepad)
- Espressif: [Bluetooth HID Device API](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/bluetooth/esp_hidd.html)
- Bluetooth SIG: [Assigned Numbers](https://www.bluetooth.com/specifications/assigned-numbers/)
- Adafruit Bluefruit HID notes: [BLE Services](https://learn.adafruit.com/adafruit-bluefruit-le-shield/ble-services)
