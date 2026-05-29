# Refined Generic Axis Exposure Witness - 2026-05-28

Status: real ESP32-S3 + macOS Chrome browser Gamepad API evidence captured for
the refined practical RJ12 Flight Pack Generic live bridge. This proves the
previous missing host-visible `rx`/`ry`/`rz` axis exposure was a witness
sampling artifact, not a target-side mapping/report failure.

This is host-visible browser Gamepad API evidence only. It is not real
game/app compatibility, Xbox host-visible evidence, BLE bond persistence, broad
host/browser support, or final product-quality calibration/deadzone evidence.

## Run Metadata

- Date/time: 2026-05-28 19:00-19:06 MDT; artifact stamp
  `20260529T010039Z`.
- Commit SHA before this working-tree change:
  `5d5dc893e1f7e93695854d0e31924a01ebdb0e84`.
- Selected serial port: `/dev/cu.usbmodem5B5E0200881`.
- Browser: Google Chrome `148.0.7778.179`.
- Browser witness URL: `http://127.0.0.1:8766/`.
- Target artifact directory:
  `target/generic-axis-exposure-witness/generic_axis_exposure_20260529T010039Z`.
- Prior partial artifact reviewed:
  `target/refined-generic-live-bridge-witness/refined_generic_live_bridge_20260529T004057Z`.
- Diagnostic review artifact:
  `target/refined-generic-live-bridge-diagnosis/diagnosis_20260529T005743Z`.

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
python3 tools/serial_command.py --port /dev/cu.usbmodem5B5E0200881 --timeout 3 GET_INFO GET_STATUS GET_USB_STATUS LIST_USB_DEVICES
python3 tools/generic_axis_exposure_witness.py --port /dev/cu.usbmodem5B5E0200881
python3 -m py_compile tools/generic_axis_exposure_witness.py
```

The target was already running the persisted refined Generic Flight Pack
configuration. `START_CONFIGURED` returned `state=ok` and
`GET_BRIDGE_STATUS` reported `enabled=true;persona=generic_gamepad`.

## Diagnosis

The earlier partial run used change-triggered browser captures and recorded no
fresh captures during the `rx`/`ry`/`rz` steps, even though serial mapping,
encoded reports, and bridge publish counters changed. The diagnosis artifact
decoded the prior serial reports as six-axis Generic reports with changing
`z`, `rx`, `ry`, and `rz` fields.

The new witness served a continuous Gamepad API sampler. It captured 2,415
browser samples with a 10-axis Gamepad API array. Continuous sampling showed
the expected host-visible axis changes:

| Physical movement | Generic target | Decoded Generic report axis | Browser axis | Browser delta | Bridge published |
| --- | --- | --- | --- | --- | --- |
| TWCS throttle maximum | `z` | `z=32767` | A2 | `-1.0 -> 1.0` | `933 -> 941` |
| TFRP/RJ12 rudder left | `rx` | `rx=-32768` | A3 | `-0.024 -> -1.0` | `986 -> 992` |
| TFRP/RJ12 rudder right | `rx` | `rx=32767` | A3 | `-1.0 -> 1.0` | `1011 -> 1017` |
| Left toe brake pressed | `ry` | `ry=32767` | A4 | `-1.0 -> 1.0` | `1054 -> 1061` |
| Right toe brake pressed | `rz` | `rz=32767` | A5 | `-1.0 -> 1.0` | `1109 -> 1116` |

The inferred browser axis map for the refined Generic practical RJ12 profile is
therefore:

- Generic `z` -> browser Gamepad API A2.
- Generic `rx` -> browser Gamepad API A3.
- Generic `ry` -> browser Gamepad API A4.
- Generic `rz` -> browser Gamepad API A5.

## Transcript Excerpts

Runtime config and bridge start:

```text
CONFIG_STATUS:valid=true;source=loaded;persona=generic_gamepad;profile=custom_runtime;mappings=6;import_active=false;last_error=none;
CONFIG_ACTION:action=start_configured;state=ok;detail=persona=generic_gamepad;bridge=true;;
BRIDGE_STATUS:enabled=true;persona=generic_gamepad;rate_hz=50;...
```

Rudder left report:

```text
GENERIC_GAMEPAD_MAPPING:...axis_01_36,target=rx,value=axis:-32768,reason=profile_rule...
ENCODED_REPORT:persona=generic_gamepad;report_id=1;bytes=0000084dfcadfaff7f008001800180;
```

Left toe pressed report:

```text
GENERIC_GAMEPAD_MAPPING:...axis_01_34,target=ry,value=axis:-32768,reason=profile_rule_inverted...
ENCODED_REPORT:persona=generic_gamepad;report_id=1;bytes=00000845fcadfaff7f1f00ff7f0180;
```

Right toe pressed report:

```text
GENERIC_GAMEPAD_MAPPING:...axis_01_33,target=rz,value=axis:-32768,reason=profile_rule_inverted...
ENCODED_REPORT:persona=generic_gamepad;report_id=1;bytes=00000845fcadfaff7f1f000180ff7f;
```

## Limitations

- This witness proves browser Gamepad API host visibility in Google Chrome on
  this Mac only.
- It does not prove real game/app compatibility or broad host/browser support.
- It does not prove Xbox host-visible refined mapping behavior.
- It does not prove BLE bond persistence.
- It does not prove final Flight Pack calibration/deadzone feel.
- It uses the practical two-USB RJ12 topology, not three separate USB Flight
  Pack devices streaming simultaneously.
