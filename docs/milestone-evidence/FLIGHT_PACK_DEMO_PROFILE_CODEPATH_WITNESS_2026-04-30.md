# Flight Pack Demo Profile Codepath Witness - 2026-04-30

Status: **host-tested and target-build verified. Target hardware profile
selection is now captured in
`FLIGHT_PACK_DEMO_PROFILE_TARGET_WITNESS_2026-04-30.md`.**

This witness records the first explicit demo profile for the Thrustmaster
T.16000M + TWCS/RJ12 topology. It does not replace the generic descriptor-driven
fallback. The generic path remains `generic_auto`; the curated demo path is
selected only when both known Thrustmaster devices are present.

## Profile

Profile ID:

```text
flight_pack_demo
```

Selection condition:

```text
044f:b10a T.16000M stick present
044f:b687 TWCS throttle present
```

Curated Generic Gamepad axis rules:

```text
044f:b10a axis_01_30 -> x
044f:b10a axis_01_31 -> y
044f:b687 axis_01_32 -> z
044f:b687 axis_01_36 -> rx
044f:b10a axis_01_36 -> ry
044f:b10a axis_01_35 -> rz
```

Buttons and the first hat still use the existing generic behavior. Sources not
included in the demo profile remain visible in mapping diagnostics as
`profile_unmapped`.

## Why This Matters

Previous target evidence proved TWCS and TFRP/RJ12 movement, but those controls
were source-only under `generic_auto` because Generic Gamepad axis slots were
already full. This profile gives the ASAP demo an intentional, reproducible
axis layout without hard-coding Thrustmaster behavior into HID parsing,
normalization, BLE transport, or the Generic Gamepad persona encoder.

## Verification

Host tests:

```bash
cargo test --workspace --locked
```

Relevant passing tests:

```text
selects_flight_pack_demo_profile_for_known_thrustmaster_pair ... ok
flight_pack_demo_profile_maps_curated_axes_before_auto_fallback ... ok
```

Target build:

```bash
RUSTUP_TOOLCHAIN=esp ./scripts/check_target_build.sh
```

Result:

```text
Target build preflight passed for xtensa-esp32s3-espidf.
```

Firmware with this codepath was flashed to:

```text
/dev/cu.usbmodem5B5E0200881
```

## Hardware Verification

The first post-flash attempt saw the HooToo hub but no downstream HID devices:

```text
>> GET_USB_STATUS
USB_STATUS:devices=1;interfaces=0;
>> LIST_USB_DEVICES
USB_DEVICES:id=1,vid=2109,pid=2813
```

After reconnecting TWCS and T.16000M through the hub, target hardware profile
selection was captured separately. See:

```text
docs/milestone-evidence/FLIGHT_PACK_DEMO_PROFILE_TARGET_WITNESS_2026-04-30.md
```
