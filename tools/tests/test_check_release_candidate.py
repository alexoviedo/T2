import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "check_release_candidate.py"
SPEC = importlib.util.spec_from_file_location("check_release_candidate", SCRIPT)
check_release_candidate = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = check_release_candidate
SPEC.loader.exec_module(check_release_candidate)


def write_required_repo(root: Path) -> None:
    for path in check_release_candidate.REQUIRED_RELEASE_FILES:
        full = root / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text("# file\n", encoding="utf-8")

    (root / "LICENSE").write_text(
        "Apache License\nVersion 2.0\n\nCopyright 2026 Alex Oviedo\n",
        encoding="utf-8",
    )
    (root / "README.md").write_text(
        "# USB2BLE\n\nLicensed under Apache-2.0. See [LICENSE](LICENSE).\n",
        encoding="utf-8",
    )
    (root / "CHANGELOG.md").write_text(
        "# Changelog\n\n## Unreleased\n\n- Future.\n\n## v0.1.0-alpha\n\n- Apache-2.0.\n",
        encoding="utf-8",
    )
    (root / "docs" / "RELEASE_CHECKLIST.md").write_text(
        "./scripts/validate_no_hardware.sh\n"
        "./scripts/check_target_build.sh\n"
        "tools/check_evidence_docs.py\n"
        "tools/check_launch_readiness.py\n"
        "tools/check_release_candidate.py\n"
        "scripts/package_firmware.sh\n"
        "ESP Web Tools\n"
        "docs/PUBLIC_CLAIMS.md\n",
        encoding="utf-8",
    )
    web = root / "web"
    web.mkdir()
    (web / "package.json").write_text(
        '{"private": true, "license": "Apache-2.0"}\n',
        encoding="utf-8",
    )
    crate = root / "crates" / "usb2ble-example"
    crate.mkdir(parents=True)
    (crate / "Cargo.toml").write_text(
        '[package]\nname = "usb2ble-example"\nversion = "0.1.0"\nlicense = "Apache-2.0"\n',
        encoding="utf-8",
    )


class ReleaseCandidateTests(unittest.TestCase):
    def test_valid_release_metadata_passes_core_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_required_repo(root)
            issues = []
            issues.extend(check_release_candidate.check_license(root))
            issues.extend(check_release_candidate.check_readme(root))
            issues.extend(check_release_candidate.check_changelog(root))
            issues.extend(check_release_candidate.check_web_package(root))
            issues.extend(check_release_candidate.check_cargo_metadata(root))
            issues.extend(check_release_candidate.check_release_files(root))
            issues.extend(check_release_candidate.check_hidden_blockers(root))
            self.assertEqual(issues, [])

    def test_missing_apache_license_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_required_repo(root)
            (root / "LICENSE").write_text("MIT\n", encoding="utf-8")
            messages = [issue.message for issue in check_release_candidate.check_license(root)]
            self.assertTrue(any("Apache" in message for message in messages))

    def test_unlicensed_web_package_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_required_repo(root)
            license_name = "UN" + "LICENSED"
            (root / "web" / "package.json").write_text(
                f'{{"private": true, "license": "{license_name}"}}\n',
                encoding="utf-8",
            )
            messages = [issue.message for issue in check_release_candidate.check_web_package(root)]
            self.assertTrue(any("license should" in message for message in messages))

    def test_hidden_launch_todo_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_required_repo(root)
            marker = "TODO" + " launch"
            (root / "README.md").write_text(f"{marker}: fill this in\n", encoding="utf-8")
            messages = [issue.message for issue in check_release_candidate.check_hidden_blockers(root)]
            self.assertTrue(any("hidden launch blocker" in message for message in messages))


if __name__ == "__main__":
    unittest.main()
