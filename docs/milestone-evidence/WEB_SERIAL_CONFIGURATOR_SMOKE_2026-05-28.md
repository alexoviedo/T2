# Web Serial Configurator Smoke - 2026-05-28

## Summary

Real browser UI evidence proves the USB2BLE configurator can connect to the
ESP32-S3 over Web Serial, load config/status/schema/catalog data, import the
Flight Pack Generic preset through the chunked config protocol, save, load, and
run `START_CONFIGURED`.

This is browser Web Serial configurator smoke evidence only. It is not
game/app compatibility evidence, BLE/gamepad host success evidence, BLE bond
persistence evidence, or final Flight Pack calibration evidence.

## Environment

- Date/time UTC: `20260528T230840Z` to `20260528T230941Z`
- Commit SHA at run: `62bf5a64e8be9f8e67d53cc47b51a14803a4660c`
- Run included the local `web/src/serial.ts` response-token hardening in this
  review chunk.
- Browser: Google Chrome `148.0.7778.179`
- Local URL: `http://127.0.0.1:5173/T2/`
- Serial port selected in Chrome Web Serial chooser:
  `/dev/cu.usbmodem5B5E0200881`
- Generated artifacts:
  `target/web-serial-smoke/web_serial_smoke_20260528T230840Z`

## Hardware Topology

- ESP32-S3 serial/programming USB connected to the computer.
- HooToo SHUTTLE HT-UC001 powered hub on the ESP32-S3 USB host/OTG path.
- T.16000M stick USB and TWCS throttle USB connected through the hub.
- TFRP pedals connected to TWCS via RJ12 when present.

The browser UI input catalog included `Thrustmaster T.16000M` controls and
`Thrustmaster TWCS/RJ12` controls.

## Commands And Checks Run

```bash
git status --short
ls /dev/cu.* /dev/tty.* 2>/dev/null | grep -E 'usb|wch|modem|serial'
python3 tools/serial_command.py --port /dev/cu.usbmodem5B5E0200881 --timeout 3 GET_INFO GET_STATUS
./scripts/validate_no_hardware.sh
./scripts/check_target_build.sh
cd web && npm ci && npm test && npm run build
cd web && npm run dev -- --host 127.0.0.1
python3 target/web-serial-smoke/selenium_web_serial_smoke.py
```

The explicit `web` command initially failed under `/usr/local/bin/node`
`v18.16.1`; rerunning with local nvm Node `v20.19.4` passed.

## UI Steps Witnessed

- Chrome opened the configurator at the local Vite URL.
- The operator selected `USB Single Serial (cu.usbmodem5B5E0200881)` from the
  Chrome Web Serial chooser.
- The UI reported `Connected`.
- The UI loaded `GET_CONFIG_STATUS` and `GET_CONFIG_JSON`.
- The UI loaded Generic and Xbox persona schemas.
- The UI loaded the input catalog.
- The UI applied the Flight Pack Generic preset through
  `BEGIN_CONFIG_JSON`, `CONFIG_JSON_CHUNK`, and `COMMIT_CONFIG_JSON`.
- The UI ran `SAVE_CONFIG`.
- The UI ran `LOAD_CONFIG` and refreshed `GET_CONFIG_JSON`.
- The UI ran `START_CONFIGURED`.

## Result Summary

- `browser_web_serial_ui_smoke_passed`: `true`
- `navigator_serial_supported`: `true`
- `connected_ui`: `true`
- `config_status_loaded`: `true`
- `schemas_loaded`: `true`
- `catalog_loaded`: `true`
- `import_commit_succeeded`: `true`
- `save_succeeded`: `true`
- `load_succeeded`: `true`
- `start_configured_succeeded`: `true`
- `game_app_compatibility_proven`: `false`
- `ble_gamepad_host_success_proven`: `false`
- `ble_bond_persistence_proven`: `false`
- `flight_pack_calibration_proven`: `false`
- `errors`: `[]`

## UI Serial Log Excerpts

```text
TX: GET_CONFIG_STATUS
CONFIG_STATUS:valid=true;source=runtime;persona=generic_gamepad;profile=custom_runtime;mappings=4;import_active=false;last_error=none;

TX: GET_PERSONA_SCHEMA generic
RX: PERSONA_SCHEMA_JSON:{"controls":[...],"persona":"generic_gamepad"}

TX: GET_PERSONA_SCHEMA xbox
RX: PERSONA_SCHEMA_JSON:{"controls":[...],"persona":"xbox_wireless_controller"}

TX: GET_INPUT_CATALOG
RX: INPUT_CATALOG_JSON:{"entries":[... "source_display_hint":"Thrustmaster T.16000M" ... "source_display_hint":"Thrustmaster TWCS/RJ12" ...]}

TX: BEGIN_CONFIG_JSON 14 <sha256>
RX: CONFIG_IMPORT:state=started;total_chunks=14;received_chunks=0;bytes=0;
TX: CONFIG_JSON_CHUNK 0 <base64url>
...
TX: CONFIG_JSON_CHUNK 13 <base64url>
RX: CONFIG_IMPORT:state=chunk;total_chunks=14;received_chunks=14;bytes=965;
TX: COMMIT_CONFIG_JSON
RX: CONFIG_IMPORT:state=committed;total_chunks=0;received_chunks=0;bytes=965;

TX: SAVE_CONFIG
RX: CONFIG_ACTION:action=save;state=ok;

TX: LOAD_CONFIG
RX: CONFIG_ACTION:action=load;state=ok;
TX: GET_CONFIG_JSON
RX: CONFIG_JSON:{"schema_version":1,...,"display_name":"Flight Pack Generic",...}

TX: START_CONFIGURED
RX: CONFIG_ACTION:action=start_configured;state=ok;detail=persona=generic_gamepad;bridge=false;;
```

The UI log also contains asynchronous `[USB_REPORT]`, `[REPORT]`, and
`ERROR:Generic` lines while the Generic persona was active. The web serial
reader was hardened in this chunk so expected command responses are still
recognized when this live target chatter is interleaved with command replies.

## Artifact Paths

- Summary: `target/web-serial-smoke/web_serial_smoke_20260528T230840Z/summary.json`
- UI serial log: `target/web-serial-smoke/web_serial_smoke_20260528T230840Z/ui_serial_log.txt`
- Browser console log: `target/web-serial-smoke/web_serial_smoke_20260528T230840Z/browser_console.log`
- Connected screenshot:
  `target/web-serial-smoke/web_serial_smoke_20260528T230840Z/browser_screenshot_connected.png`
- Configured screenshot:
  `target/web-serial-smoke/web_serial_smoke_20260528T230840Z/browser_screenshot_configured.png`

## Limitations

- Browser coverage is limited to Google Chrome `148.0.7778.179` on this macOS
  host.
- The Chrome Web Serial chooser required manual operator selection of the
  serial port; the rest of the UI flow was automated.
- `START_CONFIGURED` returned `bridge=false`; this witness does not claim live
  bridge publish success.
- BLE/gamepad host success and game/app compatibility are not claimed.
- BLE bond persistence is not claimed.
- Final Flight Pack calibration/deadzone semantics are not claimed.
