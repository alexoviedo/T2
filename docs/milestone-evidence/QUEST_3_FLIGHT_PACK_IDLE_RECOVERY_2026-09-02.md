# Quest 3 Flight Pack Idle Recovery — 2026-09-02

## Summary

The physical Flight Pack input freeze after an extended idle period was
isolated to the ESP32-S3 USB-host ingestion boundary and corrected. The
operator then passed HOTAS, throttle/hold, pedals, and toe brakes in QuestFlight
Free Flight.

This is a single-topology hardware witness. It does not establish broad USB,
Bluetooth, Android, or simulator compatibility.

## Failure evidence

The Quest was awake with QuestFlight resident. T2 still reported:

- three enumerated USB devices and two HID interfaces;
- the saved Generic Gamepad persona and 50 Hz bridge enabled;
- BLE connected with successful publication and no current transport error.

An internal `flight_pack_core` sequence delivered 491 of 494 generated reports
to Android after wake (99.39 percent), and held left/right virtual frames visibly
moved the QuestFlight yoke. This ruled out T2 report encoding, BLE-to-Quest
delivery, Android gamepad exposure, and QuestFlight consumption.

The operator then moved every physical control. T2's input catalog remained
unchanged from its pre-movement values even though the devices remained listed.
The first failing boundary was therefore physical USB report ingestion.

Source inspection identified the matching permanent-stall path: after a
completed or errored interrupt transfer, a transient resubmission/recovery
failure left `in_flight` false. The poll loop skipped every interface in that
state forever, while enumeration and BLE status remained superficially healthy.

## Correction

Commit `f0756219ff4fc32a0101b56f476b91b4c65c7070` adds a bounded 250 ms retry for
stranded interrupt transfers. A successful recovery restores the existing
transfer and emits one `USB_REPORT_RECOVERED` diagnostic. It does not alter the
Flight Pack mapping, BLE persona, bridge rate, or QuestFlight.

## Validation

- Focused platform tests: 12 passed.
- Full Rust workspace tests: 132 passed.
- Workspace Clippy with warnings denied: passed.
- Optimized ESP32-S3 target build with the pinned ESP-IDF 5.5.3 stage: passed.
- Built release ELF: 2,164,272 bytes.
- Built release ELF SHA-256:
  `AB024F0A7B30F37BA22C12F8F37B8D0FA3C2D5912BB6967888F4A8BF25DB23FF`.
- Flash and saved-config auto-start: passed.
- BLE reconnect and Android `USB2BLE Gamepad` exposure: passed.
- Operator headset acceptance: HOTAS pass; throttle/hold pass; pedals/brakes
  pass.

Primary external evidence:

```text
C:\Users\ovied\Dev\T2\T2-QuestFlight-product-extraction-artifacts\idle_wake_diagnostic_20260902T164308Z
```

## Limits

- One ESP32-S3, one HooToo powered hub, one T.16000M, and one TWCS/TFRP RJ12
  topology were tested.
- The immediate recovered controls and post-fix physical path passed; a future
  natural long-idle cycle remains the recurrence check.
- This is not evidence of broad controller compatibility, certified fidelity,
  FAA credit, or generalized Quest performance.
