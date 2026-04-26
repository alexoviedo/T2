#!/bin/bash
set -euxo pipefail
echo "Building USB2BLE firmware for ESP32-S3..."
TARGET="xtensa-esp32s3-espidf"
if ! command -v ldproxy &> /dev/null; then
    echo "Warning: ldproxy not found. This is usually needed for ESP-IDF builds."
    echo "Install with: cargo install ldproxy"
fi
if rustup toolchain list | grep -q '^esp'; then
    CARGO_BIN=(cargo +esp)
else
    CARGO_BIN=(cargo)
    echo "Warning: esp toolchain not found in rustup; using default cargo toolchain."
fi
"${CARGO_BIN[@]}" build -Z build-std=std,panic_abort --locked --package usb2ble-fw --target "$TARGET"
echo "Build complete."
