#!/usr/bin/env python3
"""Validate no-hardware public-launch readiness checks."""

from __future__ import annotations

import argparse
import dataclasses
import importlib.util
import re
import sys
from pathlib import Path


REQUIRED_FILES = (
    Path("README.md"),
    Path("SECURITY.md"),
    Path("CONTRIBUTING.md"),
    Path("CODE_OF_CONDUCT.md"),
    Path("SUPPORT.md"),
    Path("CHANGELOG.md"),
    Path("ROADMAP.md"),
    Path("docs/RELEASE_CHECKLIST.md"),
    Path("docs/PUBLIC_CLAIMS.md"),
    Path("docs/EVIDENCE_INDEX.md"),
    Path(".github/PULL_REQUEST_TEMPLATE.md"),
    Path(".github/ISSUE_TEMPLATE/bug_report.yml"),
    Path(".github/ISSUE_TEMPLATE/hardware_compatibility.yml"),
    Path(".github/ISSUE_TEMPLATE/hardware_support_request.yml"),
    Path(".github/ISSUE_TEMPLATE/documentation_issue.yml"),
    Path(".github/ISSUE_TEMPLATE/feature_request.yml"),
)

LICENSE_FILES = (
    Path("LICENSE"),
    Path("LICENSE.md"),
    Path("LICENSE.txt"),
    Path("COPYING"),
)

README_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
FORBIDDEN_README_RE = re.compile(
    r"\b(broad game compatibility|iphone compatibility|ble bond persistence|"
    r"final product-quality|consumer-ready|production ready)\b",
    re.IGNORECASE,
)
NEGATION_RE = re.compile(
    r"\b(not|no|without|unproven|not yet proven|not claimed|do not|"
    r"until|requires|forbidden|unsupported)\b",
    re.IGNORECASE,
)


@dataclasses.dataclass(frozen=True)
class Issue:
    path: Path
    message: str

    def format(self) -> str:
        return f"{self.path}: {self.message}"


def load_evidence_checker(root: Path):
    script = root / "tools" / "check_evidence_docs.py"
    spec = importlib.util.spec_from_file_location("check_evidence_docs", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {script}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def file_exists(root: Path, path: Path) -> bool:
    return (root / path).is_file()


def has_license(root: Path) -> bool:
    return any(file_exists(root, path) for path in LICENSE_FILES)


def has_license_blocker(root: Path) -> bool:
    blocker = root / "docs" / "LAUNCH_BLOCKERS.md"
    if not blocker.is_file():
        return False
    text = blocker.read_text(encoding="utf-8").lower()
    return "license" in text and "unresolved" in text


def markdown_readme_links(root: Path) -> list[tuple[str, int]]:
    readme = root / "README.md"
    links: list[tuple[str, int]] = []
    for line_number, line in enumerate(readme.read_text(encoding="utf-8").splitlines(), 1):
        for match in README_LINK_RE.finditer(line):
            links.append((match.group(1), line_number))
    return links


def is_external_link(target: str) -> bool:
    return (
        "://" in target
        or target.startswith("#")
        or target.startswith("mailto:")
        or target.startswith("tel:")
    )


def check_readme_links(root: Path) -> list[Issue]:
    issues: list[Issue] = []
    for target, line_number in markdown_readme_links(root):
        if is_external_link(target):
            continue
        path_text = target.split("#", 1)[0]
        if not path_text:
            continue
        if not (root / path_text).exists():
            issues.append(Issue(Path("README.md"), f"line {line_number}: link target missing: {target}"))
    return issues


def check_readme_claim_boundaries(root: Path) -> list[Issue]:
    readme = root / "README.md"
    issues: list[Issue] = []
    lines = readme.read_text(encoding="utf-8").splitlines()
    active_boundary_heading = ""
    for line_number, line in enumerate(lines, 1):
        if line.startswith("## "):
            heading = line.lower()
            active_boundary_heading = (
                line
                if any(word in heading for word in ("not yet proven", "safety", "limitations"))
                else ""
            )
        if not FORBIDDEN_README_RE.search(line):
            continue
        context = " ".join(
            [active_boundary_heading]
            + lines[max(0, line_number - 3): min(len(lines), line_number + 2)]
        )
        if NEGATION_RE.search(context):
            continue
        issues.append(Issue(Path("README.md"), f"line {line_number}: possible unqualified launch claim"))
    return issues


def check_repository(root: Path) -> list[Issue]:
    root = root.resolve()
    issues: list[Issue] = []

    for path in REQUIRED_FILES:
        if not file_exists(root, path):
            issues.append(Issue(path, "required public-launch file is missing"))

    if not has_license(root) and not has_license_blocker(root):
        issues.append(
            Issue(
                Path("LICENSE"),
                "missing root license and docs/LAUNCH_BLOCKERS.md does not record an unresolved license blocker",
            )
        )

    issues.extend(check_readme_links(root))
    issues.extend(check_readme_claim_boundaries(root))

    evidence_checker = load_evidence_checker(root)
    for issue in evidence_checker.check_repository(root):
        issues.append(Issue(issue.path, f"evidence validation: {issue.message}"))

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root")
    parser.add_argument("--verbose", action="store_true", help="Print success details")
    args = parser.parse_args()

    issues = check_repository(args.root)
    if issues:
        print("Launch readiness validation failed:", file=sys.stderr)
        for issue in issues:
            print(f"- {issue.format()}", file=sys.stderr)
        return 1
    if args.verbose:
        root = args.root.resolve()
        license_state = "present" if has_license(root) else "blocked"
        print(f"Launch readiness validation passed; license state: {license_state}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
