#!/bin/bash
set -e

echo "Installing cargo-binstall using the official pre-built installer script..."
curl -L --proto '=https' --tlsv1.2 -sSf https://raw.githubusercontent.com/cargo-bins/cargo-binstall/main/install-from-binstall-release.sh | bash

echo "Installing ESP-IDF Rust prerequisites (espup, ldproxy, espflash)..."
cargo binstall espup ldproxy espflash -y

echo "Installing ESP Rust toolchain (forcing v1.90.0.0 for Intel Mac compatibility)..."
espup install --toolchain-version 1.90.0.0

echo "============================================================"
echo "Environment fixed! To apply the changes to your current shell, run:"
echo "source ~/export-esp.sh"
echo "Then, you can try running ./scripts/build.sh and espflash again."
echo "============================================================"
