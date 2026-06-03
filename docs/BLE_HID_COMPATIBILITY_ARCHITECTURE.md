# BLE HID Compatibility Architecture

Status: design and evidence policy for host-specific BLE HID compatibility. This document is not compatibility evidence.

## Layer Model

USB2BLE compatibility work is split into layers so a failure can be diagnosed without guessing:

1. GAP advertising and discovery: device name, flags, appearance, advertised service UUIDs, scan response, address type, advertising interval, and whether the host shows the device before pairing.
2. GATT service shape: which services and characteristics the host discovers after connecting.
3. HOGP/HIDS details: HID Information, Report Map, Report Reference descriptors, Protocol Mode, HID Control Point, Client Characteristic Configuration descriptors, and encryption requirements.
4. HID report map: usage pages, collection shape, report IDs, signed/unsigned axis ranges, buttons, hats, triggers, and report payload sizes.
5. Security and bonding: Just Works, authentication/encryption, bond storage, bond clearing, reconnect behavior, and host cache behavior.
6. Host OS parser: how macOS, iOS, Android, Windows, Linux/BlueZ, and browser layers classify the device.
7. App/browser exposure: Chrome Gamepad API, Safari Gamepad API, native game/controller APIs, and app-specific mapping.

## Known Host Notes

- macOS + Chrome with the `generic_default` path is proven for the refined practical RJ12 Flight Pack Generic profile. See `docs/EVIDENCE_INDEX.md`.
- iPhone did not discover the current Generic advertisement in Bluetooth settings, so Safari/Gamepad API cannot be tested yet.
- Android and Windows are untested. ESP32-BLE-Gamepad documents host-specific axis/trigger behavior differences and says iOS is not supported by that generic library, which is a useful warning for USB2BLE.
- Windows game compatibility often expects XInput-like semantics rather than a generic HID gamepad. USB2BLE has an Xbox persona slice, but refined Xbox host-visible mapping is not proven.
- Linux/BlueZ is valuable as a diagnostic host because tools such as `btmon`, `bluetoothctl`, and kernel HID logs can expose lower-level behavior than iOS Settings.
- Older iOS-friendly controller hacks often used keyboard/iCade-style input. USB2BLE may eventually provide an experimental `ios_keyboard_icade_fallback`, but it must be labeled as a keyboard fallback, not a true gamepad.
- Consumer-grade iPhone controller support often involves MFi or known platform-specific identities. USB2BLE should not impersonate vendor identities in default/public mode without careful evidence and legal review.

## Variant Strategy

The proven default must remain unchanged:

- `generic_default`: current Generic Gamepad path, evidence-backed on macOS/Chrome.
- `generic_hogp_strict`: experimental Generic advertisement variant. It keeps the same logical persona/report map, but moves the complete local name into the primary advertisement and moves the HID UUID to scan response to stay within legacy advertisement payload limits.
- `generic_unsigned_6axis`: implemented experimental descriptor/report-map variant for hosts that may dislike signed axes. It keeps six `X/Y/Z/Rx/Ry/Rz` axes, uses unsigned centered `0..65535` values, and advertises a distinct `USB2BLE Gamepad U6` / `303a:4002` identity for cache-safe A/B testing. The 2026-06-02 A/B diagnostic verified the variant on target but did not improve the missing macOS HID/Chrome delivery for later refined Generic axes, so it remains non-default.
- `generic_android_sim_controls`: planned descriptor variant for simulation-control-style throttle/brake/accelerator semantics.
- `ios_keyboard_icade_fallback`: planned keyboard/iCade-style fallback, not a true Gamepad API path.
- `xbox_compatibility`: Xbox Wireless Controller model 1914 / Series X|S BLE profile target, with profile diagnostics/checker evidence and broad compatibility still unclaimed.

Variant promotion rules:

- Variants are selected only through explicit commands/configuration.
- A variant cannot replace `generic_default` until checked-in evidence shows it preserves the proven default use case or a migration plan exists.
- Every variant witness must state host, OS/browser/app version, active persona, active variant, advertisement/profile diagnostics, pairing result, app/API exposure result, and limitations.
- Failure evidence is useful when it records the layer that failed.

