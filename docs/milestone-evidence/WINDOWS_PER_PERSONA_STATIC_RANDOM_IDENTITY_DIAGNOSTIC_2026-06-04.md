# Windows Per-Persona Static Random Identity Diagnostic - 2026-06-04

Status: partial Windows identity diagnostic from Alex's Windows PC. This run
proves that `persona_static_random_experimental` produces stable, distinct BLE
advertising addresses for Generic default, `generic_unsigned_6axis`, and Xbox.
It also proves that each persona can be paired and exposed individually after
Windows Bluetooth Settings intervention. It does not prove cache-free switching
or coexistence: Alex reported that the previous persona had to be removed before
the next persona would connect.

## Context

- Date/time: 2026-06-04 around 12:00-13:50 Mountain time.
- Commit: `f892bdcd71282f62afe0453cbe0a5cea2442b0de`
- Branch: `main`
- Windows: Windows 11 Home, version `10.0.26200`, build `26200`, 64-bit.
- Selected serial port: `COM3`
- Serial device: WCH CH343, `USB\VID_1A86&PID_55D3\5B5E020088`
- Artifact root:
  `target/windows-ble-identity/windows_identity_strategy_20260604_120019`
- Repo hygiene artifact:
  `target/repo-hygiene/repo_hygiene_20260604_115916`

GitHub Actions for `main` was checked before hardware work. The latest main run
for commit `f892bdc` was successful. Local no-hardware validation also passed
before target work.

## Target Baseline

The target was flashed from the same `main` commit after the previously flashed
firmware did not expose the new identity commands. The normal repository path
hit the ESP-IDF Windows path-length limit, so the target image was built from a
short path clone of the same commit and flashed to `COM3`.

The default identity strategy remained `legacy_public`:

```text
BLE_IDENTITY_STRATEGIES_JSON:{"strategies":[{"default":true,...,"id":"legacy_public"},{"default":false,...,"id":"persona_static_random_experimental"}]}
BLE_IDENTITY_INFO_JSON:{"strategy":"legacy_public","address_type":"public","identity_applied":false}
```

The practical RJ12 Flight Pack topology was present:

```text
USB_STATUS:devices=3;interfaces=2;
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b10a|id=3,vid=044f,pid=b687
```

This is target-side topology evidence only. No physical control movement was
requested or performed.

## Advertising A/B

Advertisement-only A/B passed. `legacy_public` preserved the same public
address for all personas, while `persona_static_random_experimental` produced
stable distinct static-random addresses:

| Strategy | Persona | Advertised name | Address seen by Windows watcher | HID service `1812` |
| --- | --- | --- | --- | --- |
| `legacy_public` | Generic default | `USB2BLE Gamepad` | `90:70:69:07:0D:7E` | Seen |
| `legacy_public` | U6 | `USB2BLE Gamepad U6` | `90:70:69:07:0D:7E` | Seen |
| `legacy_public` | Xbox | `Xbox Wireless Controller` | `90:70:69:07:0D:7E` | Seen |
| `persona_static_random_experimental` | Generic default | `USB2BLE Gamepad` | `CE:A6:57:5C:AA:6A` | Seen |
| `persona_static_random_experimental` | U6 | `USB2BLE Gamepad U6` | `F8:34:F8:E8:CB:A0` | Seen |
| `persona_static_random_experimental` | Xbox | `Xbox Wireless Controller` | `CB:B3:AE:FA:FC:EF` | Seen |

A stability repeat after target resets saw the same three experimental
addresses again. This proves over-the-air Windows watcher visibility for the
advertised identities. It does not prove pairing, bond persistence, or host
input by itself.

## Pairing Workflow

Initial Windows cache cleanup found old USB2BLE-related nodes tied to the
public address. Automated `pnputil /remove-device` removal returned Access
Denied, so Alex removed USB2BLE-related devices through Windows Bluetooth
Settings.

Automated WinRT pairing discovered each advertised device and reported
`can_pair=true`, but each direct pair attempt returned `FAILED`. Alex completed
pairing manually through Windows Bluetooth Settings.

Important operator note: after the sequence, Alex reported that every time a new
persona was connected, he removed the previous persona first because the new
persona would not connect otherwise. Therefore this run does not prove that
Generic default, U6, and Xbox can coexist as simultaneously retained Windows
devices, and it does not prove cache-free persona switching.

## Generic Default Result

Generic default used:

```text
SET_BLE_IDENTITY_STRATEGY persona_static_random_experimental
START_BLE_GENERIC_GAMEPAD
```

Target identity and host result:

```text
current_address=CE:A6:57:5C:AA:6A
device_name=USB2BLE Gamepad
STATUS:ble=Connected;persona=generic_gamepad;bonds=false;
```

Windows PnP/HID showed the intended Generic identity:

```text
Bluetooth: USB2BLE Gamepad
HIDClass: HID-compliant game controller
VID/PID: 303a:4001
```

