# Windows BLE Identity Cache Diagnostic - 2026-06-04

Status: Windows host-visible identity/cache diagnostic from Alex's Windows PC.
This run verifies that Generic default, `generic_unsigned_6axis`, and Xbox
BLE-compatible personas can each pair/connect and expose the intended Windows
identity when the Windows BLE cache is cleaned between persona tests.

## Context

- Date/time: 2026-06-04 around 00:51-01:36 Mountain time.
- Commit: `f1170925518dab1b7331b7e7f47b21aa82a46cd4`
- Branch: `main`
- Selected serial port: `COM3`
- Serial device: `USB-Enhanced-SERIAL CH343 (COM3)`,
  `USB\VID_1A86&PID_55D3\5B5E020088`
- Artifact root:
  `target/windows-ble-identity/windows_ble_identity_20260604_005241`
- Repo hygiene artifact:
  `target/repo-hygiene/repo_hygiene_20260604_005142`

## Repository Hygiene

The run started from `main`, synced with `origin/main`, with a clean working
tree. No local non-main branches, remote feature branches, or stashes were
present. Two clean detached regression worktrees under
`target/ble-advertising-regression/.../worktrees/` were removed with
`git worktree remove`, followed by `git worktree prune`.

## Target Baseline

The target control plane responded on `COM3`. The practical RJ12 Flight Pack
topology remained healthy:

```text
USB_STATUS:devices=3;interfaces=2;
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b10a|id=3,vid=044f,pid=b687
```

This proves target-side USB enumeration only. It does not prove physical HOTAS
movement.

## Cache Cleanup

The Windows cache witness initially found USB2BLE-related Bluetooth/HID nodes
for the already-paired Generic identity at BLE address `90:70:69:07:0D:7E`.
Safe automated removal via `pnputil /remove-device` targeted only those
USB2BLE-related nodes, but Windows returned `Access is denied`.

Alex removed USB2BLE-related devices through Windows Bluetooth Settings. After
manual cleanup, `tools/windows_ble_cache_witness.py --dry-run` reported:

```json
{
  "candidates": []
}
```

The same manual cache cleanup was required between Generic, U6, and Xbox tests.

## Advertisement Identity

All personas advertised from the same BLE address:

```text
90:70:69:07:0D:7E
```

With a clean Windows cache, the native Windows BLE watcher saw the expected
advertised identity for each persona before pairing:

| Persona | Expected advertised name | Watcher result |
| --- | --- | --- |
| Generic default | `USB2BLE Gamepad` | Seen |
| Generic unsigned six-axis | `USB2BLE Gamepad U6` | Seen |
| Xbox BLE-compatible | `Xbox Wireless Controller` | Seen |

## Generic Default Result

Generic default was started with:

```text
START_BLE_GENERIC_GAMEPAD
```

Automated WinRT pairing discovered `USB2BLE Gamepad` and reported
`can_pair=true`, but the direct pair attempt returned `FAILED`. Alex completed
pairing through Windows Bluetooth Settings. The target then reported:

```text
STATUS:ble=Connected;profile=none;persona=generic_gamepad;bonds=false;
```

Windows PnP/HID showed the intended Generic identity:

```text
Bluetooth: USB2BLE Gamepad
HIDClass: HID-compliant game controller
VID/PID: 303a:4001
```

Virtual input replay changed target Generic report bytes and bridge publication
reached `published=26` with `last_error=none`. Edge Gamepad API then reported:

```text
id: Unknown Gamepad (Vendor: 303a Product: 4001)
mapping: ""
connected_gamepad_observations: 52
```

XInput slots 0-3 remained disconnected, which is expected for this Generic BLE
HID path.

## Generic Unsigned Six-Axis Result

The U6 variant was started with:

```text
START_BLE_GENERIC_GAMEPAD_VARIANT generic_unsigned_6axis
```

With the Windows cache cleaned first, the target reported
`active_variant=generic_unsigned_6axis` and
`device_name=USB2BLE Gamepad U6`. Alex completed pairing through Windows
Bluetooth Settings after the automated WinRT pair attempt returned `FAILED`.

