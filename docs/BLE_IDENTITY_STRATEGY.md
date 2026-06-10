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
manual cache cleanup. They are useful for separating advertised identities, but
the first Windows static-random witness did not prove a smooth multi-persona
workflow where Windows can evaluate Generic, U6, and Xbox without repeatedly
forgetting/removing devices.

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

The identity strategy can also be placed in the opt-in persisted startup BLE
configuration:

```text
SET_STARTUP_BLE_IDENTITY_STRATEGY persona_static_random_experimental
ENABLE_STARTUP_BLE true
SAVE_CONFIG
```

That configuration is disabled by default. It exists so a user-selected
single-persona workflow can boot directly into a tested mode without changing
the global default identity behavior.

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

## Static-Random Windows Diagnostic

The 2026-06-04 Windows static-random diagnostic proved advertisement identity
separation on Alex's Windows PC:

| Persona | Experimental address | Windows watcher result |
| --- | --- | --- |
| Generic default | `CE:A6:57:5C:AA:6A` | `USB2BLE Gamepad`, HID `1812` seen |
| Generic unsigned six-axis | `F8:34:F8:E8:CB:A0` | `USB2BLE Gamepad U6`, HID `1812` seen |
| Xbox BLE-compatible | `CB:B3:AE:FA:FC:EF` | `Xbox Wireless Controller`, HID `1812` seen |

Each persona could be paired individually through Windows Bluetooth Settings
after automated WinRT pairing failed. Windows PnP/HID then exposed the intended
VID/PID for each persona, and Xbox exposed XInput slot 0 deterministic report
changes. However, Alex reported that every new persona connection required
removing the previous persona first, otherwise the next persona would not
connect.

Conclusion: `persona_static_random_experimental` remains useful diagnostic
infrastructure, but it does not yet solve Windows cache-free switching or
coexistence. It must remain explicit and non-default.

## Single-Persona Xbox Reconnect Diagnostic

The 2026-06-04 single-persona Xbox reconnect diagnostic used the same explicit
experimental Xbox address:

```text
CB:B3:AE:FA:FC:EF
```

Baseline manual Windows Settings pairing still worked and deterministic Xbox
reports drove XInput. After target soft reset, the runtime identity strategy
and active persona were not persisted: the target returned to `legacy_public`,
no active persona, and `bonds=false`. Reapplying
`persona_static_random_experimental` plus `START_BLE_XBOX_CONTROLLER` restored
apparent target/Windows/XInput connection state, but deterministic reports did
not move XInput and later publish attempts returned `ERROR:Generic`.

The 2026-06-09 follow-up added explicit reconnect/report-delivery diagnostics
and a clean stop path:

```text
STOP_BLE_PERSONA
GET_BLE_CONNECTION_INFO
GET_BLE_BOND_INFO
DISCONNECT_BLE_HOST
```

After one manual Windows Settings baseline pair, `STOP_BLE_PERSONA` followed by
`START_BLE_XBOX_CONTROLLER` reconnected the same Xbox address and deterministic
reports again moved XInput. A target soft reset still returned runtime state to
`legacy_public` with no active persona, but `GET_BLE_BOND_INFO` reported one
stored ESP-IDF bond. Reapplying the explicit experimental strategy and Xbox
persona restored XInput report delivery without clearing Windows cache:

```text
current_address=CB:B3:AE:FA:FC:EF
bond_count=1
bonds_present=true
last_report_send_status=ok
publish_ok_count=10
```

Direct `DISCONNECT_BLE_HOST` remains unsupported on the ESP32 target path, and
authentication/encryption event fields remain `unknown`. This means the
static-random address plus explicit persona reapply can support the witnessed
single-persona Xbox reconnect/report-delivery path on Alex's PC, but it still
does not prove durable BLE bond persistence, power-cycle behavior, or automatic
persona/identity persistence.

The later 2026-06-09 startup reconnect witness added explicit persisted startup
BLE config. With startup BLE enabled for Xbox plus
`persona_static_random_experimental`, target soft reset and an
operator-assisted ESP32-S3 serial USB power-cycle both restored the same Xbox
address/persona without serial reapply, and deterministic reports moved Windows
XInput after a one-time startup warm restart:

```text
startup_ble_enabled=true
current_address=CB:B3:AE:FA:FC:EF
warm_restart_attempted=true
warm_restart_applied=true
last_report_send_status=ok
publish_ok_count=18
```

This is still explicit single-persona Xbox evidence on Alex's PC. It does not
make static-random identity the default and it does not prove cache-free
multi-persona switching or durable BLE bond persistence.

The 2026-06-10 startup reconnect soak added richer ESP-IDF auth/security
telemetry to `GET_BLE_BOND_INFO` and ran five target soft resets without
Windows remove/re-pair. Each cycle restored the explicit startup Xbox persona
at:

```text
CB:B3:AE:FA:FC:EF
```

XInput slot 0 stayed connected, and deterministic left-stick, trigger, and A
button reports moved XInput after every reset. The new bond diagnostics reported
one bond-list entry and auth-complete success for Windows address
`50:FE:0C:02:AE:6A`, but also reported `last_auth_complete_key_present=false`,
a stored key mask limited to `peer_identity_key`, and no dedicated encryption
event. That is useful reconnect/report-delivery evidence, not a full durable
BLE bond persistence claim.

This still needs explicit evidence or fixes for:

- A controlled no-removal Windows pairing matrix that captures the exact blocker
  when the previous persona is left paired.
- Active encryption/authentication state or more complete BLE security key
  telemetry than the current auth-complete and bond-list diagnostics expose.
- True host disconnect/reconnect support, or a documented unsupported status for
  this ESP-IDF HIDD layer.
- Whether host caches can be managed without creating stale device clutter.
- Whether existing macOS Generic/Xbox live bridge evidence remains preserved.

Do not make per-persona addresses the default without a dedicated witness run.

## Limitations

- This note is based on Alex's Windows PC and checked-in evidence from
  `docs/milestone-evidence/WINDOWS_BLE_IDENTITY_CACHE_DIAGNOSTIC_2026-06-04.md`
  and
  `docs/milestone-evidence/WINDOWS_PER_PERSONA_STATIC_RANDOM_IDENTITY_DIAGNOSTIC_2026-06-04.md`.
- It does not prove cache-free Windows persona switching or coexistence.
- It does not prove BLE bond persistence or reliable reconnect/report delivery;
  see
  `docs/milestone-evidence/WINDOWS_XBOX_RECONNECT_DIAGNOSTIC_2026-06-04.md`
  and the follow-up
  `docs/milestone-evidence/WINDOWS_XBOX_RECONNECT_FIX_DIAGNOSTIC_2026-06-09.md`;
  startup reset/power-cycle evidence for the single-persona Xbox path is in
  `docs/milestone-evidence/WINDOWS_XBOX_STARTUP_RECONNECT_WITNESS_2026-06-09.md`,
  and a five-cycle soft-reset soak with richer bond/auth telemetry is in
  `docs/milestone-evidence/WINDOWS_XBOX_STARTUP_RECONNECT_SOAK_WITNESS_2026-06-10.md`.
- It does not prove physical HOTAS movement.
- It does not prove broad Windows, game/app, Xbox console, or proprietary Xbox
  Wireless compatibility.
