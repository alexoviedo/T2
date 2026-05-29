#!/usr/bin/env python3
"""Validate checked-in evidence docs and status references without hardware."""

from __future__ import annotations

import argparse
import dataclasses
import re
import sys
from pathlib import Path


EVIDENCE_DIR = Path("docs/milestone-evidence")
EVIDENCE_INDEX = Path("docs/EVIDENCE_INDEX.md")
STATUS_DOCS = (
    Path("README.md"),
    Path("ACCEPTANCE_CHECKLIST.md"),
    Path("COMPATIBILITY_MATRIX.md"),
    Path("docs/PROJECT_STATUS_HANDOFF.md"),
    EVIDENCE_INDEX,
)

EVIDENCE_LINK_RE = re.compile(
    r"(?:docs/)?milestone-evidence/[A-Za-z0-9_.-]+\.md"
)
TARGET_PATH_RE = re.compile(r"`?(target/[A-Za-z0-9_./:-]+)`?")
TITLE_RE = re.compile(r"(?m)^#\s+\S")
STATUS_OR_SUMMARY_RE = re.compile(
    r"(?im)^(Status:|##\s+(Summary|Scope|Result Summary|Proven)\b)"
)
LIMITATION_RE = re.compile(
    r"(?im)^(##\s+(Limitations|Not Proven|Not Proven By This Build Witness)\b|"
    r".*(does not prove|not proven|not claimed|not accepted|not a .*claim|"
    r"not broad|remains? open|requires separate evidence|future work|blocked by).*)"
)
NEGATION_RE = re.compile(
    r"\b(not|no|unclaimed|without|separate|future|open|blocked|beyond|"
    r"requires|require|does not|do not|not proven|not claimed|not a|"
    r"not broad|remaining|remain|remains|unproven|still needs|"
    r"limitation|not evidence)\b"
)
FORBIDDEN_CLAIM_RE = re.compile(
    r"(game/app compatibility|app/game compatibility|real game/app|"
    r"broad game compatibility|broad xbox|console compatibility|"
    r"ble bond persistence|bond persistence|broad host|broad browser|"
    r"product-ready|final product|final calibration|final flight pack|"
    r"three-separate-usb)",
    re.IGNORECASE,
)


@dataclasses.dataclass(frozen=True)
class IndexEntry:
    path: Path
    date: str
    claim: str
    context: str
    artifacts: str
    limitations: str
    supports: str


@dataclasses.dataclass(frozen=True)
class Issue:
    path: Path
    message: str

    def format(self) -> str:
        return f"{self.path}: {self.message}"


def repo_path(root: Path, path: Path) -> Path:
    return root / path


def normalize_evidence_link(link: str) -> Path:
    path = Path(link.strip("`"))
    if path.parts and path.parts[0] == "milestone-evidence":
        return Path("docs") / path
    return path


def split_markdown_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def parse_evidence_index(root: Path) -> tuple[dict[Path, IndexEntry], list[Issue]]:
    path = repo_path(root, EVIDENCE_INDEX)
    issues: list[Issue] = []
    entries: dict[Path, IndexEntry] = {}
    if not path.exists():
        return entries, [Issue(EVIDENCE_INDEX, "missing evidence index")]

    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.startswith("| ["):
            continue
        cells = split_markdown_row(line)
        if len(cells) != 7:
            issues.append(Issue(EVIDENCE_INDEX, f"line {line_number}: expected 7 table cells"))
            continue
        match = re.search(r"\(([^)]+)\)", cells[0])
        if not match:
            issues.append(Issue(EVIDENCE_INDEX, f"line {line_number}: evidence link missing"))
            continue
        evidence_path = normalize_evidence_link(match.group(1))
        entries[evidence_path] = IndexEntry(
            path=evidence_path,
            date=cells[1],
            claim=cells[2],
            context=cells[3],
            artifacts=cells[4],
            limitations=cells[5],
            supports=cells[6],
        )
    return entries, issues


def evidence_files(root: Path) -> list[Path]:
    return sorted((root / EVIDENCE_DIR).glob("*.md"))