Windows PnP/HID showed the intended U6 identity:

```text
Bluetooth: USB2BLE Gamepad U6
HIDClass: HID-compliant game controller
VID/PID: 303a:4002
```

Virtual input replay changed target U6 report bytes and bridge publication
progressed with `last_error=none`. Edge Gamepad API then reported:

```text
id: Unknown Gamepad (Vendor: 303a Product: 4002)
mapping: ""
connected_gamepad_observations: 299
```

XInput slots 0-3 remained disconnected, which is expected for this Generic BLE
HID variant.

During manual U6 removal, Alex observed that the controller appeared to connect,
disconnect, and reconnect rapidly in Windows Bluetooth Settings. Target
diagnostics corroborated the loop:

```json
"hidd_connect": 783,
"hidd_disconnect": 783,
"state": "Advertising"
```

This is cache/identity lifecycle evidence. It is not a bond-persistence or
reconnect-stability pass.

## Xbox Result

Xbox BLE-compatible persona was started with:

```text
START_BLE_XBOX_CONTROLLER
```

With the Windows cache cleaned first, the target reported:

```text
STATUS:ble=Connected;profile=none;persona=xbox_wireless_controller;bonds=false;
device_name=Xbox Wireless Controller
vendor_id=1118
product_id=2835
```

Windows PnP/HID showed the intended Xbox-like BLE HID identity:

```text
Bluetooth: Xbox Wireless Controller
HIDClass: HID-compliant game controller
VID/PID: 045e:0b13
```

XInput exposed slot 0 after pairing:

```text
slot: 0
connected: true
left_trigger: 0
right_trigger: 0
buttons: 0
```

Deterministic Xbox report scenarios were then published. Windows XInput slot 0
reflected the expected changes:

| Scenario | XInput observation |
| --- | --- |
| `neutral` | `buttons=0`, triggers 0, sticks near neutral |
| `left_stick_right` | left X `32767` |
| `right_stick_right` | right X `32767` |
| `left_trigger_max` | left trigger `255` |
| `right_trigger_max` | right trigger `255` |
| `button_a` | buttons `4096` |
| `button_b` | buttons `8192` |
| `button_x` | buttons `16384` |
| `button_y` | buttons `32768` |
| `button_lb` | buttons `256` |
| `button_rb` | buttons `512` |

After deterministic reports, Edge Gamepad API reported:

```text
id: HID-compliant game controller (STANDARD GAMEPAD Vendor: 045e Product: 0b13)
mapping: standard
connected_gamepad_observations: 421
```

This is Windows host-visible Xbox-like BLE HID and XInput diagnostic evidence on
Alex's PC. It is not Xbox console compatibility and not proprietary Xbox
Wireless compatibility.

## Identity Strategy Conclusion

Clean Windows cache is sufficient to test Generic default, U6, and Xbox one at a
time from the same BLE address. It is not sufficient for smooth persona
switching without manual host cleanup: Windows caches the first paired identity
for `90:70:69:07:0D:7E`, and previous runs showed later personas could be
reported as the cached Generic `303a:4001` device.

Per-persona BLE addresses are therefore not required to prove an isolated
persona, but they are likely required for reliable multi-persona Windows
evaluation without repeated manual cache removal. See `docs/BLE_IDENTITY_STRATEGY.md`.

## Limitations

- Virtual input evidence does not prove physical USB movement.
- Target USB topology evidence does not prove physical HOTAS movement.
- This is evidence for Alex's Windows PC only, not broad Windows compatibility.
- Generic and U6 evidence covers Windows Bluetooth, HIDClass, and Edge Gamepad
  API layers for virtual replay only.
- Xbox evidence covers Windows Bluetooth, HIDClass, XInput slot 0, and Edge
  standard Gamepad API for deterministic virtual reports only.
- No real game/app target was launched.
- BLE bond persistence was not tested.
- Xbox console compatibility and proprietary Xbox Wireless compatibility are
  not claimed.
