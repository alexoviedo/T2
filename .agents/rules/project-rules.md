---
trigger: always_on
---

You are working on the USB2BLE / T2 Rust workspace.

You must obey the repository source-of-truth docs:
- PROJECT_CHARTER.md
- FEATURES.md
- CONTRACTS.md
- MILESTONES.md
- ACCEPTANCE_CHECKLIST.md
- COMPATIBILITY_MATRIX.md

Core rules:
1. Do not silently rewrite contracts or milestone definitions.
2. Do not widen scope beyond the assigned milestone/sub-milestone.
3. Hardware truth beats simulation.
4. Do not claim completion without acceptance evidence.
5. Keep pure crates host-testable.
6. Keep ESP-IDF/platform-specific code quarantined inside platform/fw crates.
7. Put shared types and enums in usb2ble-contracts, not ad hoc local modules.
8. Do not create dead-ends for future hub support, multi-device support, arbitrary generic mapping, or BLE Xbox persona support.
9. Every meaningful change must include tests.
10. Every milestone task must end with an evidence section:
   - what changed
   - files/crates changed
   - tests added/updated
   - exact commands run
   - host evidence
   - hardware evidence if required
   - known limitations

When uncertain, choose the smallest change that preserves long-term architecture.