## Pitfalls And Mitigations

- Payload budget: Complete Local Name, Appearance, and UUIDs may not all fit in a legacy 31-byte primary advertisement. Mitigation: use 16-bit UUIDs where valid, and capture intended fields through `GET_BLE_COMPAT_PROFILE`.
- Host cache: stale bonds/descriptors can hide improvements. Mitigation: record `FORGET_BLE_BONDS`, host-side forget steps, and reset/reboot steps.
- Stack abstraction: ESP-IDF `esp_hidd_dev_init` constructs much of the HIDS GATT table. Mitigation: target diagnostics report intent, while raw scanner/GATT tools are used for over-the-air proof.
- Descriptor compatibility: signed six-axis Generic HID works on macOS Chrome, but other hosts may map or ignore axes differently. Mitigation: keep report-map variants explicit and evidence-backed.
- Identity risk: known controller names may improve discovery but can create legal/trust problems. Mitigation: do not use vendor impersonation in default mode; keep any identity experiments private and documented.

## Diagnostics

- `GET_BLE_ADVERTISING_INFO` reports target-side advertisement intent in semicolon form.
- `GET_BLE_COMPAT_PROFILE` reports active persona, variant, identity, advertisement fields, report-map length, intended services, and security policy as JSON.
- `LIST_BLE_COMPAT_VARIANTS` reports implemented/planned variants as JSON.
- `tools/ble_advertising_probe.py` captures best-effort macOS Bluetooth summaries and can ingest manual scanner exports.
- `tools/ble_compatibility_variant_witness.py` runs variants one boot at a time and saves target-side and host-discovery artifacts.
- `tools/check_ble_hid_profile.py` checks profile snapshots for HOGP/HIDS-adjacent structure while marking stack-hidden GATT details as `unknown`.
- `tools/check_xbox_ble_profile.py` checks the Xbox model-1914 BLE profile shape, including VID/PID, Report ID 1 input, Report ID 3 output, trigger/stick ranges, button/share layout, and source report-map features.
- `tools/ble_compat_reset.py` runs a conservative reset workflow: stop bridge, clear bonds, reboot, start a selected variant, and dump the active profile.
- `tools/ble_profile_snapshot.py` writes source-defined profile snapshots for supported/planned variants.

## Evidence Needed To Promote A Variant

At minimum:

- Raw or independent scanner evidence for advertisement fields, when possible.
- Target transcript including `GET_BLE_ADVERTISING_INFO` and `GET_BLE_COMPAT_PROFILE`.
- Host discovery/pairing result.
- App/API exposure result if the claim reaches beyond Bluetooth visibility.
- Movement/input witness for any mapping claim.
- Explicit limitations and non-claims.

Promotion from experimental to supported requires:

1. the target host discovers the advertised variant,
2. the host pairs/connects,
3. the intended GATT/HIDS shape is exposed or any stack-hidden pieces are independently captured,
4. input reports are sent over BLE,
5. the host app/API sees the intended input,
6. reconnect or bond behavior is tested,
7. evidence is checked in and linked from the evidence index.

## References

- Apple Support: [Connect a wireless game controller to your Apple device](https://support.apple.com/en-us/111099)
- Apple Developer: [Discovering game controllers](https://developer.apple.com/documentation/gamecontroller/discovering-game-controllers)
- Apple Developer WebKitJS: [Gamepad](https://developer.apple.com/documentation/webkitjs/gamepad)
- Espressif: [Bluetooth HID Device API](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/bluetooth/esp_hidd.html)
- Zephyr Project: [Bluetooth: Peripheral HIDS sample](https://docs.zephyrproject.org/latest/samples/bluetooth/peripheral_hids/README.html)
- ESP32-BLE-Gamepad: [Project documentation](https://github.com/lemmingDev/ESP32-BLE-Gamepad)
- xpadneo: [Xbox Series X|S BLE descriptor notes](https://github.com/atar-axis/xpadneo/blob/master/docs/descriptors/xbxs.md)
- Bluetooth SIG: [Assigned Numbers](https://www.bluetooth.com/specifications/assigned-numbers/)
