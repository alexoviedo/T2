# AGENTS.md

- Code and checked-in evidence are the source of truth; never trust milestone claims without artifacts.
- Do not mark milestones complete without reproducible evidence in-repo.
- Never present synthetic target witness as real hardware behavior.
- Keep platform-specific and `unsafe` implementation details in platform crates.
- Prefer the smallest honest hardware demo before expanding scope.
- Current focus: preserve the known **Generic/Xbox live bridge** hardware paths while hardening demo credibility with soak, calibration, and real app/game evidence.
- Never claim host, soak, calibration, or game/app compatibility without checked-in transcripts and host-visible evidence that exists.
- Before changing ESP-IDF build wiring, run `scripts/verify_cloud_equivalent.sh` or explain exactly why it cannot be run.
