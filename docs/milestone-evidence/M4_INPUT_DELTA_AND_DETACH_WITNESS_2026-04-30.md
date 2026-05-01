# M4 Input Delta And Detach Witness - 2026-04-30

Status: **accepted hardware evidence for TWCS movement, TFRP movement through
TWCS/RJ12, T.16000M trigger button, and detach cleanup.**

This witness uses real ESP32-S3 target runs through the HooToo SHUTTLE
HT-UC001 powered hub. It does not claim calibrated semantic mapping. In the
current `generic_auto` profile, TWCS/TFRP movement is visible as source-only
mapping diagnostics because the Generic Gamepad axis slots are already filled.

## Hardware Context

- ESP32-S3 serial port: `/dev/cu.usbmodem5B5E0200881`
- Powered hub: `2109:2813`
- TWCS throttle: `044f:b687`, device `2`, interface `0`
- TFRP pedals connected through TWCS RJ12
- T.16000M stick: `044f:b10a`, device `3`, interface `0` for trigger test
- Firmware version from current demo path: `0.4.2-ble-hid-demo`

## TWCS Throttle Movement

Raw USB precheck:

```bash
python3 tools/usb_report_delta_witness.py \
  --port /dev/cu.usbmodem5B5E0200881 \
  --source 2:0 \
  --label twcs_throttle_raw_after_reset \
  --watch-seconds 25 \
  --sample-interval 0.10
```

Observed raw deltas:

```text
Raw USB report byte deltas:
  byte[20]: 237 -> 236
  byte[22]: 210 -> 211
  byte[24]: 156 -> 157
  byte[26]: 31 -> 30
  byte[28]: 205 -> 206
  byte[30]: 158 -> 157
  byte[32]: 109 -> 110
  byte[34]: 216 -> 215

Saved raw witness: target/usb-report-delta-witness/usb_report_delta_20260430T211836Z_twcs_throttle_raw_after_reset.json
```

Mapping witness:

```bash
python3 tools/mapping_delta_witness.py \
  --port /dev/cu.usbmodem5B5E0200881 \
  --label twcs_throttle_mapping_after_reset \
  --watch-seconds 25 \
  --sample-interval 0.10
```

Selected observed mapping deltas:

```text
Mapped target deltas:
  3:0:044f:b10a:axis_01_31 -> y: axis:-1083 -> axis:-1079 (preferred_axis)
Unmapped/source-only deltas:
  2:0:044f:b687:axis_01_32 -> none: axis:32767 -> axis:-32768 (axis_slots_full)
  2:0:044f:b687:usage_ff00_21_36 -> none: unknown:16 -> unknown:113 (unsupported_control)

Saved raw witness: target/mapping-delta-witness/mapping_delta_20260430T211911Z_twcs_throttle_mapping_after_reset.json
```

Result: TWCS movement changes raw USB reports and appears in
`GET_GENERIC_GAMEPAD_MAPPING` diagnostics. It is source-only under the current
auto-mapper because axis slots are full.

## TFRP Pedal Movement Through TWCS RJ12

Raw USB precheck:

```bash
python3 tools/usb_report_delta_witness.py \
  --port /dev/cu.usbmodem5B5E0200881 \
  --source 2:0 \
  --label tfrp_pedals_raw_via_twcs \
  --watch-seconds 25 \
  --sample-interval 0.10
```

Selected raw deltas:

```text
Raw USB report byte deltas:
  byte[11]: 18 -> 16
  byte[12]: 2 -> 3
  byte[29]: 65 -> 96
  byte[31]: 21 -> 23
  byte[57]: 171 -> 108
  byte[59]: 235 -> 157

Saved raw witness: target/usb-report-delta-witness/usb_report_delta_20260430T212025Z_tfrp_pedals_raw_via_twcs.json
```

Mapping witness:

```bash
python3 tools/mapping_delta_witness.py \
  --port /dev/cu.usbmodem5B5E0200881 \
  --label tfrp_pedals_mapping_via_twcs \
  --watch-seconds 25 \
  --sample-interval 0.10
```

Selected observed mapping deltas:

```text
Mapped target deltas:
  3:0:044f:b10a:axis_01_30 -> x: axis:-671 -> axis:-667 (preferred_axis)
  3:0:044f:b10a:axis_01_31 -> y: axis:-1087 -> axis:-1079 (preferred_axis)
Unmapped/source-only deltas:
  2:0:044f:b687:axis_01_36 -> none: axis:287 -> axis:415 (axis_slots_full)
  2:0:044f:b687:usage_ff00_21_31 -> none: unknown:91 -> unknown:96 (unsupported_control)
  2:0:044f:b687:usage_ff00_21_32 -> none: unknown:65 -> unknown:32 (unsupported_control)
  2:0:044f:b687:usage_ff00_21_62 -> none: unknown:123 -> unknown:116 (unsupported_control)

Saved raw witness: target/mapping-delta-witness/mapping_delta_20260430T212101Z_tfrp_pedals_mapping_via_twcs.json
```

