# Live Bridge Soak Witness - 2026-05-10

## Summary

Real ESP32-S3 hardware soak for explicit Xbox live bridge mode.

This witness extends the live bridge smoke evidence with a 300-second run that
sampled bridge status every 5 seconds. It proves the bridge stayed connected,
continued publishing heartbeat/stable-state reports, reported no errors, and
stopped cleanly.

This is still not a broad game/app compatibility claim. Browser Gamepad API
events are included as host-visible support, but real app/game compatibility
requires separate evidence.

## Environment

- Firmware commit: `38c4fe87b8f690b614b31f7be892f27a16a8b967`
- Firmware version: `0.4.2-ble-hid-demo`
- Board/port: ESP32-S3 on `/dev/cu.usbmodem5B5E0200881`
- Host OS: macOS 12.7.5 (`21H1222`)
- Active persona: `xbox_wireless_controller`
- Soak duration: 300 seconds
- Sample interval: 5 seconds
- Bridge rate: default 50 Hz

## Artifacts

- Helper summary: `target/live-bridge-soak/xbox_soak_20260510T005749Z/summary.json`
- Serial transcript: `target/live-bridge-soak/xbox_soak_20260510T005749Z/serial_transcript.txt`
- Bridge samples JSONL: `target/live-bridge-soak/xbox_soak_20260510T005749Z/bridge_status_samples.jsonl`
- Browser witness JSONL: `target/live-bridge-soak/xbox_soak_20260510T005749Z/gamepad-witness/gamepad_witness_20260510T005749Z.jsonl`

## Key Serial Evidence

Start:

```text
GET_STATUS
STATUS:ble=Idle;profile=none;persona=none;bonds=false;
START_BLE_XBOX_CONTROLLER
BLE_ACTION:action=start_xbox_controller;state=Advertising;
GET_STATUS
STATUS:ble=Connected;profile=none;persona=xbox_wireless_controller;bonds=false;
START_BRIDGE
BRIDGE_STATUS:enabled=true;persona=xbox_wireless_controller;rate_hz=50;last_publish_ms=none;published=0;skipped_duplicate=0;skipped_rate=0;skipped_not_connected=0;skipped_not_ready=0;last_error=none;
```

Late soak sample:

```text
GET_STATUS
STATUS:ble=Connected;profile=none;persona=xbox_wireless_controller;bonds=false;
GET_BRIDGE_STATUS
BRIDGE_STATUS:enabled=true;persona=xbox_wireless_controller;rate_hz=50;last_publish_ms=308890;published=221;skipped_duplicate=220;skipped_rate=0;skipped_not_connected=0;skipped_not_ready=0;last_error=none;
```

Stop:

```text
GET_BRIDGE_STATUS
BRIDGE_STATUS:enabled=true;persona=xbox_wireless_controller;rate_hz=50;last_publish_ms=313001;published=224;skipped_duplicate=223;skipped_rate=0;skipped_not_connected=0;skipped_not_ready=0;last_error=none;
STOP_BRIDGE
BRIDGE_STATUS:enabled=false;persona=xbox_wireless_controller;rate_hz=50;last_publish_ms=314318;published=225;skipped_duplicate=224;skipped_rate=0;skipped_not_connected=0;skipped_not_ready=0;last_error=none;
```

## Result

| Check | Result |
| --- | --- |
| Xbox persona started | Pass |
| BLE connected at start | Pass |
| BLE connected at end | Pass |
| Published count increased | Pass, delta `218` |
| `last_error=none` throughout samples | Pass |
| Persona mismatch absent | Pass |
| `skipped_not_connected` delta | `0` |
| `skipped_not_ready` delta | `0` |
| `skipped_rate` delta | `0` |
| Bridge stopped cleanly | Pass |
| Browser input events | `22` |

## Honest Conclusion

Proven:

- Xbox live bridge can remain connected and publishing for a 300-second ESP32-S3 run.
- Bridge status samples remain clean: no BLE-not-connected skips, no not-ready skips, no rate skips, and no last error.
- The bridge can stop cleanly after the soak.
- Browser Gamepad API captured host-visible events during the run.

Not proven:

- Generic long-duration soak stability.
- Multi-hour stability.
- Real game/app compatibility.
- Final Flight Pack calibration or pedal axis labels.
