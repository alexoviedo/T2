# Web Pages Configurator Desktop Witness - 2026-06-12

Status: public GitHub Pages desktop Web Serial configurator witness on Alex's
Windows PC. The deployed public configurator connected to the ESP32-S3 through
the browser serial chooser, imported the Flight Pack Xbox config, saved it,
loaded it, started the configured Xbox persona, and the saved config persisted
across a target soft reset.

This does not prove web flashing, mobile Web Serial, broad browser support,
broad Windows compatibility, game compatibility, physical HOTAS movement, BLE
bond persistence, Xbox console support, proprietary Xbox Wireless support, or
calibration quality.

## Context

- Date/time: 2026-06-12 around 10:33-11:05 Mountain time.
- Branch: `main`
- Starting commit for retest: `6429e5ad5d4d19120b6d1b4884655fe1eaa9044e`
- Web Serial framing fix commit:
  `85ffa4ba63c5a2bd2b26b55cbb7e92fe188a93b6`
- CI for the framing fix:
  <https://github.com/alexoviedo/T2/actions/runs/27429847862> completed
  successfully.
- Windows host: Alex's Windows PC. `Get-ComputerInfo` reported
  `Windows 10 Home`, version `2009`, build `26200`.
- Selected serial port: `COM3`
- Serial device: WCH CH343 / ESP32-S3 programming USB.
- Artifact root:
  `target/web-cross-platform/web_configurator_retest_20260610_131406`

No firmware was flashed for this witness. No physical HOTAS controls were moved.

## Public Pages Deployment

After the framing fix, the public Pages root was reachable and showed a fresh
deploy timestamp:

```text
https://alexoviedo.github.io/T2/
HTTP/1.1 200 OK
Last-Modified: Fri, 12 Jun 2026 16:53:53 GMT
Content-Length: 8095
```

The deployed JavaScript asset was downloaded and inspected from:

```text
https://alexoviedo.github.io/T2/assets/index-C1S4BG25.js
```

The served bundle contained the newline-only Web Serial writer from commit
`85ffa4b`. That replaced the previous CRLF write path that produced one
interleaved `ERROR:Generic` response per browser command in the earlier retest
log.

## Public Web Serial Configurator Retest

Alex opened:

```text
https://alexoviedo.github.io/T2/?v=85ffa4b
```

and selected the ESP32-S3 / CH343 / `COM3` device in the browser serial chooser.
The page reported `Connected`.

The first clean connect log showed the expected board handshake:

```text
TX: GET_CONFIG_STATUS
RX: CONFIG_STATUS:valid=true;source=runtime;persona=xbox_wireless_controller;profile=custom_runtime;mappings=18;startup_ble_enabled=true;startup_ble_persona=xbox_wireless_controller;startup_ble_identity_strategy=persona_static_random_experimental;startup_ble_variant=xbox_compatibility;import_active=false;last_error=none;
TX: GET_CONFIG_JSON
RX: CONFIG_JSON:{"schema_version":1,"metadata_version":1,"display_name":"Flight Pack Xbox",...}
```

The pasted public UI log summary was:

```text
TX count: 180
RX: ERROR:Generic count: 0
SAVE_CONFIG ok count: 1
LOAD_CONFIG ok count: 1
START_CONFIGURED ok count: 1
```

This fixes the previously observed public Web Serial symptom where the page
reported connected but also showed `Timeout waiting for response` or repeated
interleaved `ERROR:Generic` lines.

## Config Import Save Load Start

The public UI imported the Flight Pack Xbox config as 55 JSON chunks and
committed it:

```text
CONFIG_IMPORT:state=committed;total_chunks=0;received_chunks=0;bytes=3890;
CONFIG_STATUS:valid=true;source=runtime;persona=xbox_wireless_controller;profile=custom_runtime;mappings=18;startup_ble_enabled=true;startup_ble_persona=xbox_wireless_controller;startup_ble_identity_strategy=persona_static_random_experimental;startup_ble_variant=xbox_compatibility;import_active=false;last_error=none;
```

The public UI saved the config:

```text
CONFIG_ACTION:action=save;state=ok;
CONFIG_STATUS:valid=true;source=saved;persona=xbox_wireless_controller;profile=custom_runtime;mappings=18;startup_ble_enabled=true;startup_ble_persona=xbox_wireless_controller;startup_ble_identity_strategy=persona_static_random_experimental;startup_ble_variant=xbox_compatibility;import_active=false;last_error=none;
```

The public UI loaded the config:

```text
CONFIG_ACTION:action=load;state=ok;
CONFIG_STATUS:valid=true;source=loaded;persona=xbox_wireless_controller;profile=custom_runtime;mappings=18;startup_ble_enabled=true;startup_ble_persona=xbox_wireless_controller;startup_ble_identity_strategy=persona_static_random_experimental;startup_ble_variant=xbox_compatibility;import_active=false;last_error=none;
```

