# Changelog

All notable public-facing changes should be documented here.

## Unreleased

- Fixed a permanent Flight Pack input freeze after a transient ESP32-S3 USB
  interrupt-transfer resubmission failure. Stranded transfers now retry at a
  bounded interval and resume without rebuilding the USB hierarchy.
- Preserved the optimized 50 Hz Quest bridge, saved boot auto-start, Generic
  Gamepad identity, and existing Flight Pack mapping.
- Refreshed the GitHub Pages build lockfile to patched Vite, PostCSS, and Nano ID
  versions; `npm audit` reports zero known vulnerabilities.

## v0.1.0-alpha

First public alpha release candidate:

- Licensed the project under Apache-2.0.
- Added public launch-readiness docs, community templates, and release checks.
- Added a self-hosted browser game/app compatibility smoke witness for the
  refined Generic Flight Pack profile.
- Added refined Generic live bridge soak and axis exposure evidence.
- Added runtime config persistence and Chrome Web Serial configurator smoke
  evidence.
- ESP32-S3 firmware for USB HID to BLE Generic/Xbox-style gamepad personas.
- Web Serial configurator and ESP Web Tools flashing UI.
- Evidence-backed practical RJ12 Flight Pack Generic demo path.
- CI target preflight, firmware packaging, release artifact, and Pages deploy.
- Clear limitations around game/app compatibility, host support, reconnect
  behavior, and calibration quality.
