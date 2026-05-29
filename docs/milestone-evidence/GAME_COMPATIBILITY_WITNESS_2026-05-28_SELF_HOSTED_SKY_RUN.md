# Self-Hosted Browser Game Compatibility Witness - 2026-05-28

Status: real ESP32-S3 + Google Chrome evidence captured for the refined Generic
Flight Pack profile in a self-hosted browser game/app surface.

This witness proves that the repo-local `USB2BLE Sky Run` browser mini-game can
see `USB2BLE Gamepad`, consume refined Generic axes, update in-game ship state,
score gates, and complete a mission while the Generic live bridge remains
connected and publishing. This is a narrow self-hosted browser game/app
compatibility smoke only. It is not broad game compatibility, not native
app/game compatibility, not Xbox compatibility, not BLE bond persistence, not
final calibration quality, and not three-separate-USB Flight Pack streaming.

## Run Metadata

- Date/time: 2026-05-28 22:19-22:21 MDT; artifact stamp
  `20260529T041959Z`.
- Commit SHA before this working-tree change:
  `c284b03f9472c40aaf2c332584c893854733602f`.
- Selected serial port: `/dev/cu.usbmodem5B5E0200881`.
- Host OS: macOS 12.7.5 (`21H1222`).
- Browser: Google Chrome `148.0.7778.179`.
- App/game: `USB2BLE Sky Run`.
- App/game URL during run: `http://127.0.0.1:8770/`.
- Self-hosted app path: `tools/browser_game_compat/index.html`.
- Target artifact directory:
  `target/game-compatibility/self_hosted_sky_run_generic_20260529T041959Z`.

## Hardware And BLE Context

- ESP32-S3 serial/programming USB connected to the Mac.
- HooToo SHUTTLE HT-UC001 powered hub on the ESP32-S3 USB host/OTG path.
- T.16000M stick USB and TWCS throttle USB connected through the HooToo hub.
- TFRP pedals connected to TWCS by RJ12.
- macOS Bluetooth reported `USB2BLE Gamepad`, address
  `90:70:69:07:0D:7E`, VID `0x303A`, PID `0x4001`.

The target reported the expected devices:

```text
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b10a|id=3,vid=044f,pid=b687
```

## Commands Run

```bash
git status --short
./scripts/validate_no_hardware.sh
./scripts/check_target_build.sh
python3 tools/check_evidence_docs.py --verbose
python3 tools/serial_command.py --port /dev/cu.usbmodem5B5E0200881 --timeout 3 GET_INFO GET_STATUS GET_USB_STATUS LIST_USB_DEVICES GET_CONFIG_STATUS GET_BRIDGE_STATUS
python3 tools/browser_game_compat_witness.py --port /dev/cu.usbmodem5B5E0200881 --duration-seconds 65
```

The first isolated-Chrome-profile attempt did not expose a gamepad to the page.
The accepted run used the normal Chrome profile, matching the previous
host-visible browser witnesses. No Alex action was required.

## Active Persona And Config

The target was already running the persisted refined Generic runtime config.
`START_CONFIGURED` succeeded and kept the Generic bridge enabled:

```text
CONFIG_STATUS:valid=true;source=loaded;persona=generic_gamepad;profile=custom_runtime;mappings=6;import_active=false;last_error=none;
CONFIG_ACTION:action=start_configured;state=ok;detail=persona=generic_gamepad;bridge=true;;
```

## Bridge Result

| Check | Result |
| --- | --- |
| Bridge persona | `generic_gamepad` |
| Bridge enabled | start and end |
| Serial bridge samples | 13 |
| `published` counter | `9550 -> 9595`, delta `45` |
| `skipped_not_connected` delta | `0` |
| `skipped_not_ready` delta | `0` |
| Bridge `last_error` values | `none` |

Representative serial sample:

```text
BRIDGE_STATUS:enabled=true;persona=generic_gamepad;rate_hz=50;last_publish_ms=13892355;published=9595;skipped_duplicate=9448;skipped_rate=0;skipped_not_connected=1;skipped_not_ready=0;last_error=none;
```

## App/Game Result

The mini-game is a canvas game with a ship, gates, score, and mission state.
It consumes the browser Gamepad object as an in-app control source:

- A0/A1 influence stick steering.
- A2 is used as throttle.
- A3 is used as rudder.
- A4/A5 are used as toe-brake differential input.

Captured app/game summary:

| App/game check | Result |
| --- | --- |
| Controller identity | `USB2BLE Gamepad (Vendor: 303a Product: 4001)` |
| Connected game events | 139 |
| Game-state events | 135 |
| Max observed axis magnitude | `1.0` |
| Mission completed | `true` |
| Max score | `200` |
| Ship delta X | about `597.8` |
| Ship delta Y | about `-290` |

Representative browser game event:

```json
{"axes":[-0.029,-0.041,1,0.003,-1,-1,0,0,0,1.286],"connected":true,"gamepad_id":"USB2BLE Gamepad (Vendor: 303a Product: 4001)","kind":"game_state","mission_completed":true,"score":200}
```

Conclusion: pass for the narrow self-hosted browser game/app smoke, not broad
compatibility.
The app recognized the controller, consumed refined Generic axes, changed
visible game state, and completed the mission while serial bridge counters
remained clean.

## Artifacts

- Summary:
  `target/game-compatibility/self_hosted_sky_run_generic_20260529T041959Z/summary.json`
- Browser game events:
  `target/game-compatibility/self_hosted_sky_run_generic_20260529T041959Z/browser_game_events.jsonl`
- Serial transcript:
  `target/game-compatibility/self_hosted_sky_run_generic_20260529T041959Z/serial_transcript.txt`
- Bridge samples:
  `target/game-compatibility/self_hosted_sky_run_generic_20260529T041959Z/bridge_status_samples.jsonl`
- Operator notes:
  `target/game-compatibility/self_hosted_sky_run_generic_20260529T041959Z/operator_notes.md`

Screenshots were not captured in this run; browser game event logs and serial
bridge samples are the app/game evidence artifacts.

## Limitations

- This is self-hosted browser game/app compatibility smoke only.
- It does not prove compatibility with external browser games.
- It does not prove native app/game compatibility.
- It does not prove broad game compatibility from one app surface.
- It does not prove Xbox game compatibility.
- It does not prove BLE bond persistence.
- It does not prove final Flight Pack calibration/deadzone feel.
- It does not prove broad host/browser support or iPhone compatibility.
- It uses the practical two-USB RJ12 topology, not three separate USB Flight
  Pack devices streaming simultaneously.
