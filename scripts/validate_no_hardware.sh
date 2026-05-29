#!/bin/bash
set -euo pipefail

echo "Running no-hardware USB2BLE validation..."

cargo fmt --all -- --check
cargo clippy --workspace --all-targets --locked -- -D warnings
cargo build --workspace --locked
cargo test --workspace --locked
bash -n scripts/*.sh
python3 -m py_compile tools/*.py tools/gamepad_witness/*.py
python3 tools/check_evidence_docs.py

if [[ -d tools/tests ]]; then
    python3 -m unittest discover -s tools/tests -p 'test_*.py'
fi

if [[ -d web ]]; then
    (
        cd web
        npm ci
        npm test
        npm run build
    )
fi

echo "No-hardware validation complete."
