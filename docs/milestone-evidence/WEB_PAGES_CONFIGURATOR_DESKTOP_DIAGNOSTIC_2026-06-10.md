# Web Pages Configurator Desktop Diagnostic - 2026-06-10

Status: partial public GitHub Pages desktop-web diagnostic. The public Pages
site, firmware manifest, and public gamepad tester were reachable after deploy.
Alex then tried the public Web Serial configurator: the browser reported the
serial port connected, but the first board command timed out. A narrow Web
Serial handshake fix was pushed and deployed, but the desktop configurator
workflow is not a pass until the fixed public page is retested successfully.

This is not Web Serial configuration success, flash success, broad desktop
browser compatibility, broad Windows compatibility, game compatibility, BLE bond
persistence, physical HOTAS movement, or final calibration evidence.

## Context

- Date/time: 2026-06-10 around 11:34-12:58 Mountain time.
- Initial repo commit for this chunk: `50baf496d54f254583554b5b2d4ae2058ebe0f39`
- Public web/gamepad tester commit:
  `ac0c2c156b38c9aef1f500c9d3328638441b4002`
- Web Serial handshake fix commit:
  `e573d76bb85b6efcd6ed64edc4e749d43ec8971d`
- Branch: `main`
- CI for the Web Serial follow-up:
  <https://github.com/alexoviedo/T2/actions/runs/27298682689> completed
  successfully, including Host checks, Web app checks, ESP32-S3 target
  preflight, release packaging, and Pages deploy.
- Windows host: Alex's Windows PC. Registry reported `Windows 10 Home`,
  display version `25H2`, build `26200.8655`.
- Selected serial port during target probes: `COM3`
- Artifact root:
  `target/web-cross-platform/web_cross_platform_20260610_113446`
- Desktop Pages/configurator artifacts:
  `target/web-cross-platform/web_cross_platform_20260610_113446/pages_configurator_desktop`

No firmware was flashed for this diagnostic. No physical HOTAS controls were
moved.

## Public Pages And Firmware Manifest

The public Pages root was reachable after deploy:

```text
https://alexoviedo.github.io/T2/
HTTP/1.1 200 OK
Last-Modified: Wed, 10 Jun 2026 18:57:16 GMT
Content-Length: 8095
```

The firmware manifest was reachable:

```json
{
  "name": "USB2BLE",
  "version": "latest",
  "new_install_prompt_erase": true,
  "builds": [
    {
      "chipFamily": "ESP32-S3",
      "parts": [
        {
          "path": "usb2ble-fw-esp32s3-merged.bin",
          "offset": 0,
          "sha256": "d093d0a7f8da268a6f5a920515197a1762f5d5abe91e214e4cb19fef51a65bd5"
        }
      ]
    }
  ]
}
```

The public gamepad tester URL was also reachable:

```text
https://alexoviedo.github.io/T2/gamepad-test.html
HTTP/1.1 200 OK
Last-Modified: Wed, 10 Jun 2026 18:57:15 GMT
Content-Length: 21852
```

## Target Probe

The target was autodetected as `COM3`. Initial target status showed the explicit
startup Xbox path was active, but only the HooToo hub was reported on USB host:

```text
INFO:version=1;name=usb2ble;persona=xbox_wireless_controller;
STATUS:ble=Connected;profile=none;persona=xbox_wireless_controller;bonds=false;
USB_STATUS:devices=1;interfaces=0;
USB_DEVICES:id=1,vid=2109,pid=2813
```

A software reset was performed with `espflash reset`; no firmware was flashed.
After reset, the practical RJ12 Flight Pack topology recovered:

```text
USB_STATUS:devices=3;interfaces=2;
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b687|id=3,vid=044f,pid=b10a
```

The target retained the explicit saved startup BLE Xbox configuration:

```text
startup_ble_enabled=true
startup_ble_persona=xbox_wireless_controller
startup_ble_identity_strategy=persona_static_random_experimental
startup_ble_variant=xbox_compatibility
current_address=CB:B3:AE:FA:FC:EF
```

## Public Web Serial Observation

Alex opened the deployed public site and clicked Connect Board. The browser
reported that the serial port was connected, but the UI also reported:

```text
Timeout waiting for response
```

This means the browser-level serial port open succeeded, but the board command
handshake did not complete. The desktop Web Serial configurator workflow is not
accepted as passing from this observation.

## Web Serial Fix

Commit `e573d76bb85b6efcd6ed64edc4e749d43ec8971d` made a narrow browser-side
fix:

- set DTR/RTS with Web Serial `setSignals` when supported,
- wait 2.5 seconds after opening ESP32-S3 CDC serial,
- drain boot chatter before the first command,
- use a 10 second command-response timeout,
- only display `Connected` after `GET_CONFIG_STATUS` and `GET_CONFIG_JSON`
  both respond,
- close the browser serial port if the board handshake fails.

The fixed JS bundle was confirmed in the deployed public asset by probing for
the `dataTerminalReady`, `requestToSend`, `Connecting...`, and 10-second
timeout markers after Pages deploy.

## Conclusion

Partial diagnostic:

- Pass: GitHub Pages root loads.
- Pass: firmware manifest loads and points to an ESP32-S3 merged firmware
  artifact.
- Pass: public gamepad tester page loads.
- Pass: CI and Pages deploy were green after the Web Serial handshake fix.
- Partial/fail: the first public Web Serial configurator attempt opened the
  serial port but timed out waiting for a board response.
- Pending: retest the deployed `e573d76` public page through the browser serial
  chooser and verify `GET_CONFIG_STATUS` plus `GET_CONFIG_JSON` responses.
- Not attempted: web flashing, public Web Serial config import/save/load, and
  public UI config persistence across reset.

## Limitations

- This is a desktop Pages/configurator diagnostic, not a successful Web Serial
  configurator witness.
- The firmware flash flow was not exercised.
- Public UI config/persona/mapping persistence was not proven in this run.
- The public gamepad tester is separate from Web Serial and does not prove
  configurator behavior.
- No physical HOTAS controls were moved.
- No broad desktop browser, Windows, game/app, iOS, Quest/Android, BLE bond
  persistence, Xbox console/proprietary wireless, or final calibration claim is
  proven.
