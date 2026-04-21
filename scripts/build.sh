#!/bin/bash
set -e
echo "Building USB2BLE firmware..."
cargo build --package usb2ble-fw
echo "Build complete."
