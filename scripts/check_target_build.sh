#!/bin/bash
set -euxo pipefail

echo "Preflight: building usb2ble-fw for ESP32-S3 target..."
TARGET="xtensa-esp32s3-espidf"

# Use the Espressif Rust toolchain explicitly when available (CI via xtensa-toolchain action).
if rustup toolchain list | grep -q '^esp'; then
    CARGO_BIN=(cargo +esp)
else
    CARGO_BIN=(cargo)
    echo "Warning: esp toolchain not found in rustup; using default cargo toolchain."
fi

"${CARGO_BIN[@]}" build --locked --package usb2ble-fw --target "$TARGET"

echo "Target build preflight passed for $TARGET."
