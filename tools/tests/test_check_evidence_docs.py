import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "check_evidence_docs.py"
SPEC = importlib.util.spec_from_file_location("check_evidence_docs", SCRIPT)
check_evidence_docs = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = check_evidence_docs
SPEC.loader.exec_module(check_evidence_docs)


class EvidenceDocsValidationTests(unittest.TestCase):
    def write_repo(self, root: Path, evidence_text: str, readme_ref: str) -> None:
        evidence_dir = root / "docs" / "milestone-evidence"
        evidence_dir.mkdir(parents=True)
        (evidence_dir / "GOOD_WITNESS_2026-05-28.md").write_text(evidence_text, encoding="utf-8")
        (root / "docs" / "EVIDENCE_INDEX.md").write_text(
            "# Evidence Index\n\n"
            "| Evidence | Date | Claim Proven | Context | Target Artifacts | Limitations | Supports |\n"
            "| --- | --- | --- | --- | --- | --- | --- |\n"
            "| [GOOD_WITNESS_2026-05-28.md](milestone-evidence/GOOD_WITNESS_2026-05-28.md) | 2026-05-28 | Host-visible smoke. | Test context. | `target/example/run` | Not game/app compatibility. | M6 |\n",
            encoding="utf-8",
        )
        for name in ("ACCEPTANCE_CHECKLIST.md", "COMPATIBILITY_MATRIX.md", "README.md"):
            (root / name).write_text(readme_ref, encoding="utf-8")
        (root / "docs" / "PROJECT_STATUS_HANDOFF.md").write_text(readme_ref, encoding="utf-8")

    def test_valid_minimal_repository_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_repo(
                root,
                "# Good Witness - 2026-05-28\n\n"
                "Status: real hardware evidence.\n\n"
                "Artifact: `target/example/run`\n\n"
                "## Limitations\n\n"
                "- This is not game/app compatibility.\n",
                "See `docs/milestone-evidence/GOOD_WITNESS_2026-05-28.md`.\n",
            )
            self.assertEqual(check_evidence_docs.check_repository(root), [])

    def test_missing_referenced_evidence_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_repo(
                root,
                "# Good Witness - 2026-05-28\n\nStatus: ok.\n\n## Limitations\n\n- Limited.\n",
                "See `docs/milestone-evidence/MISSING_WITNESS_2026-05-28.md`.\n",
            )
            messages = [issue.message for issue in check_evidence_docs.check_repository(root)]
            self.assertTrue(any("references missing evidence file" in message for message in messages))

    def test_unqualified_game_app_claim_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_repo(
                root,
                "# Good Witness - 2026-05-28\n\n"
                "Status: ok.\n\n"
                "This proves game/app compatibility.\n\n"
                "## Limitations\n\n- Limited.\n",
                "",
            )
            messages = [issue.message for issue in check_evidence_docs.check_repository(root)]
            self.assertTrue(any("possible unqualified" in message for message in messages))


if __name__ == "__main__":
    unittest.main()
