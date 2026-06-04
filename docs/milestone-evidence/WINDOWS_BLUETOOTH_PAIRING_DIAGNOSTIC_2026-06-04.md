# Windows Bluetooth Pairing Diagnostic - 2026-06-04

Status: partial Windows host-visible diagnostic from Alex's Windows PC. This
run verifies that current firmware advertisements still work, that Generic
default can pair/connect on Windows after manual Settings approval, and that
Windows exposes the paired Generic persona through HID and Edge Gamepad API
layers during virtual input replay.

## Context

- Date/time: 2026-06-04 around 00:18-00:35 Mountain time
- Commit: `623b17c8ca1d717f13976d1d4162e0c49dc2b7d3`
- Branch: `main`
- Selected serial port: `COM3`
- Serial device: `USB-Enhanced-SERIAL CH343 (COM3)`,
  `USB\VID_1A86&PID_55D3\5B5E020088`
- Artifact root:
  `target/windows-pairing-host-visible/windows_pairing_20260604_001941`
- Repo hygiene artifact:
  `target/repo-hygiene/repo_hygiene_20260604_001847`

## Repository Hygiene

The local branch was `main`, synced with `origin/main`, and clean at the start
of the run. No local feature branches or stashes were present. Two detached
regression worktrees remain documented under `target/ble-advertising-regression`
and were not deleted.

## Target Baseline

The target control plane responded on `COM3`. The practical RJ12 Flight Pack
topology remained healthy:

```text
USB_STATUS:devices=3;interfaces=2;
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b10a|id=3,vid=044f,pid=b687
```

This proves target-side enumeration only. It does not prove physical HOTAS
movement.

## Advertisement Sanity

The native Windows BLE watcher saw all gate advertisements from the fixed
current firmware at address `90:70:69:07:0D:7E`:

| Mode | Expected name | Result |
| --- | --- | --- |
| Raw smoke | `BLE_SMOKE` | Seen, RSSI -30 to -32 dBm |
| Generic default | `USB2BLE Gamepad` | Seen, HID UUID `1812`, RSSI -30 to -32 dBm |
| Xbox | `Xbox Wireless Controller` | Seen, HID UUID `1812`, RSSI -30 to -32 dBm |

The first raw-smoke attempt returned `ERROR:PersonaAlreadyActive` because an
older persona owner was still active. A board reset cleared the owner and the
advertisement was then visible.

## Generic Default Result

Generic default was started with:

```text
START_BLE_GENERIC_GAMEPAD
```

Windows automated WinRT pairing resolved `USB2BLE Gamepad` and reported
`can_pair=true`, but the direct pair attempt returned `FAILED`. Alex completed
Windows Bluetooth Settings pairing manually. After that, the target reported:

```text
STATUS:ble=Connected;profile=none;persona=generic_gamepad;bonds=false;
```

Windows PnP/HID inventory then showed:

```text
Bluetooth: USB2BLE Gamepad
HIDClass: HID-compliant game controller
InstanceId: HID\{00001812-0000-1000-8000-00805F9B34FB}_DEV_VID&02303A_PID&4001_REV&0001_907069070D7E\...
```

Virtual input replay was run for neutral, stick, throttle, rudder, and toe
scenarios. Target `GET_GENERIC_GAMEPAD_REPORT` bytes changed across scenarios,
and `GET_BRIDGE_STATUS` reached `published=27` with `last_error=none`.

Edge Gamepad API did not show a connected gamepad before virtual input began.
After virtual input/bridge publishing, Edge reported:

```text
id: Unknown Gamepad (Vendor: 303a Product: 4001)
mapping: ""
connected_gamepad_observations: 95
```

XInput slots 0-3 remained disconnected, which is expected for this Generic BLE
HID path and is not treated as a Generic failure.

## Generic Unsigned Variant Result

The target reports `generic_unsigned_6axis` as available. The variant was
started with:

```text
START_BLE_GENERIC_GAMEPAD_VARIANT generic_unsigned_6axis
```

The target reported `active_variant=generic_unsigned_6axis` and
`device_name=USB2BLE Gamepad U6`, but Windows did not expose a separate
`USB2BLE Gamepad U6` pairing identity. It reused the already-paired
`USB2BLE Gamepad` device identity at VID:PID `303a:4001`.

Target-side virtual reports changed under the U6 encoder, and Edge continued to
see the cached Generic gamepad identity:

```text
id: Unknown Gamepad (Vendor: 303a Product: 4001)
mapping: ""
```

The bridge did not publish U6 reports successfully in this cached connection
state; `GET_BRIDGE_STATUS` reported `last_error=ble_error`.

Conclusion: this run does not prove Windows accepts the U6 identity or VID:PID
`303a:4002`. A clean Windows unpair/cache-clearing or per-persona BLE identity
test is required.

## Xbox Result

Xbox persona was started with:

```text
START_BLE_XBOX_CONTROLLER
```

The target reported:

```text
STATUS:ble=Connected;profile=none;persona=xbox_wireless_controller;bonds=false;
device_name=Xbox Wireless Controller
vendor_id=1118
product_id=2835
```

However, Windows inventory still showed the previously paired Generic identity:

```text
Bluetooth: USB2BLE Gamepad
HIDClass: HID-compliant game controller
VID:PID: 303a:4001
```

XInput slots 0-3 remained disconnected. Edge continued to expose:

```text
id: Unknown Gamepad (Vendor: 303a Product: 4001)
mapping: ""
```

Target Xbox report bytes changed for virtual stick, rudder, and toe scenarios,
but bridge publication reported `last_error=ble_error` in the cached Generic
host connection. `PUBLISH_XBOX_TEST_REPORT A/B/LT/RT` returned `ERROR:Generic`
for those shorthand arguments in this firmware.

Conclusion: this run does not prove Windows Xbox host-visible compatibility,
XInput exposure, Xbox console compatibility, or proprietary Xbox Wireless
compatibility.

## Limitations

- Virtual input evidence does not prove physical USB movement.
- Target USB topology evidence does not prove physical HOTAS movement.
- This is evidence for Alex's Windows PC only, not broad Windows compatibility.
- Generic default host-visible evidence covers Windows Bluetooth, HIDClass, and
  Edge Gamepad API layers for virtual replay only.
- XInput did not expose Generic, U6, or Xbox in this run.
- U6 and Xbox were blocked by Windows reusing the first-paired Generic identity
  for the same BLE address; separate host identity behavior remains unproven.
- BLE bond persistence was not tested.
- No real game/app target was launched.