Result: TFRP pedal movement through TWCS/RJ12 changes raw TWCS USB reports and
appears in mapping diagnostics. It is source-only under the current auto-mapper
because axis slots are full.

## T.16000M Trigger Button Press

Raw USB precheck:

```bash
python3 tools/usb_report_delta_witness.py \
  --port /dev/cu.usbmodem5B5E0200881 \
  --source 3:0 \
  --label t16000_trigger_raw_after_reset \
  --watch-seconds 20 \
  --sample-interval 0.10
```

Observed raw deltas:

```text
Raw USB report byte deltas:
  byte[0]: 0 -> 1
  byte[3]: 89 -> 88
  byte[5]: 242 -> 241
  byte[6]: 30 -> 31
  byte[7]: 122 -> 119

Saved raw witness: target/usb-report-delta-witness/usb_report_delta_20260430T212149Z_t16000_trigger_raw_after_reset.json
```

Mapping witness:

```bash
python3 tools/mapping_delta_witness.py \
  --port /dev/cu.usbmodem5B5E0200881 \
  --label t16000_trigger_mapping_after_reset \
  --watch-seconds 20 \
  --sample-interval 0.10
```

Selected observed mapping delta:

```text
Mapped target deltas:
  3:0:044f:b10a:button_1 -> button_1: button:1 -> button:0 (button)

Saved raw witness: target/mapping-delta-witness/mapping_delta_20260430T212218Z_t16000_trigger_mapping_after_reset.json
```

Result: a clean button-press path is captured and mapped to Generic Gamepad
`button_1`.

## Detach Cleanup

Two stale-state attempts happened before the detach fix. In those attempts the
physical device was unplugged, but `GET_USB_STATUS`, `GET_HID_SUMMARY`, and
`GET_LAST_USB_REPORT` still reported stale device state. The fix added detach
handling for both ESP-IDF client `DEV_GONE` events and interrupt-transfer
`NO_DEVICE`/`CANCELED` statuses.

Patched firmware was flashed, then TWCS was detached from the HooToo hub while
the hub stayed connected to the ESP32-S3.

Command:

```bash
python3 tools/detach_cleanup_witness.py \
  --port /dev/cu.usbmodem5B5E0200881 \
  --source 2:0 \
  --label twcs_detach_cleanup_transfer_status_fix \
  --watch-seconds 30
```

Before detach:

```text
>> GET_USB_STATUS
USB_STATUS:devices=2;interfaces=1;
>> LIST_USB_DEVICES
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b687
>> GET_HID_SUMMARY 2:0
HID_SUMMARY:axes=8;buttons=14;hats=1;report_ids=1,0;axis_usages=01:30,01:31,01:35,01:33,01:34,01:36,01:37,01:32;button_usages=1,2,3,4,5,6,7,8,9,10,11,12,13,14;hat_usages=01:39;
>> GET_LAST_USB_REPORT 2:0
USB_REPORT:01fe0100020002ff03ff030902c302ffff080000ec3fd13fa32d15428a4155156610331bcacae8d629298b8a8483a0502d2da0510abc02cd5b6c266600008002
```

Detach and after-state:

```text
[DETACH] Device: ID=2

After detach:
>> GET_USB_STATUS
USB_STATUS:devices=1;interfaces=0;
>> LIST_USB_DEVICES
USB_DEVICES:id=1,vid=2109,pid=2813
>> GET_HID_SUMMARY 2:0
ERROR:NotFound
>> GET_LAST_USB_REPORT 2:0
ERROR:NotFound

Saved raw witness: target/detach-cleanup-witness/detach_cleanup_20260430T213646Z_twcs_detach_cleanup_transfer_status_fix.json
```

Result: detach cleanup removes the downstream HID device, its interface,
descriptor summary, and cached raw report while leaving the hub identity present.

## Interpretation

- TWCS movement delta witness: **pass**, source-only under current auto-map.
- TFRP pedal delta witness through TWCS/RJ12: **pass**, source-only under
  current auto-map.
- T.16000M trigger/button delta witness: **pass**, mapped to `button_1`.
- Detach cleanup witness: **pass** after platform detach handling fix.
- Remaining work is profile/calibration quality, especially assigning TWCS and
  TFRP axes to intended Generic Gamepad targets instead of relying on full-slot
  generic auto-mapping.
