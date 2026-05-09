# AGENTS.md

- Code and checked-in evidence are the source of truth; never trust milestone claims without artifacts.
- Do not mark milestones complete without reproducible evidence in-repo.
- Never present synthetic target witness as real hardware behavior.
- Keep platform-specific and `unsafe` implementation details in platform crates.
- Prefer the smallest honest hardware demo before expanding scope.
- Current focus: preserve the known **Generic BLE Gamepad** hardware path while validating **Xbox BLE pairing/input compatibility** with real ESP32-S3 witness evidence.
- Never claim Xbox host compatibility without checked-in pairing/input transcripts and any host-visible evidence that exists.
- Before changing ESP-IDF build wiring, run `scripts/verify_cloud_equivalent.sh` or explain exactly why it cannot be run.
