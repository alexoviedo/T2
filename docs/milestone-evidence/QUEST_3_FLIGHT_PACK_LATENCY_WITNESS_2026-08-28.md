# Quest 3 Flight Pack Latency Witness - 2026-08-28

## Summary

This witness closes the severe latency defect for one tested Quest 3 Flight Pack
configuration. It also records the boundary of that result: external flight-control
latency and accuracy passed, while Quest controller/optical-hand handoff remains a
separate QuestFlight issue.

The accepted firmware uses optimized release builds and a non-drifting,
microsecond-resolution 50 Hz bridge deadline. Production build, target preflight,
flash, package, and CI artifact paths now select release firmware, and flash/package
paths fail closed if asked to use a debug profile.

## Tested configuration

- Host/target: Alex's Windows PC and one ESP32-S3
- Receiver: one awake Meta Quest 3 paired as `USB2BLE Gamepad`
- USB topology: HooToo powered hub, T.16000M, and TWCS/RJ12 pedals/throttle
- Persona: Generic gamepad
- Configured bridge rate: 50 Hz
- QuestFlight mode accepted: Free Flight
- Source base: `5a70ca0ab12b1ca9c14595a49a3feac785203fc6`
- Feature branch during the witness: `feature/questflight-controller-latency-v1`

## Deterministic transport result

The final `flight_pack_core` run generated 500 deliberately changing frames on
the ESP32 internal clock:

- Expected/generated frames: 500/500
- Missed sequence intervals: 0
- Bridge publish attempts: 504
- BLE transport successes: 504
- Bridge rate skips: 0
- Android reports received: 500 (100.0% of expected deliberate reports)
- Alternating report values observed: yes
- Android inter-arrival gap median: 29.668 ms
- Android inter-arrival gap p95: 30.231 ms
- Android maximum gap: 60.167 ms
- Android unexplained gaps above 100 ms: 0
- Maximum recorded bridge poll: 8.084 ms
- Bridge polls above 50 ms: 0

The transport result passed the scoped deterministic gate. It is evidence for this
hardware/topology combination, not a broad Android, BLE-controller, or Quest
performance claim.

## Build and artifact provenance

All 45 firmware tests passed before the final test was expanded into the exact
500-frame regression. The focused final regression passed 1/1. The release build,
flash, and merged-image package completed successfully.

- Release ELF SHA-256:
  `E6D78A016DCF4CBC8EFECE5BA2360F18B81EC1FB4A38FC601936F4D765BAF897`
- Packaged image byte length: 1,588,576
- Packaged image SHA-256:
  `B3BA25FDFEF350C5789824D0F84213E86E6B351414765D46FD226FA250FC32AF`

Primary external evidence root:

```text
C:\Users\ovied\Dev\T2\T2-QuestFlight-product-extraction-artifacts\t2_release_pipeline_gate2a_20260828T181329Z\scheduler_correction
```

Key artifacts under that root are `result.txt`, `android_getevent.log`,
`android_capture_summary.json`, `serial_commands.log`, `release_build.log`,
`release_flash.log`, `package.log`, and `hub_ready_verification.log`.

## Physical QuestFlight acceptance

After the powered hub was restored and the target reported the hub, T.16000M,
and TWCS/RJ12 devices, Alex tested the installed QuestFlight build in Free Flight.
The operator result was:

- Latency: pass
- Accuracy: pass
- Throttle hold: pass
- Pedals/brakes: pass
- Hand handoff: partial

The handoff limitation was that optical hand tracking appeared unavailable; a hand
was seen only in association with a held Quest controller. That issue is not
evidence of a T2 transport failure and was not corrected in this milestone.

## Limits

- This is one Quest 3, one ESP32-S3, and one Flight Pack topology.
- Demo mode was not reaccepted in this final physical run.
- Optical-hand and Quest-controller coexistence remains unresolved in QuestFlight.
- No broad device compatibility, certified fidelity, FAA credit, or generalized
  Quest performance claim is made.
