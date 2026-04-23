#!/bin/bash
set -euo pipefail

echo "Preflight: building usb2ble-fw for ESP32-S3 target..."
TARGET="xtensa-esp32s3-espidf"

cargo build --package usb2ble-fw --target "$TARGET"

echo "Target build preflight passed for $TARGET."
