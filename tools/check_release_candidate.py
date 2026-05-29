#!/usr/bin/env python3
"""Validate no-hardware v0.1.0-alpha release-candidate readiness."""

from __future__ import annotations

import argparse
import dataclasses
import importlib.util
import json
import re
import sys
from pathlib import Path


EXPECTED_LICENSE = "Apache-2.0"
EXPECTED_COPYRIGHT = "Copyright 2026 Alex Oviedo"
RELEASE_VERSION = "v0.1.0-alpha"

REQUIRED_RELEASE_FILES = (
    Path("LICENSE"),
    Path("README.md"),
    Path("CHANGELOG.md"),
    Path("ROADMAP.md"),
    Path("docs/RELEASE_CHECKLIST.md"),
    Path("docs/PUBLIC_CLAIMS.md"),
    Path("docs/EVIDENCE_INDEX.md"),
    Path("scripts/package_firmware.sh"),
    Path("scripts/build.sh"),
    Path("scripts/flash.sh"),
    Path(".github/workflows/ci.yml"),
)

SKIP_DIRS = {
    ".git",
    ".embuild",
    ".idf_tools",
    "target",
    "node_modules",
    "dist",
}

HIDDEN_BLOCKER_PATTERNS = (
    "TODO" + " launch",
    "FIXME" + " public",
)


@dataclasses.dataclass(frozen=True)
class Issue:
    path: Path
    message: str

    def format(self) -> str:
        return f"{self.path}: {self.message}"


def load_tool(root: Path, name: str):
    script = root / "tools" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {script}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def check_license(root: Path) -> list[Issue]:
    issues: list[Issue] = []
    path = root / "LICENSE"
    if not path.is_file():
        return [Issue(Path("LICENSE"), "missing root Apache-2.0 license")]
    text = read_text(path)
    if "Apache License" not in text or "Version 2.0" not in text:
        issues.append(Issue(Path("LICENSE"), "does not look like Apache License 2.0 text"))
    if EXPECTED_COPYRIGHT not in text:
        issues.append(Issue(Path("LICENSE"), f"missing {EXPECTED_COPYRIGHT!r}"))
    return issues


def check_readme(root: Path) -> list[Issue]:
    text = read_text(root / "README.md")
    issues: list[Issue] = []
    if EXPECTED_LICENSE not in text:
        issues.append(Issue(Path("README.md"), f"does not reference {EXPECTED_LICENSE}"))
    if "[LICENSE](LICENSE)" not in text:
        issues.append(Issue(Path("README.md"), "does not link to LICENSE"))
    return issues


def check_changelog(root: Path) -> list[Issue]:
    text = read_text(root / "CHANGELOG.md")
    issues: list[Issue] = []
    if f"## {RELEASE_VERSION}" not in text:
        issues.append(Issue(Path("CHANGELOG.md"), f"missing {RELEASE_VERSION} section"))
    if "Apache-2.0" not in text:
        issues.append(Issue(Path("CHANGELOG.md"), "release notes do not mention Apache-2.0 licensing"))
    return issues


def check_web_package(root: Path) -> list[Issue]:
    path = root / "web" / "package.json"
    if not path.is_file():
        return []
    package = json.loads(read_text(path))
    issues: list[Issue] = []
    if package.get("private") is not True:
        issues.append(Issue(Path("web/package.json"), "web package should stay private unless intentionally published"))
    if package.get("license") != EXPECTED_LICENSE:
        issues.append(Issue(Path("web/package.json"), f"license should be {EXPECTED_LICENSE}"))
    return issues


def cargo_tomls(root: Path) -> list[Path]:
    return sorted(path for path in root.glob("crates/*/Cargo.toml") if path.is_file())


def check_cargo_metadata(root: Path) -> list[Issue]:
    issues: list[Issue] = []
    for path in cargo_tomls(root):
        text = read_text(path)
        if f'license = "{EXPECTED_LICENSE}"' not in text:
            issues.append(Issue(path.relative_to(root), f"missing license = {EXPECTED_LICENSE!r}"))
    return issues


def check_release_files(root: Path) -> list[Issue]:
    issues: list[Issue] = []
    for path in REQUIRED_RELEASE_FILES:
        if not (root / path).is_file():
            issues.append(Issue(path, "required release-candidate file is missing"))
    checklist = root / "docs" / "RELEASE_CHECKLIST.md"
    if checklist.is_file():
        text = read_text(checklist)
        for phrase in (
            "./scripts/validate_no_hardware.sh",
            "./scripts/check_target_build.sh",
            "tools/check_evidence_docs.py",
            "tools/check_launch_readiness.py",
            "tools/check_release_candidate.py",
            "scripts/package_firmware.sh",
            "ESP Web Tools",
            "docs/PUBLIC_CLAIMS.md",
        ):
            if phrase not in text:
                issues.append(Issue(Path("docs/RELEASE_CHECKLIST.md"), f"missing checklist phrase {phrase!r}"))
    return issues


def iter_repo_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        yield rel, path


def check_hidden_blockers(root: Path) -> list[Issue]:
    issues: list[Issue] = []
    for rel, path in iter_repo_files(root):
        try:
            text = read_text(path)
        except UnicodeDecodeError:
            continue
        if rel == Path("docs/LAUNCH_BLOCKERS.md"):
            continue
        for pattern in HIDDEN_BLOCKER_PATTERNS:
            if re.search(re.escape(pattern), text, re.IGNORECASE):
                issues.append(Issue(rel, f"contains hidden launch blocker marker {pattern!r}"))
    return issues


def check_repository(root: Path) -> list[Issue]:
    root = root.resolve()
    issues: list[Issue] = []

    issues.extend(check_license(root))
    issues.extend(check_readme(root))
    issues.extend(check_changelog(root))
    issues.extend(check_web_package(root))
    issues.extend(check_cargo_metadata(root))
    issues.extend(check_release_files(root))
    issues.extend(check_hidden_blockers(root))

    evidence_checker = load_tool(root, "check_evidence_docs")
    for issue in evidence_checker.check_repository(root):
        issues.append(Issue(issue.path, f"evidence validation: {issue.message}"))

    launch_checker = load_tool(root, "check_launch_readiness")
    for issue in launch_checker.check_repository(root):
        issues.append(Issue(issue.path, f"launch validation: {issue.message}"))

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root")
    parser.add_argument("--verbose", action="store_true", help="Print success details")
    args = parser.parse_args()

    issues = check_repository(args.root)
    if issues:
        print("Release-candidate validation failed:", file=sys.stderr)
        for issue in issues:
            print(f"- {issue.format()}", file=sys.stderr)
        return 1
    if args.verbose:
        print(f"Release-candidate validation passed for {RELEASE_VERSION} ({EXPECTED_LICENSE}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