def referenced_evidence_paths(root: Path) -> dict[Path, set[Path]]:
    references: dict[Path, set[Path]] = {}
    for doc in STATUS_DOCS:
        path = repo_path(root, doc)
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        references[doc] = {normalize_evidence_link(match.group(0)) for match in EVIDENCE_LINK_RE.finditer(text)}
    return references


def has_limitations(text: str, index_entry: IndexEntry | None) -> bool:
    if LIMITATION_RE.search(text):
        return True
    if index_entry and index_entry.limitations and index_entry.limitations not in {"-", "none", "None"}:
        return True
    return False


def check_overclaims(path: Path, text: str) -> list[Issue]:
    issues: list[Issue] = []
    lines = text.splitlines()
    active_boundary_heading = ""
    for line_number, line in enumerate(lines, 1):
        if line.startswith("## "):
            heading = line.lower()
            active_boundary_heading = (
                line
                if any(word in heading for word in ("limitation", "not proven", "honest conclusion"))
                else ""
            )
        elif line.strip().lower().startswith("not proven"):
            active_boundary_heading = line
        if not FORBIDDEN_CLAIM_RE.search(line):
            continue
        previous_two = lines[line_number - 3] if line_number > 2 else ""
        previous_line = lines[line_number - 2] if line_number > 1 else ""
        next_line = lines[line_number] if line_number < len(lines) else ""
        context = " ".join((active_boundary_heading, previous_two, previous_line, line, next_line)).lower()
        if NEGATION_RE.search(context):
            continue
        issues.append(
            Issue(
                path,
                f"line {line_number}: possible unqualified compatibility/product claim: {line.strip()}",
            )
        )
    return issues


def check_repository(root: Path) -> list[Issue]:
    root = root.resolve()
    index_entries, issues = parse_evidence_index(root)
    files = [path.relative_to(root) for path in evidence_files(root)]
    file_set = set(files)

    for evidence_path in files:
        text = repo_path(root, evidence_path).read_text(encoding="utf-8")
        index_entry = index_entries.get(evidence_path)
        if not TITLE_RE.search(text):
            issues.append(Issue(evidence_path, "missing top-level title"))
        if not STATUS_OR_SUMMARY_RE.search(text):
            issues.append(Issue(evidence_path, "missing Status, Summary, Scope, or Proven section"))
        if not has_limitations(text, index_entry):
            issues.append(Issue(evidence_path, "missing explicit limitation/not-proven boundary"))
        if index_entry is None:
            issues.append(Issue(evidence_path, "not listed in docs/EVIDENCE_INDEX.md"))
        else:
            target_paths = TARGET_PATH_RE.findall(text)
            if target_paths and "target/" not in index_entry.artifacts:
                issues.append(
                    Issue(
                        evidence_path,
                        "mentions target artifacts but index artifact cell does not list a target/ path",
                    )
                )
        issues.extend(check_overclaims(evidence_path, text))

    for index_path, entry in sorted(index_entries.items()):
        if index_path not in file_set:
            issues.append(Issue(EVIDENCE_INDEX, f"indexes missing evidence file {index_path}"))
        if not entry.limitations or entry.limitations in {"-", "none", "None"}:
            issues.append(Issue(EVIDENCE_INDEX, f"{index_path.name} has no limitation summary"))

    for source_doc, refs in referenced_evidence_paths(root).items():
        for ref in sorted(refs):
            if ref not in file_set:
                issues.append(Issue(source_doc, f"references missing evidence file {ref}"))

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root")
    parser.add_argument("--verbose", action="store_true", help="Print success details")
    args = parser.parse_args()

    issues = check_repository(args.root)
    if issues:
        print("Evidence validation failed:", file=sys.stderr)
        for issue in issues:
            print(f"- {issue.format()}", file=sys.stderr)
        return 1
    if args.verbose:
        root = args.root.resolve()
        count = len(evidence_files(root))
        print(f"Evidence validation passed for {count} evidence documents.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
