#!/bin/bash
set -e

echo "Opening USB2BLE monitor..."

if ! command -v espflash &> /dev/null; then
    echo "Error: espflash not found."
    echo "Install with: cargo install espflash"
    exit 1
fi

# Invoke espflash monitor. Arguments like --port can be passed to this script.
espflash monitor "$@"