Virtual input replay accepted the requested Generic scenarios. The bridge stayed
connected and published reports with `last_error=none`. Edge Gamepad API probes
in this run reported zero connected gamepad observations; the probes requested a
temporary browser profile but Edge reported opening an existing browser session.
XInput remained disconnected for Generic, as expected.

## Generic Unsigned Six-Axis Result

U6 used:

```text
SET_BLE_IDENTITY_STRATEGY persona_static_random_experimental
START_BLE_GENERIC_GAMEPAD_VARIANT generic_unsigned_6axis
```

Target identity and host result:

```text
current_address=F8:34:F8:E8:CB:A0
device_name=USB2BLE Gamepad U6
STATUS:ble=Connected;persona=generic_gamepad;bonds=false;
```

Windows PnP/HID showed the intended U6 identity:

```text
Bluetooth: USB2BLE Gamepad U6
HIDClass: HID-compliant game controller
VID/PID: 303a:4002
```

Virtual input replay accepted the requested U6 scenarios. The bridge stayed
connected and published reports with `last_error=none`. Edge Gamepad API probes
again reported zero connected gamepad observations. XInput remained disconnected
for U6, as expected.

## Xbox Result

Xbox used:

```text
SET_BLE_IDENTITY_STRATEGY persona_static_random_experimental
START_BLE_XBOX_CONTROLLER
```

Target identity and host result:

```text
current_address=CB:B3:AE:FA:FC:EF
device_name=Xbox Wireless Controller
STATUS:ble=Connected;persona=xbox_wireless_controller;bonds=false;
```

Windows PnP/HID showed the intended Xbox-like BLE HID identity:

```text
Bluetooth: Xbox Wireless Controller
HIDClass: Bluetooth LE XINPUT compatible input device
HIDClass: HID-compliant game controller
VID/PID: 045e:0b13
```

XInput exposed slot 0:

```text
slot: 0
connected: true
```

The shared virtual-input bridge accepted neutral, stick, rudder, and toe-brake
scenarios and published changing Xbox reports. After stopping the bridge, direct
deterministic Xbox test reports surfaced through XInput slot 0:

| Scenario | XInput observation |
| --- | --- |
| `neutral` | `buttons=0`, triggers 0, sticks near neutral |
| `left_stick_left` | left X `-32768` |
| `left_stick_right` | left X `32767` |
| `left_stick_up` | left Y `32767` |
| `left_stick_down` | left Y `-32768` |
| `right_stick_left` | right X `-32768` |
| `right_stick_right` | right X `32767` |
| `left_trigger_max` | left trigger `255` |
| `right_trigger_max` | right trigger `255` |
| `button_a` | buttons `4096` |
| `button_b` | buttons `8192` |
| `button_x` | buttons `16384` |
| `button_y` | buttons `32768` |

Edge Gamepad API probes in this run reported zero connected gamepad
observations. This run therefore proves Windows PnP/HID/XInput exposure for the
Xbox-like BLE HID identity on Alex's PC, not Edge Gamepad API visibility.

## Reconnection Micro-Smoke

The optional reconnection micro-smoke is diagnostic only because the pairing
sequence involved manual removal between personas.

- Generic default restarted at `CE:A6:57:5C:AA:6A` and stayed advertising during
  the poll window; no automatic reconnection was observed.
- U6 restarted at `F8:34:F8:E8:CB:A0` and stayed advertising during the poll
  window; no automatic reconnection was observed.
- Xbox restarted at `CB:B3:AE:FA:FC:EF` and reached `Connected` without a new
  pairing prompt in this micro-smoke.

This is not a BLE bond-persistence pass. Target status continued to report
`bonds=false`, and the host-cache state had been changed manually during the
run.

## Conclusion

`persona_static_random_experimental` should remain explicit and experimental.
It solved the advertisement identity part of the Windows cache problem: Generic,
U6, and Xbox advertised as distinct stable static-random BLE addresses and
Windows saw those addresses.

It did not prove the desired cache-free Windows workflow. In this run,
automated pairing failed for all three personas, manual Windows Settings pairing
was required, and Alex reported that the previous persona had to be removed
before the next persona would connect. A user-facing Windows cache/removal
workflow is still required for this PC.

The strategy must not become default based on this evidence.

## Limitations

- This is evidence from Alex's Windows PC only, not broad Windows
  compatibility.
- No game/app tests were run.
- Virtual input evidence does not prove physical HOTAS movement.
- Target USB topology evidence does not prove physical HOTAS movement.
- BLE bond persistence is not proven.
- Generic/U6 Edge Gamepad API visibility is not proven by this run.
- Xbox Edge Gamepad API visibility is not proven by this run.
- Xbox console compatibility and proprietary Xbox Wireless compatibility are
  not claimed.
- Existing macOS evidence was not regression-tested in this run.
