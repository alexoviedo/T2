# Security Policy

USB2BLE is experimental firmware that interacts with USB HID devices, Bluetooth
LE HID hosts, and browser Web Serial APIs.

## Reporting Vulnerabilities

Please report security issues privately using GitHub private vulnerability
reporting or GitHub Security Advisories for this repository when available.

If private reporting is not enabled, open a minimal public issue that says a
security report is available, but do not include exploit details, private logs,
device identifiers, or sensitive host information in the issue body.

## Supported Versions

Until the first public release, only the current `main` branch is considered for
security fixes.

## Scope

Security reports may include:

- unsafe firmware behavior,
- malformed USB HID descriptor/report handling,
- Web Serial or firmware flashing UI issues,
- BLE identity or pairing concerns,
- scripts that mishandle local files or command arguments.

This project does not currently provide safety-critical guarantees. Do not use
it in situations where unexpected input, disconnects, or firmware faults could
create physical risk.
