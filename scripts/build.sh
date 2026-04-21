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

# Build with correct target
cargo build --package usb2ble-fw --target $TARGET

echo "Build complete."
