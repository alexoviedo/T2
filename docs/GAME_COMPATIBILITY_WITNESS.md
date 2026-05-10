# Game/App Compatibility Witness

Status: **manual evidence workflow; compatibility is not claimed until a real
app/game run is captured and checked in.**

Browser Gamepad API evidence is useful because it proves host-visible HID
reports, but it is not a substitute for a real app/game compatibility witness.
Use this runbook when testing whether USB2BLE behaves like a usable controller
inside an actual application.

## Evidence Standard

A real compatibility witness must capture:

- firmware commit SHA
- firmware version
- host OS and version
- active BLE persona: `generic_gamepad` or `xbox_wireless_controller`
- Bluetooth identity shown by the OS
- browser Gamepad API identity, if used as supporting evidence
- app/game name and version, if available
- bridge status before and after the app/game test
- `published` count delta from `GET_BRIDGE_STATUS`
- which axes/buttons the app/game recognized
- whether control orientation was correct
- screenshots or operator notes describing the app-visible result
- honest pass/fail conclusion

Do not mark broad game compatibility complete from one app. Treat each app/game
as one compatibility data point.

## Recommended Folder Layout

Create a timestamped folder under `target/game-compatibility/`:

```text
target/game-compatibility/<app>_<persona>_<timestamp>/
  serial_transcript.txt
  bridge_status_samples.jsonl
  browser_witness.jsonl        # optional
  operator_notes.md
  screenshots/                 # optional manual screenshots
  summary.json
```

Only add a checked-in milestone evidence document after reviewing the generated
folder and confirming it contains real app/game evidence.

## Before The App/Game

Build, flash, and reset:

```sh
./scripts/build.sh
./scripts/flash.sh --port /dev/cu.usbmodem5B5E0200881
espflash reset --chip esp32s3 --port /dev/cu.usbmodem5B5E0200881 --non-interactive
```

Start the target persona. For Xbox:

```sh
python3 tools/serial_command.py \
  --port /dev/cu.usbmodem5B5E0200881 \
  GET_STATUS \
  START_BLE_XBOX_CONTROLLER \
  GET_STATUS
```

For Generic:

```sh
python3 tools/serial_command.py \
  --port /dev/cu.usbmodem5B5E0200881 \
  GET_STATUS \
  START_BLE_GENERIC_GAMEPAD \
  GET_STATUS
```

Pair/connect in macOS Bluetooth if needed. Reset before switching personas; the
firmware intentionally supports one active BLE HID report map per boot/session.

## Start Live Bridge

```sh
python3 tools/serial_command.py \
  --port /dev/cu.usbmodem5B5E0200881 \
  GET_BRIDGE_STATUS \
  START_BRIDGE \
  GET_BRIDGE_STATUS
```

Expected shape:

```text
BRIDGE_STATUS:enabled=true;persona=<persona>;rate_hz=50;last_publish_ms=<ms>;published=<n>;skipped_duplicate=<n>;skipped_rate=<n>;skipped_not_connected=<n>;skipped_not_ready=<n>;last_error=none;
```

## Optional Browser Support

Browser evidence is optional support. It can be captured with:

```sh
python3 tools/gamepad_witness/server.py \
  --port 8765 \
  --out-dir target/game-compatibility/browser-witness
```

Open:

```sh
open http://127.0.0.1:8765/
```

Click **Arm** if the page offers it. Record the browser ID and VID/PID, but do
not treat this as app/game compatibility by itself.

## App/Game Test

Open the app/game while live bridge mode is enabled.

Record in `operator_notes.md`:

```markdown
# Operator Notes

- Date:
- Firmware commit:
- Firmware version:
- Host OS:
- App/game name:
- App/game version:
- Active persona:
- Bluetooth identity shown by OS:
- Browser Gamepad API identity, if checked:
- Controls tested:
- Axes recognized:
- Buttons recognized:
- Orientation correct:
- Any deadzones/calibration needed:
- Did the app/game accept the controller:
- Pass/fail:
- Notes:
```

Recommended first checks:

- Does the app/game show a controller connected?
- Does the stick move the expected axis?
- Does one button press register?
- Does the app/game keep receiving input for at least 60 seconds?
- Does `GET_BRIDGE_STATUS` show `published` increasing and `last_error=none`?

## Stop And Capture Final Status

```sh
python3 tools/serial_command.py \
  --port /dev/cu.usbmodem5B5E0200881 \
  GET_BRIDGE_STATUS \
  STOP_BRIDGE \
  GET_BRIDGE_STATUS
```

The final conclusion should distinguish:

- serial bridge stability
- browser Gamepad API visibility
- real app/game recognition
- mapping/calibration quality

## Checked-In Evidence

When a run succeeds, add a concise checked-in evidence document:

```text
docs/milestone-evidence/GAME_COMPATIBILITY_WITNESS_<YYYY-MM-DD>_<APP>.md
```

The document should link to the target evidence folder and quote the relevant
serial/app evidence. If the app/game does not recognize controls, check in a
failure report only if it teaches us something concrete.
