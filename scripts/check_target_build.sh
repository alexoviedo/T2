#!/bin/bash
set -euxo pipefail

echo "Preflight: building usb2ble-fw for ESP32-S3 target..."
TARGET="xtensa-esp32s3-espidf"

# Use the Espressif Rust toolchain explicitly when available (CI via xtensa-toolchain action).
if rustup toolchain list | grep -q '^esp'; then
    CARGO_BIN=(cargo +esp)
    RUSTC_BIN=(rustc +esp)
else
    CARGO_BIN=(cargo)
    RUSTC_BIN=(rustc)
    echo "Warning: esp toolchain not found in rustup; using default cargo toolchain."
fi

# Diagnostic: check for xtensa target support
if ! "${RUSTC_BIN[@]}" --print target-list | grep -q xtensa; then
    echo "Error: selected rustc does not support xtensa targets."
    "${RUSTC_BIN[@]}" -V
    exit 1
fi

"${CARGO_BIN[@]}" build --package usb2ble-fw --target "$TARGET"

echo "Target build preflight passed for $TARGET."