The public UI started the configured persona:

```text
CONFIG_ACTION:action=start_configured;state=ok;detail=persona=xbox_wireless_controller;bridge=false;;
```

## Target State Before Reset

After Alex disconnected the browser from `COM3`, the CLI probe confirmed the
same saved/runtime config and target topology:

```text
CONFIG_STATUS:valid=true;source=runtime;persona=xbox_wireless_controller;profile=custom_runtime;mappings=18;startup_ble_enabled=true;startup_ble_persona=xbox_wireless_controller;startup_ble_identity_strategy=persona_static_random_experimental;startup_ble_variant=xbox_compatibility;import_active=false;last_error=none;
STARTUP_BLE_CONFIG_JSON:{"compatibility_variant":"xbox_compatibility","enabled":true,"identity_strategy":"persona_static_random_experimental","persona":"xbox_wireless_controller",...}
BLE_IDENTITY_INFO_JSON:... "current_address":"CB:B3:AE:FA:FC:EF" ... "address_type":"static_random" ...
USB_STATUS:devices=3;interfaces=2;
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b687|id=3,vid=044f,pid=b10a
```

## Reset Persistence

The target was reset with:

```text
espflash reset --chip esp32s3 --port COM3 --non-interactive
```

No serial reconfiguration commands were sent after reset. The post-reset probe
showed the config loaded from storage and startup BLE reapplied the Xbox persona
with the explicit experimental identity strategy:

```text
INFO:version=1;name=usb2ble;persona=xbox_wireless_controller;
CONFIG_STATUS:valid=true;source=loaded;persona=xbox_wireless_controller;profile=custom_runtime;mappings=18;startup_ble_enabled=true;startup_ble_persona=xbox_wireless_controller;startup_ble_identity_strategy=persona_static_random_experimental;startup_ble_variant=xbox_compatibility;import_active=false;last_error=none;
STARTUP_BLE_CONFIG_JSON:{"compatibility_variant":"xbox_compatibility","enabled":true,"identity_strategy":"persona_static_random_experimental","persona":"xbox_wireless_controller",...}
BLE_IDENTITY_INFO_JSON:... "current_address":"CB:B3:AE:FA:FC:EF" ... "identity_applied":true ...
USB_STATUS:devices=3;interfaces=2;
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b687|id=3,vid=044f,pid=b10a
```

The target-side Xbox deterministic report path also responded after reset. The
first attempt was invalid because the command argument was accidentally split by
the shell and is preserved in the artifact as operator error. The corrected run
passed:

```text
PUBLISH_XBOX_TEST_REPORT left_stick_right
BLE_ACTION:action=publish_xbox_test_report;state=Connected;persona=xbox_wireless_controller;report_id=1;bytes=ffff0080008000800000000000000000;
PUBLISH_XBOX_TEST_REPORT neutral
BLE_ACTION:action=publish_xbox_test_report;state=Connected;persona=xbox_wireless_controller;report_id=1;bytes=00800080008000800000000000000000;
...
"last_report_send_status":"ok"
"publish_ok_count":2
```

## Conclusion

Pass, with narrow scope:

- Pass: public Pages root was deployed and reachable after commit `85ffa4b`.
- Pass: public Web Serial configurator connected through the browser serial
  chooser and completed `GET_CONFIG_STATUS` plus `GET_CONFIG_JSON`.
- Pass: public UI Flight Pack Xbox import/commit completed without interleaved
  `ERROR:Generic` responses.
- Pass: public UI `SAVE_CONFIG`, `LOAD_CONFIG`, and `START_CONFIGURED`
  completed.
- Pass: after target soft reset, the saved config loaded automatically with
  Xbox persona, 18 mappings, startup BLE enabled, and
  `persona_static_random_experimental`.
- Pass: after reset, target diagnostics still reported static-random Xbox
  address `CB:B3:AE:FA:FC:EF` and the practical RJ12 Flight Pack topology.
- Pass: corrected deterministic Xbox report publishes succeeded after reset.
- Not attempted: web flashing.
- Not attempted: iPhone, Quest, or mobile browser testing.
- Not attempted: physical HOTAS movement.

## Limitations

- This is one Windows desktop Web Serial witness on Alex's PC.
- Browser serial chooser approval was manual.
- The web flash flow was not exercised.
- The public Gamepad API tester remains covered by separate evidence and is not
  upgraded by this Web Serial configurator witness.
- Virtual/deterministic report evidence does not prove physical HOTAS movement.
- This does not prove broad browser/platform support, broad Windows
compatibility, broad game compatibility, Xbox console support, proprietary
Xbox Wireless support, BLE bond persistence, or calibration quality.
