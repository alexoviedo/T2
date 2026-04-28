#!/bin/bash
set -e

# Target for ESP32-S3 xtensa
TARGET="xtensa-esp32s3-espidf"
BINARY="target/$TARGET/debug/usb2ble-fw"

echo "Flashing USB2BLE firmware..."

if ! command -v espflash &> /dev/null; then
    echo "Error: espflash not found."
    echo "Install with: cargo install espflash"
    exit 1
fi

if [ ! -f "$BINARY" ]; then
    echo "Error: Binary not found at $BINARY"
    echo "Run scripts/build.sh first."
    exit 1
fi

# Invoke espflash. Arguments like --port can be passed to this script.
espflash flash "$@" "$BINARY"

echo "Flash complete."
