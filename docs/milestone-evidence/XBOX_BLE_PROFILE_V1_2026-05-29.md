# Xbox BLE Profile v1 - 2026-05-29

Status: target-side Xbox BLE profile/report diagnostic evidence. This does not prove Xbox console compatibility, proprietary Xbox Wireless compatibility, broad host compatibility, or refined Xbox Flight Pack host-visible input.

## Summary

Xbox BLE Compatibility Profile v1 tightens the existing Xbox persona around the Xbox Wireless Controller model 1914 / Series X|S BLE reference shape:

- model-1914 BLE identity: `Xbox Wireless Controller`, VID `0x045e`, PID `0x0b13`,
- Game Pad HID report map with Report ID 1 input and Report ID 3 output,
- 16-byte input payload for sticks, triggers, hat, buttons, and Consumer Record / Share,
- 8-byte rumble-shaped output payload parsed as a safe no-op diagnostic object,
- target diagnostics for Xbox-specific report IDs, report lengths, control ranges, and claim boundaries,
- checker tooling that validates the source/profile shape before any host claim is made.

The current default Generic path is unchanged.

## Reference Model

The reference target is Xbox Wireless Controller model 1914 / Series X|S over Bluetooth LE HID. xpadneo documents a captured `045E:0B13` BLE HID report descriptor with Report ID 1 input and Report ID 3 output collections. USB2BLE uses these facts as compatibility-profile checks, not as a claim that Xbox consoles or proprietary Xbox Wireless are supported.

See `docs/XBOX_BLE_COMPATIBILITY_NOTES.md`.

## Target Context

- Date/time: 2026-05-29T20:32:39Z
- Local base commit: `4dace54328b008413a5141b70c4851df4a5db75a`
- Local build state: dirty working tree containing the Xbox Profile v1 changes documented here
- Serial port: `/dev/cu.usbmodem5B5E0200881`
- Firmware action: rebuilt and flashed before witness
- Hardware observed by serial:
  - HooToo hub: `2109:2813`
  - T.16000M stick: `044f:b10a`
  - TWCS/RJ12: `044f:b687`

## Commands Run

```text
./scripts/check_target_build.sh
./scripts/build.sh
./scripts/flash.sh --port /dev/cu.usbmodem5B5E0200881
python3 tools/xbox_ble_profile_witness.py --port /dev/cu.usbmodem5B5E0200881 --out-dir target/xbox-ble-profile-v1
python3 tools/check_xbox_ble_profile.py --builtin
```

## Checker Results

| Checker | Result |
| --- | --- |
| `tools/check_xbox_ble_profile.py` on target profile JSON | 30 pass, 0 warn, 0 fail |
| `tools/check_ble_hid_profile.py` on target profile JSON | 17 pass, 8 unknown, 0 fail |

The `unknown` HOGP/HIDS fields are ESP-IDF stack-hidden details such as HID Information, HID Control Point, Protocol Mode, Report Reference descriptors, CCCD/notify shape, Device Information Service, Battery Service, raw advertisement bytes, BLE address, and last bonded host.

## Target Transcript Excerpts

Xbox advertisement/profile:

```text
>> START_BLE_XBOX_CONTROLLER
BLE_ACTION:action=start_xbox_controller;state=Advertising;
>> GET_BLE_ADVERTISING_INFO
BLE_ADVERTISING_INFO:persona=xbox_wireless_controller;state=Advertising;variant=xbox_compatibility;device_name=Xbox Wireless Controller;appearance=0x03c4;advertised_uuids=1812;scan_rsp_uuids=;adv_name=false;scan_rsp_name=true;flags=0x06;adv_type=ADV_TYPE_IND;own_addr_type=public;security=bond;io_capability=none;bonds=false;raw_adv_bytes=false;
```

Profile JSON summary:

```text
active_persona=xbox_wireless_controller
active_variant=xbox_compatibility
vendor_id=0x045e
product_id=0x0b13
report_ids=[1,3]
report_map_len=283
input_payload_len=16
output_payload_len=8
stick_logical_range=0..65535
trigger_logical_range=0..1023
share_usage=consumer_record
```

Current USB-derived Xbox mapping/report:

```text
>> GET_XBOX_GAMEPAD_MAPPING
XBOX_GAMEPAD_MAPPING:profile=xbox_flight_pack_demo;persona=xbox_wireless_controller;...
```

The mapping included:

- `044f:b10a:axis_01_30 -> left_x`
- `044f:b10a:axis_01_31 -> left_y`
- `044f:b687:axis_01_36 -> right_x`
- `044f:b687:axis_01_34 -> left_trigger`
- `044f:b687:axis_01_33 -> right_trigger`
- `044f:b687:axis_01_32 -> none` with `profile_unmapped`, which is the intentional Xbox throttle compromise.

Encoded target report:

```text
>> GET_XBOX_GAMEPAD_REPORT
ENCODED_REPORT:persona=xbox_wireless_controller;report_id=1;bytes=517cc97a1f8000800000000000000000;
```

## Artifacts

- `target/xbox-ble-profile-v1/xbox_profile_20260529T203239Z`
- `target/xbox-ble-profile-v1/xbox_profile_20260529T203239Z/summary.json`
- `target/xbox-ble-profile-v1/xbox_profile_20260529T203239Z/serial_transcript.txt`
- `target/xbox-ble-profile-v1/xbox_profile_20260529T203239Z/xbox_compat_profile.json`
- `target/xbox-ble-profile-v1/xbox_profile_20260529T203239Z/xbox_profile_check.json`
- `target/xbox-ble-profile-v1/xbox_profile_20260529T203239Z/ble_hid_profile_check.json`

## Pass / Fail Table

| Check | Result |
| --- | --- |
| Firmware rebuilt and flashed from Xbox Profile v1 working tree | PASS |
| Target starts Xbox BLE persona | PASS |
| Target reports `xbox_compatibility` variant | PASS |
| Target reports model-1914 identity `045e:0b13` | PASS |
| Target reports Report IDs `[1, 3]` | PASS |
| Xbox reference checker passes target profile JSON | PASS |
| BLE HOGP/HIDS checker has no structural failures | PASS |
| `GET_XBOX_GAMEPAD_MAPPING` returns Flight Pack Xbox diagnostics | PASS |
| TWCS throttle is intentionally unmapped in Xbox profile | PASS |
| `GET_XBOX_GAMEPAD_REPORT` returns 16-byte Report ID 1 payload | PASS |
| Host-visible refined Xbox Flight Pack mapping | NOT CLAIMED |
| Xbox console / proprietary Xbox Wireless compatibility | NOT CLAIMED |
| Windows / Android / iOS / broad host compatibility | NOT CLAIMED |

## Limitations

- This is target-side profile/report evidence, not a host-visible Xbox mapping witness.
- No Xbox console was used or targeted.
- No proprietary Xbox Wireless behavior is implemented or claimed.
- No Windows, Android, iOS, Linux, Steam, SDL, native game, or broad browser compatibility is proven by this run.
- Rumble output is descriptor-shaped and parser-safe, but functional rumble was not tested.
- Bond persistence and reconnect hardening remain unproven for the Xbox profile.
