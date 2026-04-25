#!/bin/bash
set -e
echo "Building USB2BLE firmware for ESP32-S3..."

# Target for ESP32-S3 xtensa
TARGET="xtensa-esp32s3-espidf"

# Check if ldproxy is installed (common requirement for ESP-IDF)
if ! command -v ldproxy &> /dev/null; then
    echo "Warning: ldproxy not found. This is usually needed for ESP-IDF builds."
    echo "Install with: cargo install ldproxy"
fi

# Use the Espressif Rust toolchain explicitly when available
if rustup toolchain list | grep -q '^esp'; then
    CARGO_BIN=(cargo +esp)
else
    CARGO_BIN=(cargo)
    echo "Warning: esp toolchain not found in rustup; using default cargo toolchain."
fi

# Build with correct target
"${CARGO_BIN[@]}" build --package usb2ble-fw --target $TARGET

echo "Build complete."
