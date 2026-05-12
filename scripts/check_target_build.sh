#!/bin/bash
set -euxo pipefail

echo "Preflight: building usb2ble-fw for ESP32-S3 target..."
echo "Default ESP-IDF pin: v5.5.3 (crates/usb2ble-fw/Cargo.toml)"
if [[ -n "${IDF_PATH:-}" || -n "${ESP_IDF_VERSION:-}" ]]; then
    echo "Warning: IDF_PATH or ESP_IDF_VERSION is set and will override the checked-in ESP-IDF pin."
fi
TARGET="xtensa-esp32s3-espidf"

# Use the Espressif Rust toolchain explicitly when available (CI via xtensa-toolchain action).
if cargo +esp --version >/dev/null 2>&1; then
    CARGO_BIN=(cargo +esp)
    BUILD_FLAGS=("-Z" "build-std=std,panic_abort")
else
    CARGO_BIN=(cargo)
    BUILD_FLAGS=()
    echo "Warning: esp toolchain not found in rustup; using default cargo toolchain."
fi

"${CARGO_BIN[@]}" build "${BUILD_FLAGS[@]}" --locked --package usb2ble-fw --target "$TARGET"

echo "Target build preflight passed for $TARGET."
