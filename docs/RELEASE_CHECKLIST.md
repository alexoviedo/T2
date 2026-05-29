# Release Checklist

Use this before public announcements, tags, or GitHub releases.

## Required Before Public Launch

- [ ] Root `LICENSE` selected and committed.
- [ ] `docs/LAUNCH_BLOCKERS.md` has no unresolved launch-blocking items.
- [ ] `./scripts/validate_no_hardware.sh` passes.
- [ ] `./scripts/check_target_build.sh` passes.
- [ ] CI passes on the public branch.
- [ ] README current status matches `docs/EVIDENCE_INDEX.md`.
- [ ] `python3 tools/check_evidence_docs.py --verbose` passes.
- [ ] `python3 tools/check_launch_readiness.py --verbose` passes.

## Evidence

- [ ] New behavior claims have checked-in evidence summaries.
- [ ] Generated artifacts stay under `target/` and are not committed.
- [ ] Evidence docs include limitations and target artifact paths.
- [ ] `docs/EVIDENCE_INDEX.md` includes every checked-in evidence document.

## Firmware And Web Artifacts

- [ ] `scripts/package_firmware.sh` creates the merged ESP32-S3 image.
- [ ] CI uploads `usb2ble-fw-esp32s3-flashable`.
- [ ] `latest` GitHub Release contains the merged image, manifest text, and ELF.
- [ ] GitHub Pages deploy includes `web/dist/firmware/manifest.json`.
- [ ] ESP Web Tools manifest points at the published merged image.

## Community And Support

- [ ] `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, and `SUPPORT.md`
  are present.
- [ ] Issue templates and pull request template are present.
- [ ] Public repository URL, Pages URL, and support destination are confirmed.

## Claim Review

- [ ] Public wording follows `docs/PUBLIC_CLAIMS.md`.
- [ ] No broad game/app, iPhone, Xbox refined host-visible, bond persistence,
  final calibration, broad host/browser, or three-separate-USB claims are made
  without evidence.
