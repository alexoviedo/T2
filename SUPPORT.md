# Support

USB2BLE is an experimental alpha project. Support is best-effort.

## Before Asking For Help

Run:

```bash
./scripts/validate_no_hardware.sh
python3 tools/check_evidence_docs.py --verbose
```

For hardware issues, also collect:

```bash
python3 tools/serial_command.py --port <PORT> GET_INFO GET_STATUS GET_USB_STATUS LIST_USB_DEVICES GET_CONFIG_STATUS GET_BRIDGE_STATUS
```

## Include In Bug Reports

- Host OS and version.
- ESP32-S3 board model if known.
- Firmware commit SHA or release artifact.
- Hardware topology and USB VID/PID list.
- Commands run and exact output.
- Target artifact directory, if a witness helper generated one.
- What you expected and what happened.

## Unsupported Claims

Do not assume support for broad game compatibility, iPhone compatibility, Xbox
refined Flight Pack host visibility, BLE bond persistence, final calibration
feel, or arbitrary USB HID controllers unless evidence exists in the repo.
