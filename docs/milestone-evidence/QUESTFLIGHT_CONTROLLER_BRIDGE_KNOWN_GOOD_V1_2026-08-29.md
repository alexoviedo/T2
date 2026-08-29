# QuestFlight Controller Bridge Known-Good V1 - 2026-08-29

## Summary

This milestone records the accepted T2 firmware, configuration, and QuestFlight
pair for one physically tested Flight Pack topology. After restoring this pair,
the operator reported that HOTAS, throttle, pedals, toe brakes, latency, accuracy,
and throttle position-hold all worked as remembered.

This is the recovery baseline for subsequent QuestFlight input-selection work.
That work is isolated to QuestFlight. T2 runtime, mapping, and transport changes
are outside its scope.

## Accepted source pair

- T2 runtime source: `65ae4c77db4e14777c481b991cd6ff763d568365`
- QuestFlight source: `474f3fd01369839d0fb7e973ee334ca57ed15fcb`
- QuestFlight APK SHA-256:
  `57481476695D91FA3C69249ADBAC657D3647DCFD4183457C0250A753E1626F38`
- T2 annotated milestone tag: `questflight-controller-bridge-known-good-v1`

## Tested topology

- Target: ESP32-S3 on Windows `COM3`
- Receiver: one awake Meta Quest 3
- BLE persona: Generic gamepad, exposed as `USB2BLE Gamepad`
- Bridge rate: 50 Hz
- USB hub: VID/PID `2109:2813`
- Stick: Thrustmaster T.16000M, VID/PID `044f:b10a`
- Throttle/pedals: Thrustmaster TWCS/RJ12, VID/PID `044f:b687`
- QuestFlight mode physically accepted: Free Flight

## Accepted semantic mapping

The saved runtime configuration contains 23 mappings. Its six axes are:

| Physical source | Source control | Generic target | QuestFlight domain |
| --- | --- | --- | --- |
| T.16000M | `axis_01_30` | `x` | Yoke aileron |
| T.16000M | `axis_01_31` | `y` | Yoke elevator |
| TWCS/RJ12 | `axis_01_32` | `z`, inverted | Throttle |
| TWCS/RJ12 | `axis_01_36` | `rx` | Rudder pedals |
| TWCS/RJ12 | `axis_01_34` | `ry`, inverted | Left toe brake |
| TWCS/RJ12 | `axis_01_33` | `rz`, inverted | Right toe brake |

The remaining 17 mappings expose the T.16000M hat and buttons 1 through 16.
QuestFlight receives one composite BLE gamepad. This mapping is the authoritative
record of which physical USB controls feed its semantic axes.

## Recovery artifacts

External recovery root:

```text
C:\Users\ovied\Dev\T2\T2-QuestFlight-product-extraction-artifacts\known_good_restore_20260829T195717Z\t2_known_good_recovery
```

- Optimized release ELF: `usb2ble-fw`
- ELF byte length: 2,164,268
- ELF SHA-256:
  `87F1AEC5B02264DD68D57A6D18D1C92A779B42338B4E2DBFE8A165CBBDF23661`
- Exported configuration: `questflight_flight_pack_config.json`
- Configuration byte length: 4,648
- Configuration SHA-256:
  `286570A2DA0E64F7605BF3D9B30645A42A97CFB7673F5FED8B7AA22BA5DB5B9C`
- Recovery manifest: `recovery_manifest.json`

Flash the preserved ELF with:

```text
espflash flash --port COM3 usb2ble-fw
```

After BLE reconnection, invoke `START_CONFIGURED` if `GET_BRIDGE_STATUS` does not
already report `enabled=true`.

## Physical acceptance

After the clean T2 source and preserved QuestFlight APK were restored, the
operator reported a large improvement and confirmed that everything worked as
remembered. The accepted observations were:

- HOTAS yoke control: pass
- Throttle response and position hold: pass
- Rudder pedals and toe brakes: pass
- Latency: pass
- Accuracy: pass

No selectable-input policy was present in this build. The result therefore
defines the all-inputs-enabled behavior that later QuestFlight candidates must
match exactly.

## Limits

- This is one Quest 3, one ESP32-S3, and one Flight Pack topology.
- The acceptance is operator-observed, not a calibrated latency measurement.
- Demo mode was not reaccepted in this recovery run.
- The milestone does not prove broad controller or Android compatibility.
- It does not establish certified fidelity, FAA credit, or generalized Quest
  performance.
