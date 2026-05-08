# CI Flashable Firmware Artifact Witness - 2026-04-30

## Scope

This is local validation for the CI path that builds and packages a flashable
ESP32-S3 firmware artifact.

It proves the repo can produce a merged ESP32-S3 binary image with `espflash
save-image`. It does not prove a completed GitHub Actions run until the workflow
is pushed and executed on GitHub.

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

This is workflow wiring evidence only. A real GitHub-hosted release asset still
requires a pushed workflow run.

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
- The same packaging script works locally.
- Local Rust dependencies now resolve under the default stable toolchain.
- The ESP32-S3 target build still passes after the CI packaging changes.

## Not Proven

- A GitHub-hosted artifact from a completed run of the modified workflow. That
  requires pushing these changes and letting GitHub Actions run.
- A GitHub-hosted `latest` release from the modified workflow. That also
  requires a pushed `main` workflow run.
