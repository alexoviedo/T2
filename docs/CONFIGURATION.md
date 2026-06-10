# Runtime Configuration

USB2BLE now has a versioned runtime configuration substrate. The first UI
transport target is Web Serial over USB so a browser app can use the existing
serial control plane. A future BLE GATT Config Mode should reuse the same JSON
model and chunk protocol instead of inventing a second format.

## Data Model

`RuntimeConfig` is JSON and currently uses `schema_version: 1`. It includes:

- `selected_persona`: `generic_gamepad` or `xbox_wireless_controller`.
- `selected_profile`: a built-in profile ID or `custom_runtime`.
- `bridge`: `auto_start_persona`, `auto_start_bridge`, and `rate_hz`.
- `startup_ble`: optional boot-time BLE persona startup, disabled by default.
- `mappings`: source VID/PID/interface/control to target control rules.
- per-rule `invert`, optional `deadzone`, and optional `axis_to_trigger`.

If no valid config is stored, firmware keeps the existing built-in behavior.
Built-in profiles remain available and are not removed by custom runtime config.

`startup_ble` is explicit product workflow configuration, not a global default.
When disabled, boot/reset behavior is unchanged and no BLE persona starts
automatically. When enabled, firmware applies the configured BLE identity
strategy and starts the configured BLE persona after boot. The initial supported
startup target is the Xbox-compatible persona with `xbox_compatibility`; this
lets a user opt into the already witnessed single-persona Xbox path without
making `persona_static_random_experimental` the project default.

## Flight Pack Presets

The practical RJ12 Flight Pack presets use the checked-in axis-label and
mapping-refinement evidence as their source of truth. Generic maps stick
`x/y`, TWCS throttle `z`, RJ12 rudder `rx`, and the two RJ12 toe brakes to
`ry/rz`. Xbox maps stick `left_x/left_y`, RJ12 rudder `right_x`, and the two
RJ12 toe brakes to `left_trigger/right_trigger`; TWCS throttle is intentionally
unmapped in the Xbox preset because the trigger slots are used for toe brakes.

## Serial Protocol

Machine-oriented endpoints:

```text
GET_CONFIG_STATUS
GET_CONFIG_SCHEMA
GET_PERSONA_SCHEMA generic
GET_PERSONA_SCHEMA xbox
GET_INPUT_CATALOG
GET_CONFIG_JSON
BEGIN_CONFIG_JSON <total_chunks> <sha256|none>
CONFIG_JSON_CHUNK <index> <base64url_data>
COMMIT_CONFIG_JSON
RESET_CONFIG
SAVE_CONFIG
LOAD_CONFIG
START_CONFIGURED
GET_STARTUP_BLE_CONFIG
ENABLE_STARTUP_BLE <true|false>
SET_STARTUP_BLE_PERSONA <persona_id>
SET_STARTUP_BLE_IDENTITY_STRATEGY <strategy_id>
SET_STARTUP_BLE_VARIANT <variant_id>
```

Import is validated before commit. Invalid JSON, schema mismatch, unknown
persona/target controls, duplicate target mappings, invalid transforms,
oversized payloads, missing/out-of-order chunks, bad base64, checksum mismatch,
and storage failures return explicit `ERROR:` lines.

## Persistence

The `ConfigStore` trait now persists validated `RuntimeConfig`. Host tests use
the in-memory store. ESP32-S3 target builds use ESP-IDF NVS via the platform
crate. If stored config is missing or invalid, firmware falls back safely to the
default runtime config and reports status through `GET_CONFIG_STATUS`.

Startup BLE fields are persisted with the rest of runtime config. Existing
schema-version-1 JSON that does not contain `startup_ble` remains valid; the
field defaults to disabled with `legacy_public` identity strategy. `SAVE_CONFIG`
is required for startup BLE settings to survive reset or power-cycle.

The first hardware witness for this path is
`docs/milestone-evidence/WINDOWS_XBOX_STARTUP_RECONNECT_WITNESS_2026-06-09.md`.
It proves an explicit saved Xbox startup config on Alex's Windows PC, not a
global default change and not broad Windows/game compatibility.

## Smoke Tool

`tools/configure_board.py` is a protocol harness, not the product UI:

```bash
python3 tools/configure_board.py --port <PORT> show
python3 tools/configure_board.py --port <PORT> schema
python3 tools/configure_board.py --port <PORT> catalog
python3 tools/configure_board.py --port <PORT> export
python3 tools/configure_board.py --port <PORT> import path/to/config.json
python3 tools/configure_board.py --port <PORT> preset flight-pack-xbox
python3 tools/configure_board.py --port <PORT> save
python3 tools/configure_board.py --port <PORT> load
python3 tools/configure_board.py --port <PORT> reset
python3 tools/configure_board.py --port <PORT> start-configured
```

Transcripts are saved under `target/configure-board/<timestamp>/`.

## Persistence Witness

For a complete target-side evidence run that captures baseline status, schema,
catalog, chunked import, save/reset/load, and `START_CONFIGURED`, use:

```bash
python3 tools/config_persistence_witness.py --port <PORT>
```

See `docs/CONFIG_PERSISTENCE_WITNESS.md`. The witness proves the CLI/Web
Serial-compatible protocol path, not browser UI behavior or game/app
compatibility.
