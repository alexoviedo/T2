# Refined Generic Live Bridge Soak Witness - 2026-05-28

Status: real ESP32-S3 + macOS Chrome browser Gamepad API evidence captured for
a 300-second refined practical RJ12 Flight Pack Generic live bridge soak.

This proves the persisted refined Generic Flight Pack runtime config can start
the Generic live bridge and remain host-visible through browser Gamepad API
sampling for a 300-second run. This is host-visible browser evidence only. It
is not real game/app compatibility, Xbox host-visible refined mapping evidence,
BLE bond persistence, broad host/browser support, final product-quality
calibration/deadzone evidence, or three-separate-USB Flight Pack streaming.

## Run Metadata

- Date/time: 2026-05-28 19:18-19:41 MDT; artifact stamp
  `20260529T011849Z`.
- Commit SHA before this working-tree change:
  `de5b00860839495b300dbb07bf1af12046d2a47f`.
- Selected serial port: `/dev/cu.usbmodem5B5E0200881`.
- Browser: Google Chrome `148.0.7778.179`.
- Browser witness URL: `http://127.0.0.1:8768/`.
- Target artifact directory:
  `target/refined-generic-live-bridge-soak/refined_generic_soak_20260529T011849Z`.

## Hardware Topology

- ESP32-S3 serial/programming USB connected to the Mac.
- HooToo SHUTTLE HT-UC001 powered hub on the ESP32-S3 USB host/OTG path.
- T.16000M stick USB and TWCS throttle USB connected through the HooToo hub.
- TFRP pedals connected to TWCS by RJ12.

The target reported the expected devices:

```text
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b10a|id=3,vid=044f,pid=b687
```

## Commands Run

```bash
git status --short
ls /dev/cu.* /dev/tty.* 2>/dev/null | grep -E 'usb|wch|modem|serial'
python3 tools/serial_command.py --port /dev/cu.usbmodem5B5E0200881 --timeout 3 GET_INFO GET_STATUS GET_USB_STATUS LIST_USB_DEVICES GET_CONFIG_STATUS
./scripts/validate_no_hardware.sh
./scripts/check_target_build.sh
cargo test -p usb2ble-personas -p usb2ble-mapping -p usb2ble-contracts --locked
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile tools/refined_generic_live_bridge_soak.py tools/generic_axis_exposure_witness.py
python3 tools/refined_generic_live_bridge_soak.py --port /dev/cu.usbmodem5B5E0200881
```

The target was not reflashed for this run because the control plane was
responsive, the expected devices were present, BLE was connected, and the
persisted refined six-mapping Generic runtime config was already loaded.

## Loaded Config

The run used `START_CONFIGURED` from the persisted runtime config:

```text
CONFIG_STATUS:valid=true;source=loaded;persona=generic_gamepad;profile=custom_runtime;mappings=6;import_active=false;last_error=none;
CONFIG_ACTION:action=start_configured;state=ok;detail=persona=generic_gamepad;bridge=true;;
```

The exported config contained the refined practical RJ12 Generic mappings:

| Physical control | Source ID | Generic target | Transform |
| --- | --- | --- | --- |
| T.16000M stick X | `044f:b10a:axis_01_30` | `x` | none |
| T.16000M stick Y | `044f:b10a:axis_01_31` | `y` | none |
| TWCS throttle | `044f:b687:axis_01_32` | `z` | inverted |
| TFRP/RJ12 rudder | `044f:b687:axis_01_36` | `rx` | none |
| TFRP/RJ12 left toe brake | `044f:b687:axis_01_34` | `ry` | inverted |
| TFRP/RJ12 right toe brake | `044f:b687:axis_01_33` | `rz` | inverted |

## Soak Result

| Check | Result |
| --- | --- |
| Soak duration | 300 seconds |
| Serial bridge samples | 60 |
| Browser Gamepad API samples | 6,114 |
| Browser connected samples | 6,114 |
| Browser axes length | 10 |
| Bridge enabled at start/end | Pass |
| Browser connected at start/end | Pass |
| Bridge `published` counter | `2120 -> 2331`, delta `211` |
| Bridge `skipped_duplicate` counter | `2036 -> 2215`, delta `179` |
| Bridge `skipped_rate` delta | `0` |
| Bridge `skipped_not_connected` delta | `0` |
| Bridge `skipped_not_ready` delta | `0` |
| Bridge `last_error` values | `none` |
| Summary result | `refined_generic_soak_passed=true` |

The browser Gamepad API samples stayed connected throughout the soak and
retained the expected refined Generic axis visibility:

| Generic target | Browser axis | Min | Max | Delta | Samples |
| --- | --- | --- | --- | --- | --- |
| `z` | A2 | `-1.0` | `1.0` | `2.0` | 6,114 |
| `rx` | A3 | `-1.0` | `1.0` | `2.0` | 6,114 |
| `ry` | A4 | `-1.0` | `1.0` | `2.0` | 6,114 |
| `rz` | A5 | `-1.0` | `1.0` | `2.0` | 6,114 |

Pre-soak and post-soak movement marker windows were captured for TWCS throttle
minimum/maximum, rudder left/right, left toe released/pressed, and right toe
released/pressed. The helper summary reported all focused movement checks as
true:

```json
{"rx": true, "ry": true, "rz": true, "z": true}
```

## Transcript Excerpts

Initial bridge status after `START_CONFIGURED`:

```text
BRIDGE_STATUS:enabled=true;persona=generic_gamepad;rate_hz=50;last_publish_ms=2958225;published=1673;skipped_duplicate=1611;skipped_rate=0;skipped_not_connected=1;skipped_not_ready=0;last_error=none;
```

First soak sample:

```text
STATUS:ble=Connected;profile=none;persona=generic_gamepad;bonds=false;
BRIDGE_STATUS:enabled=true;persona=generic_gamepad;rate_hz=50;last_publish_ms=3575815;published=2120;skipped_duplicate=2036;skipped_rate=0;skipped_not_connected=1;skipped_not_ready=0;last_error=none;
```

Late soak result from `summary.json`:

```json
{
  "published_end": 2331,
  "published_delta": 211,
  "skipped_not_connected_delta": 0,
  "skipped_not_ready_delta": 0,
  "skipped_rate_delta": 0,
  "last_error_values": ["none"]
}
```

## Artifacts

- Summary: `target/refined-generic-live-bridge-soak/refined_generic_soak_20260529T011849Z/summary.json`
- Serial transcript: `target/refined-generic-live-bridge-soak/refined_generic_soak_20260529T011849Z/serial_transcript.txt`
- Bridge samples: `target/refined-generic-live-bridge-soak/refined_generic_soak_20260529T011849Z/bridge_status_samples.jsonl`
- Browser samples: `target/refined-generic-live-bridge-soak/refined_generic_soak_20260529T011849Z/browser_captures.jsonl`
- Movement windows: `target/refined-generic-live-bridge-soak/refined_generic_soak_20260529T011849Z/movement_summaries.json`
- Operator notes: `target/refined-generic-live-bridge-soak/refined_generic_soak_20260529T011849Z/operator_notes.md`

## Limitations

- This proves a 300-second refined Generic live bridge soak in Google Chrome on
  this Mac only.
- It does not prove real game/app compatibility.
- It does not prove Xbox host-visible refined mapping behavior.
- It does not prove durable BLE bond persistence.
- It does not prove broad host/browser support.
- It does not prove final Flight Pack calibration/deadzone feel.
- It uses the practical two-USB RJ12 topology, not three separate USB Flight
  Pack devices streaming simultaneously.
