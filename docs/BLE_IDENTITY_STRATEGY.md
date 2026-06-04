# BLE Identity Strategy

Status: diagnostic note from Windows BLE identity/cache testing on 2026-06-04.

## Current Behavior

USB2BLE currently advertises Generic default, `generic_unsigned_6axis`, and Xbox
BLE-compatible personas from the same public BLE address observed on Alex's
Windows PC:

```text
90:70:69:07:0D:7E
```

The advertised name, HID descriptor identity, and VID/PID can change by
persona, but Windows associates those identities with the same BLE address.
When the host cache is clean, Windows can pair each persona separately:

| Persona | Windows paired name | Host VID/PID result |
| --- | --- | --- |
| Generic default | `USB2BLE Gamepad` | `303a:4001` |
| Generic unsigned six-axis | `USB2BLE Gamepad U6` | `303a:4002` |
| Xbox BLE-compatible | `Xbox Wireless Controller` | `045e:0b13` |

When the host cache is not clean, Windows can reuse the first paired identity
for later personas that advertise from the same BLE address. That can make U6
or Xbox diagnostics appear as Generic on Windows even when the target has
started the intended persona.

## Cache Workflow

The current reliable Windows test workflow is:

1. Stop bridge and virtual input.
2. Run `FORGET_BLE_BONDS` on the target.
3. Remove the USB2BLE-related Bluetooth device from Windows Settings.
4. Verify no USB2BLE-related PnP/HID/Bluetooth cache candidates remain with:

   ```powershell
   python tools\windows_ble_cache_witness.py --dry-run
   ```

The cache witness intentionally targets only USB2BLE-related devices. It does
not remove unrelated Bluetooth controllers. On Alex's PC, automated
`pnputil /remove-device` removal found the right nodes but returned
`Access is denied`, so manual Windows Settings removal was required.

## Per-Persona Address Option

Per-persona BLE addresses are not required to prove one persona at a time with
manual cache cleanup. They are likely needed for a smoother multi-persona
workflow where Windows should evaluate Generic, U6, and Xbox without repeatedly
forgetting the same BLE address.

The experimental runtime strategy is:

```text
persona_static_random_experimental
```

The default strategy remains:

```text
legacy_public
```

`legacy_public` preserves release behavior: all personas use the controller's
public BLE address. `persona_static_random_experimental` derives stable
static-random BLE addresses from the board Bluetooth/public address plus the
active persona/variant salt. The strategy is explicit, runtime-only, and must
be selected before a persona is advertising or connected.

Control-plane diagnostics:

```text
LIST_BLE_IDENTITY_STRATEGIES
GET_BLE_IDENTITY_INFO
SET_BLE_IDENTITY_STRATEGY legacy_public
SET_BLE_IDENTITY_STRATEGY persona_static_random_experimental
```

Experimental address intents:

| Persona | Address intent |
| --- | --- |
| Generic default | stable Generic identity |
| Generic unsigned six-axis | stable U6 identity |
| Xbox BLE-compatible | stable Xbox identity |

The static-random address derivation sets bits 47:46 to `0b11`, as required for
a BLE static random address. The target reports the selected strategy, base
address when available, current address, applied address, address type, and last
random-address return through `GET_BLE_IDENTITY_INFO`.

This still needs explicit evidence for:

- Windows pairing and reconnection behavior for each address.
- Whether bond storage and `FORGET_BLE_BONDS` remain understandable.
- Whether host caches become easier to manage without creating stale device
  clutter.
- Whether existing macOS Generic/Xbox live bridge evidence remains preserved.

Do not make per-persona addresses the default without a dedicated witness run.

## Limitations

- This note is based on Alex's Windows PC and checked-in evidence from
  `docs/milestone-evidence/WINDOWS_BLE_IDENTITY_CACHE_DIAGNOSTIC_2026-06-04.md`.
- It does not prove BLE bond persistence.
- It does not prove physical HOTAS movement.
- It does not prove broad Windows, game/app, Xbox console, or proprietary Xbox
  Wireless compatibility.
