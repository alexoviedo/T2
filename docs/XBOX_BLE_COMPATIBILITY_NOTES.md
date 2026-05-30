# Xbox BLE Compatibility Notes

Status: research and implementation checklist for the USB2BLE Xbox BLE profile. This is not a claim of Xbox console, proprietary Xbox Wireless, Windows, Android, iOS, or broad game compatibility.

## Scope

USB2BLE targets the Bluetooth LE HID behavior of the Xbox Wireless Controller model 1914 / Series X|S family because ESP32-S3 can act as a BLE HID peripheral. This profile is useful for hosts that understand an Xbox-like BLE HID device over HOGP/HIDS.

Out of scope:

- Xbox consoles,
- proprietary Xbox Wireless dongle/protocol support,
- Bluetooth Classic-only Xbox controllers,
- headset/audio transport,
- exact trigger-rumble behavior beyond safe report acceptance until captured by host evidence,
- broad Windows, Android, iOS, Linux, browser, or game compatibility without checked-in evidence.

## Reference Model

The xpadneo project documents a captured Xbox Series X|S BLE HID report descriptor for `VID 045E`, `PID 0B13`. It also documents that newer BLE firmware uses a mostly unified descriptor across BLE models, with Elite Series 2 using `PID 0B22` while most non-Elite BLE controllers use `PID 0B13`.

Reference shape encoded by USB2BLE:

- device name: `Xbox Wireless Controller`,
- VID/PID: `045E:0B13`,
- GAP appearance: gamepad,
- top-level Game Pad application collection,
- Report ID 1 input report,
- unsigned 16-bit left stick X/Y,
- unsigned 16-bit right stick Z/Rz,
- 10-bit Simulation Controls Brake / Accelerator for triggers,
- hat switch range `1..8` with `0` as neutral/null,
- 15 gamepad buttons,
- Consumer Record usage for Share,
- Report ID 3 output report for rumble-shaped host output.

USB2BLE treats Report ID 3 output as safe/no-op unless a future host-stack path exposes output writes to firmware and evidence proves behavior.

## Current USB2BLE Match

Current implementation intentionally matches the model-1914 BLE identity and report-map shape at the target/profile level:

- `XBOX_MODEL_1914_SERIES_XS_BLE_IDENTITY` exposes `Xbox Wireless Controller`, Microsoft VID `0x045e`, PID `0x0b13`, and gamepad appearance.
- `XBOX_WIRELESS_CONTROLLER_REPORT_MAP` includes Report ID 1 input and Report ID 3 output collections.
- `XboxWirelessControllerEncoder` emits a 16-byte Report ID 1 payload: four unsigned 16-bit sticks, two 10-bit trigger payload slots carried in 16-bit little-endian fields, hat, 15 buttons, and a Share/Record byte.
- `parse_xbox_rumble_output_report` parses the 8-byte Report ID 3 payload as a safe no-op diagnostic object.
- `GET_BLE_COMPAT_PROFILE` reports Xbox-specific VID/PID, model target, descriptor reference, report IDs, report lengths, trigger/stick ranges, output support boundary, and claim boundary.
- `tools/check_xbox_ble_profile.py` checks source/profile snapshots against this reference model.

## Current USB2BLE Gaps

- No Xbox console or proprietary Xbox Wireless compatibility is implemented or claimed.
- Refined Flight Pack Xbox mapping is target-side only until a host-visible Xbox
  mapping witness captures physical rudder/toe-brake movement through the live
  bridge.
- Windows, Android, iOS, Linux, and external/native game compatibility are unproven for the refined Xbox profile.
- Rumble host-output writes are descriptor-shaped and parser-safe, but not host-visible functional rumble.
- BLE bond persistence/reconnect behavior remains unproven for this profile.

## macOS Chrome Standard-Layout Discovery

The 2026-05-29 deterministic host-visible diagnostic showed that Chrome can
expose USB2BLE's Xbox-compatible persona as:

```text
Xbox Wireless Controller (STANDARD GAMEPAD)
mapping=standard
axes=4
buttons=18
```

Chrome/macOS remapped Xbox-like raw button bits to browser-standard positions
rather than using USB2BLE's original logical order literally. USB2BLE therefore
uses the observed raw bit positions for the main logical buttons in the Xbox
encoder:

| Logical control | Raw Xbox button bit | Browser standard result |
| --- | --- | --- |
| A | 0 | B0 |
| B | 1 | B1 |
| X | 3 | B2 |
| Y | 4 | B3 |
| LB | 6 | B4 |
| RB | 7 | B5 |
| View | 10 | B8 |
| Menu | 11 | B9 |

Left/right stick press remain unresolved: the raw bits tested for those
controls did not surface as browser B10/B11 in the current macOS Chrome run.
The result is a strong host-visible diagnostic for the main controls, not a
complete Xbox standard-layout claim.

## Flight Pack Xbox Mapping

The practical RJ12 Flight Pack Xbox profile is intentionally constrained by Xbox-like control slots:

| Source control | Xbox target | Transform | Rationale |
| --- | --- | --- | --- |
| T.16000M `044f:b10a:axis_01_30` | `left_x` | axis | primary stick X |
| T.16000M `044f:b10a:axis_01_31` | `left_y` | axis | primary stick Y |
| TWCS/RJ12 `044f:b687:axis_01_36` | `right_x` | axis | rudder as right stick X |
| TWCS/RJ12 `044f:b687:axis_01_34` | `left_trigger` | `axis_to_trigger invert=true` | left toe brake as Brake |
| TWCS/RJ12 `044f:b687:axis_01_33` | `right_trigger` | `axis_to_trigger invert=true` | right toe brake as Accelerator |
| TWCS `044f:b687:axis_01_32` | unmapped | intentional | throttle has no clean Xbox analog slot after toe brakes consume trigger slots |

This is a deliberate profile tradeoff, not a final product-quality mapping claim.

## Promotion Criteria

The Xbox BLE profile can be promoted only after evidence shows:

1. source/profile checker passes for the intended variant,
2. target transcript captures `GET_BLE_ADVERTISING_INFO` and `GET_BLE_COMPAT_PROFILE`,
3. host discovers and pairs with the Xbox-like BLE HID device,
4. host/app/browser sees Report ID 1 input movement for the intended controls,
5. refined Flight Pack Xbox mapping is host-visible if that mapping is claimed,
6. reconnect/bond behavior is tested if persistence is claimed,
7. checked-in evidence documents host, OS/browser/app, artifact paths, limitations, and non-claims.

## References

- xpadneo: [Xbox Series X|S descriptor notes](https://github.com/atar-axis/xpadneo/blob/master/docs/descriptors/xbxs.md)
- xpadneo: [BLE model/PID and Share-button quirks](https://github.com/atar-axis/xpadneo/blob/master/docs/README.md)
- ESP32-BLE-Gamepad: [configurable BLE gamepad behavior and platform notes](https://github.com/lemmingDev/ESP32-BLE-Gamepad)
- Espressif: [Bluetooth HID Device API](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/bluetooth/esp_hidd.html)
- Zephyr: [Bluetooth Peripheral HIDS sample](https://docs.zephyrproject.org/latest/samples/bluetooth/peripheral_hids/README.html)
