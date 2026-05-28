# Config Persistence Witness

Status: repeatable workflow for target-side runtime config protocol evidence.

This witness exercises the same serial protocol used by the Web Serial
configurator path. It is CLI protocol evidence, not browser UI evidence, and it
does not prove BLE/game/app compatibility by itself.

Current checked-in target evidence:
`docs/milestone-evidence/CONFIG_PERSISTENCE_WITNESS_2026-05-28.md` proves
runtime config import/export, `SAVE_CONFIG`, command-path `LOAD_CONFIG`, actual
board reset, post-reboot `LOAD_CONFIG`, and matching imported/loaded config for
a Generic Gamepad runtime config.

Current checked-in browser UI evidence:
`docs/milestone-evidence/WEB_SERIAL_CONFIGURATOR_SMOKE_2026-05-28.md` proves
the Google Chrome Web Serial configurator smoke path for connect,
config/status/schema/catalog load, Flight Pack Generic import, save, load, and
`START_CONFIGURED`.

## Hardware Setup

- ESP32-S3 serial/programming USB connected to the computer.
- HooToo SHUTTLE HT-UC001 powered hub connected to the ESP32-S3 USB host/OTG
  path.
- T.16000M stick USB connected to the hub.
- TWCS throttle USB connected to the hub.
- TFRP pedals connected to TWCS via RJ12.

The USB/HOTAS setup is recommended because `GET_INPUT_CATALOG` is most useful
with live normalized inputs present. The config protocol witness can still run
with only the ESP32-S3 serial connection.

## No-Hardware Validation

Safe checks without connected hardware:

```bash
./scripts/validate_no_hardware.sh
python3 -m py_compile tools/config_persistence_witness.py
```

The ESP32-S3 target preflight is also no-device, but it requires the local
Xtensa/ESP-IDF toolchain:

```bash
./scripts/check_target_build.sh
```

## Build And Flash

```bash
./scripts/check_target_build.sh
./scripts/build.sh
./scripts/flash.sh --port <PORT>
```

## Run The Witness

The script refuses to auto-select a port. If omitted, it lists likely ports:

```bash
python3 tools/config_persistence_witness.py
```

Run the default Generic Flight Pack config witness:

```bash
python3 tools/config_persistence_witness.py --port <PORT>
```

Run the strongest persistence witness, including an actual board reset after
`SAVE_CONFIG`:

```bash
python3 tools/config_persistence_witness.py --port <PORT> --reboot-after-save
```

By default the reset phase runs:

```bash
espflash reset --chip esp32s3 --port <PORT> --non-interactive
```

Override it when needed:

```bash
python3 tools/config_persistence_witness.py \
  --port <PORT> \
  --reboot-after-save \
  --reset-command 'espflash reset --chip esp32s3 --port {port} --non-interactive'
```

Use `--no-checked-in-evidence` to keep a successful target run entirely under
`target/` while reviewing the artifacts.

Run the Xbox config shape:

```bash
python3 tools/config_persistence_witness.py --port <PORT> --persona xbox
```

Run a minimal no-mapping config:

```bash
python3 tools/config_persistence_witness.py --port <PORT> --profile minimal
```

The script captures:

- `GET_INFO`
- `GET_STATUS`
- `GET_USB_STATUS`
- `LIST_USB_DEVICES`
- `GET_CONFIG_STATUS`
- `GET_CONFIG_SCHEMA`
- `GET_PERSONA_SCHEMA generic`
- `GET_PERSONA_SCHEMA xbox`
- `GET_INPUT_CATALOG`
- `GET_CONFIG_JSON`
- chunked config import with `BEGIN_CONFIG_JSON`, `CONFIG_JSON_CHUNK`, and
  `COMMIT_CONFIG_JSON`
- post-import `GET_CONFIG_STATUS` and `GET_CONFIG_JSON`
- `SAVE_CONFIG`
- `RESET_CONFIG`
- `LOAD_CONFIG`
- final `GET_CONFIG_STATUS` and `GET_CONFIG_JSON`
- with `--reboot-after-save`: close serial, reset the board, wait for reboot,
  reopen serial, capture post-reboot `GET_INFO`, `GET_STATUS`,
  `GET_CONFIG_STATUS`, then `LOAD_CONFIG`, `GET_CONFIG_STATUS`, and
  `GET_CONFIG_JSON`
- `START_CONFIGURED`
- `GET_STATUS`
- `GET_BRIDGE_STATUS`

Artifacts are written under:

```text
target/config-persistence-witness/config_persistence_<timestamp>/
  serial_transcript.txt
  transcript.json
  summary.json
  imported_config.json
  loaded_config.json
  operator_notes.md
```

## Evidence Boundaries

This workflow can prove that a target accepted runtime config JSON, persisted it
through `SAVE_CONFIG`, restored it through the `RESET_CONFIG` plus `LOAD_CONFIG`
command path, and accepted `START_CONFIGURED`.

It proves durable reboot persistence only when `--reboot-after-save` succeeds
and `summary.json` reports `reboot_persistence_proven: true`. Browser UI smoke
is a separate workflow from this CLI witness.

## Manual Web Serial UI Smoke

After the CLI witness passes, the browser UI can be smoked separately:

```bash
cd web
npm ci
npm run dev
```

Open the local Vite URL in Chrome or Edge, connect to the same serial port, and
exercise the Configure tab:

- connect over Web Serial
- load board config/status
- choose the Flight Pack Generic or Flight Pack Xbox preset
- commit/import config
- save config
- load config
- start configured

Save screenshots or copied serial-log excerpts under `target/web-serial-smoke/`.
Only summarize a new browser/platform run as checked-in Web Serial UI evidence
after reviewing those real browser artifacts.

## Checked-In Evidence

After a successful hardware run, the script may write a concise summary under:

```text
docs/milestone-evidence/CONFIG_PERSISTENCE_WITNESS_<YYYY-MM-DD>.md
```

Pass `--no-checked-in-evidence` to suppress that and keep only `target/`
artifacts.

Only check in real transcript excerpts from the generated artifacts. Do not add
synthetic target evidence.
