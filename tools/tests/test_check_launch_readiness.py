import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "check_launch_readiness.py"
SPEC = importlib.util.spec_from_file_location("check_launch_readiness", SCRIPT)
check_launch_readiness = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = check_launch_readiness
SPEC.loader.exec_module(check_launch_readiness)


def write_required_repo(root: Path, *, license_file: bool = False, license_blocker: bool = True) -> None:
    for path in check_launch_readiness.REQUIRED_FILES:
        full = root / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(f"# {path.name}\n", encoding="utf-8")

    (root / "README.md").write_text(
        "# USB2BLE\n\nSee [Evidence](docs/EVIDENCE_INDEX.md).\n",
        encoding="utf-8",
    )
    if license_file:
        (root / "LICENSE").write_text("Test license\n", encoding="utf-8")
    if license_blocker:
        (root / "docs" / "LAUNCH_BLOCKERS.md").write_text(
            "# Launch Blockers\n\n## License\n\nStatus: unresolved.\n",
            encoding="utf-8",
        )

    evidence_dir = root / "docs" / "milestone-evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / "GOOD_WITNESS_2026-05-28.md").write_text(
        "# Good Witness\n\nStatus: real evidence.\n\n## Limitations\n\n- Limited.\n",
        encoding="utf-8",
    )
    (root / "docs" / "EVIDENCE_INDEX.md").write_text(
        "# Evidence Index\n\n"
        "| Evidence | Date | Claim Proven | Context | Target Artifacts | Limitations | Supports |\n"
        "| --- | --- | --- | --- | --- | --- | --- |\n"
        "| [GOOD_WITNESS_2026-05-28.md](milestone-evidence/GOOD_WITNESS_2026-05-28.md) | 2026-05-28 | Smoke. | Context. | none listed | Limited. | M6 |\n",
        encoding="utf-8",
    )
    for path in (
        root / "ACCEPTANCE_CHECKLIST.md",
        root / "COMPATIBILITY_MATRIX.md",
        root / "docs" / "PROJECT_STATUS_HANDOFF.md",
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")

    source_checker = SCRIPT.parent / "check_evidence_docs.py"
    checker_path = root / "tools" / "check_evidence_docs.py"
    checker_path.parent.mkdir(parents=True, exist_ok=True)
    checker_path.write_text(source_checker.read_text(encoding="utf-8"), encoding="utf-8")


class LaunchReadinessTests(unittest.TestCase):
    def test_valid_repo_with_license_blocker_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_required_repo(root)
            self.assertEqual(check_launch_readiness.check_repository(root), [])

    def test_missing_template_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_required_repo(root)
            (root / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml").unlink()
            messages = [issue.message for issue in check_launch_readiness.check_repository(root)]
            self.assertTrue(any("required public-launch file" in message for message in messages))

    def test_missing_license_and_blocker_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_required_repo(root, license_blocker=False)
            messages = [issue.message for issue in check_launch_readiness.check_repository(root)]
            self.assertTrue(any("missing root license" in message for message in messages))

    def test_missing_readme_link_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_required_repo(root)
            (root / "README.md").write_text("[Missing](docs/MISSING.md)\n", encoding="utf-8")
            messages = [issue.message for issue in check_launch_readiness.check_repository(root)]
            self.assertTrue(any("link target missing" in message for message in messages))


if __name__ == "__main__":
    unittest.main()
