#!/bin/bash
set -euo pipefail

echo "Running no-hardware USB2BLE validation..."

cargo fmt --all -- --check
cargo clippy --workspace --all-targets --locked -- -D warnings
cargo build --workspace --locked
cargo test --workspace --locked
bash -n scripts/*.sh

if [[ -d web ]]; then
    (
        cd web
        npm ci
        npm test
        npm run build
    )
fi

echo "No-hardware validation complete."
