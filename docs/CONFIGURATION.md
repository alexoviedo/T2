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
- `mappings`: source VID/PID/interface/control to target control rules.
- per-rule `invert`, optional `deadzone`, and optional `axis_to_trigger`.

If no valid config is stored, firmware keeps the existing built-in behavior.
Built-in profiles remain available and are not removed by custom runtime config.

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
