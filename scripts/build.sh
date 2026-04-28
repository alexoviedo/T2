#!/bin/bash
set -euxo pipefail
echo "Building USB2BLE firmware for ESP32-S3..."
echo "Default ESP-IDF pin: v5.5.3 (crates/usb2ble-fw/Cargo.toml)"
if [[ -n "${IDF_PATH:-}" || -n "${ESP_IDF_VERSION:-}" ]]; then
    echo "Warning: IDF_PATH or ESP_IDF_VERSION is set and will override the checked-in ESP-IDF pin."
fi
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
