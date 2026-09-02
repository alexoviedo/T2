# Quest 3 Flight Pack Hung-Transfer Recovery — 2026-09-02

## Outcome

The accepted Quest Flight Pack path now recovers both known USB interrupt
transfer stall states:

- a transfer that is no longer in flight; and
- a transfer that remains marked in flight but never completes.

After the second correction was built and flashed, Android received changing
HOTAS, throttle, rudder, and both toe-brake axes. The operator then passed the
QuestFlight Free Flight check, including a 60-second idle/wake check, with
normal latency and accuracy.

This is a single-topology hardware witness. It is not a broad controller,
Android, Bluetooth, or simulator-compatibility claim.

## Proven failure boundary

Before the correction, T2 still reported all three USB devices, both HID
interfaces, BLE connected, the saved Generic Gamepad configuration loaded, and
the 50 Hz bridge active with no current error. During 75 seconds of deliberate
physical control movement:

- the T.16000M and TWCS raw USB reports remained byte-identical;
- the normalized flight axes remained byte-identical;
- the encoded Generic Gamepad report remained byte-identical;
- Android received no changing `USB2BLE Gamepad` event from that movement; and
- the bridge publish counter continued increasing because heartbeat
  publication resent the stale report.

This directly located the first failing boundary in T2 physical USB ingestion,
not QuestFlight, Android input mapping, or BLE delivery.

Source inspection then found the uncovered state. The earlier recovery retried
only when `in_flight` was false. A submitted interrupt transfer with
`in_flight == true` and `done == false` could remain in that state forever,
leaving enumeration and bridge health superficially normal while physical
inputs were stale.

Primary failure evidence:

```text
C:\Users\ovied\Dev\T2\T2-QuestFlight-product-extraction-artifacts\controller_nonresponse_attribution_20260902T194908Z
```

## Correction

The platform USB host now applies a 500 ms progress watchdog only to the two
witnessed continuously-reporting Thrustmaster devices (`044f:b10a` and
`044f:b687`). On a stalled submitted transfer it uses ESP-IDF's endpoint
halt/flush/clear recovery sequence, consumes the intentional cancellation
callback, and resubmits the existing transfer. Recovery attempts are bounded to
one per 250 ms and emit explicit stall/recovery diagnostics.

The change does not alter the Flight Pack mapping, calibration, BLE persona,
bridge rate, saved configuration, or QuestFlight. Quiet event-driven HID
devices are excluded from this watchdog.

The annotated tag `questflight-controller-bridge-hung-transfer-recovery-v1`
identifies the accepted source milestone.

## Validation

- Focused platform tests: 14 passed.
- Full Rust workspace tests: 134 passed.
- Workspace Clippy with warnings denied: passed.
- Optimized ESP32-S3 target build with pinned ESP-IDF 5.5.3: passed.
- Release ELF: 2,168,372 bytes.
- Release ELF SHA-256:
  `9312B56CFAEC802422F1E7EC4BD3A81705ED9246095D41D2E2CC3D95DBC487C3`.
- Flash and saved-config autostart: passed.
- Post-flash topology: HooToo hub, T.16000M, and TWCS/RJ12 present; two HID
  interfaces; BLE connected; Generic bridge enabled at 50 Hz; no bridge error.
- Android physical capture: 1,720 event lines and 680 `SYN_REPORT` frames.
- Captured mapped-axis ranges:
  - HOTAS X: -32768 to 32767;
  - HOTAS Y: -32768 to 32767;
  - throttle Z: -32767 to 32767;
  - rudder Rx: -32768 to 32767;
  - left brake Ry: -32767 to 32767;
  - right brake Rz: -32767 to 32767.
- Operator QuestFlight Free Flight acceptance:
  - HOTAS: pass;
  - throttle and hold: pass;
  - pedals and toe brakes: pass;
  - latency and accuracy: pass;
  - response after 60 seconds idle: pass.

Primary correction/build/flash/capture evidence:

```text
C:\Users\ovied\Dev\T2\T2-QuestFlight-product-extraction-artifacts\usb_hung_transfer_recovery_20260902T200457Z
```

## Limits

- The physical witness covers one ESP32-S3, one HooToo powered hub, one
  T.16000M, and one TWCS/TFRP RJ12 topology.
- The operator passed a 60-second idle/wake check. An overnight or multi-hour
  recurrence soak has not yet been run.
- The test does not establish broad USB hub/controller compatibility, certified
  fidelity, FAA credit, or generalized Quest performance.
