# AGENTS.md

- Code and checked-in evidence are the source of truth; never trust milestone claims without artifacts.
- Do not mark milestones complete without reproducible evidence in-repo.
- Never present synthetic target witness as real hardware behavior.
- Keep platform-specific and `unsafe` implementation details in platform crates.
- Prefer the smallest honest hardware demo before expanding scope.
- Current focus: **M2B.1 real attach/detach + identity witness on ESP32-S3**.
- Before changing ESP-IDF build wiring, run `scripts/verify_cloud_equivalent.sh` or explain exactly why it cannot be run.
