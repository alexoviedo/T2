# CI Flashable Firmware Artifact Witness - 2026-04-30

## Scope

This witness started as local validation for the CI path that builds and
packages a flashable ESP32-S3 firmware artifact. It now also includes
GitHub-hosted Actions, artifact, and release evidence from the pushed workflow.

It proves the repo can produce a merged ESP32-S3 binary image with
`espflash save-image`, upload that package as a GitHub Actions artifact, and
publish the same files to the `latest` GitHub Release.

## CI Change

The `esp32s3_target_preflight` job now:

- installs `espflash` version `4.4.0`
- runs `./scripts/check_target_build.sh`
- runs `./scripts/package_firmware.sh`
- uploads `usb2ble-fw-esp32s3-flashable` with:
  - `target/firmware/usb2ble-fw-esp32s3-merged.bin`
  - `target/firmware/usb2ble-fw-esp32s3-manifest.txt`
  - `target/xtensa-esp32s3-espidf/debug/usb2ble-fw`

## Release Hardening Addendum - 2026-05-08

The release job is wired to create/update the `latest` GitHub Release on pushes
to `main`, using the same `usb2ble-fw-esp32s3-flashable` artifact.

The release job now:

- waits for both `host_checks` and `esp32s3_target_preflight`
- declares explicit `contents: write` permission for GitHub Release creation
- names the release `Latest USB2BLE firmware`
- overwrites release assets when the `latest` release is refreshed
- marks the release as the latest repository release

## GitHub-Hosted Verification - 2026-05-08

Pushed commit:

```text
a7588f1660f28c2bf9f496034c9179b381585280
```

GitHub Actions run:

```text
CI
run_id=25577980057
url=https://github.com/alexoviedo/T2/actions/runs/25577980057
status=completed
conclusion=success
created_at=2026-05-08T20:30:02Z
updated_at=2026-05-08T20:34:57Z
```

Jobs:

```text
Host checks: completed, success
ESP32-S3 target preflight: completed, success
Create Release: completed, success
```

Hosted Actions artifact:

```text
id=6888279194
name=usb2ble-fw-esp32s3-flashable
workflow_run=25577980057
head_sha=a7588f1660f28c2bf9f496034c9179b381585280
size_in_bytes=8336747
expired=false
created_at=2026-05-08T20:34:43Z
```

Hosted GitHub Release:

```text
tag=latest
name=Latest USB2BLE firmware
url=https://github.com/alexoviedo/T2/releases/tag/latest
published_at=2026-05-08T20:34:55Z
draft=false
prerelease=false
```

Release assets:

```text
usb2ble-fw                              22701344 bytes
usb2ble-fw-esp32s3-manifest.txt             683 bytes
usb2ble-fw-esp32s3-merged.bin           2113728 bytes
```

The hosted release manifest and binary were downloaded and checked locally:

```text
shasum -a 256 /tmp/t2-release-check/usb2ble-fw-esp32s3-merged.bin
1b6b3adfff0d39352330e0ebf6fe7168b7ef2ad1c87c63376039bb0a9f1b9a50
```

Downloaded release manifest excerpt:

```text
git_rev=a7588f1
git_dirty=false
image_sha256=1b6b3adfff0d39352330e0ebf6fe7168b7ef2ad1c87c63376039bb0a9f1b9a50
flash_command=espflash write-bin --chip esp32s3 --port <PORT> 0x0 target/firmware/usb2ble-fw-esp32s3-merged.bin
```

## Hosted Release Flash Smoke - 2026-05-08

The downloaded `latest` release image was flashed to the local ESP32-S3:

```bash
espflash write-bin \
  --chip esp32s3 \
  --port /dev/cu.usbmodem5B5E0200881 \
  0x0 \
  /tmp/t2-release-check/usb2ble-fw-esp32s3-merged.bin
```

Flasher output excerpt:

```text
Chip type:         esp32s3 (revision v0.2)
Crystal frequency: 40 MHz
Flash size:        16MB
Features:          WiFi, BLE, Embedded Flash
MAC address:       90:70:69:07:0d:7c
```

The command exited successfully. After reboot, the target answered the serial
control plane:

```text
>> GET_STATUS
STATUS:ble=Idle;profile=none;bonds=false;
>> GET_USB_STATUS
USB_STATUS:devices=3;interfaces=2;
>> LIST_USB_DEVICES
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b687|id=3,vid=044f,pid=b10a
>> GET_INFO
INFO:version=1;name=usb2ble;persona=none;
>> GET_GENERIC_GAMEPAD_REPORT
ENCODED_REPORT:persona=generic_gamepad;report_id=1;bytes=000008a5fca5f900801f00008078f8;
```

## Local Verification

Before changing CI/build wiring, this required check was run:

```bash
RUSTUP_TOOLCHAIN=esp ./scripts/verify_cloud_equivalent.sh
```

Result:

```text
Target build preflight passed for xtensa-esp32s3-espidf.
```

The local default Rust toolchain was moved from explicit `1.85.0` to `stable`,
currently:

```text
rustc 1.95.0 (59807616e 2026-04-14)
cargo 1.95.0 (f2d3ce0bd 2026-03-21)
```

Local host checks now pass with plain `cargo`:

```bash
cargo fmt --all -- --check
cargo clippy --workspace --all-targets --locked -- -D warnings
cargo test --workspace --locked
```

Firmware package command:

```bash
./scripts/package_firmware.sh
```

Package result:

```text
target/firmware/usb2ble-fw-esp32s3-merged.bin: 2.0M
target/firmware/usb2ble-fw-esp32s3-manifest.txt: 644B
image_sha256=76476d19ce4680e48d9d20b84d80b9291b6066f87bc8b75a9fc52ae5ea062d2b
```

After the 2026-05-08 demo/runbook and release hardening changes, the same
verification and package flow passed again:

```bash
./scripts/verify_cloud_equivalent.sh
./scripts/package_firmware.sh
```

Package result:

```text
target/firmware/usb2ble-fw-esp32s3-merged.bin: 2.0M
target/firmware/usb2ble-fw-esp32s3-manifest.txt: 644B
image_sha256=d50c469aa822405fc93fe4e779d7121f8ca72da5c75f2d897be9fb0177501468
```

Flash command for the merged artifact:

```bash
espflash write-bin --chip esp32s3 --port <PORT> 0x0 target/firmware/usb2ble-fw-esp32s3-merged.bin
```

## Proven

- CI is wired to produce and upload a flashable merged firmware image artifact.
- CI is wired to create/update a `latest` GitHub Release after host checks and
  ESP32-S3 target packaging both pass.
- GitHub Actions produced a hosted `usb2ble-fw-esp32s3-flashable` artifact from
  commit `a7588f1`.
- GitHub Actions created/refreshed a hosted `latest` release with the merged
  ESP32-S3 binary, manifest, and ELF.
- The downloaded release manifest SHA matches the downloaded release binary.
- The downloaded hosted release binary flashed successfully to the ESP32-S3 and
  booted far enough to answer serial control-plane commands.
- The same packaging script works locally.
- Local Rust dependencies now resolve under the default stable toolchain.
- The ESP32-S3 target build still passes after the CI packaging changes.

## Not Proven

- A full browser Gamepad API end-to-end demo was not repeated after flashing
  the hosted release asset. The release image did answer USB and Generic
  Gamepad report commands after flash.
