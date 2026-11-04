from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/milo-mep"


class ReleaseTests(unittest.TestCase):
    def test_release_identity_and_reference_routes(self):
        skill = (SKILL / "SKILL.md").read_text()
        version = re.search(r'^  version: "(\d+\.\d+\.\d+)"$', skill, re.M)
        self.assertIsNotNone(version, "skill needs a semantic release version in metadata")
        self.assertIn(f"**Skill release: {version.group(1)}.**", skill)
        self.assertIn(f"**Skill release {version.group(1)}", (SKILL / "CHANGELOG.md").read_text())
        description = re.search(r"description: >-\n(.*?)\n---", skill, re.S).group(1)
        self.assertLessEqual(len(" ".join(line.strip() for line in description.splitlines())), 1024)
        pin = (SKILL / "assets/source/SOURCE_VERSION").read_text()
        self.assertRegex(pin, r"commit:\s+[a-f0-9]{40}\b")
        for path in set(re.findall(r"(?:references|assets|scripts)/[\w./-]+\.(?:md|py|mjs|js|json|xlsx)", skill)):
            self.assertTrue((SKILL / path).is_file(), path)

    def test_generated_browser_tool_is_current_and_check_is_read_only(self):
        scripts = SKILL / "scripts"
        with tempfile.TemporaryDirectory() as temp:
            isolated = Path(temp)
            for name in ("build-lint-html.mjs", "lint-core.mjs", "lint-ui.js", "lint.html"):
                shutil.copy2(scripts / name, isolated / name)
            command = ["node", str(isolated / "build-lint-html.mjs")]
            current = subprocess.run(command + ["--check"], capture_output=True, text=True)
            self.assertEqual(current.returncode, 0, current.stderr)
            original = (isolated / "lint.html").read_bytes()
            with (isolated / "lint-core.mjs").open("a") as source:
                source.write("\n// freshness-test change\n")
            stale = subprocess.run(command + ["--check"], capture_output=True, text=True)
            self.assertEqual(stale.returncode, 1, stale.stderr)
            self.assertIn("is stale", stale.stderr)
            self.assertEqual((isolated / "lint.html").read_bytes(), original)
            subprocess.run(command, capture_output=True, text=True, check=True)
            subprocess.run(command + ["--check"], capture_output=True, text=True, check=True)

    def package_fixture(self, directory):
        root = Path(directory) / "repo"
        root.mkdir()
        shutil.copy2(ROOT / "package-milo-mep.sh", root)
        skill = root / "skills/milo-mep"
        shutil.copytree(SKILL, skill, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        return root, skill

    def package(self, root, cwd):
        return subprocess.run(["sh", str(root / "package-milo-mep.sh")],
                              cwd=cwd, capture_output=True, text=True)

    def test_archive_has_exact_runtime_contents_and_works_from_other_cwd(self):
        with tempfile.TemporaryDirectory() as temp:
            root, skill = self.package_fixture(temp)
            for name in (".hidden", "evals", "__pycache__"):
                folder = skill / name
                folder.mkdir()
                (folder / "excluded.txt").write_text("not shipped")
            for name in (".local", "old.skill", "cache.pyc", "cache.pyo"):
                (skill / name).write_text("not shipped")
            archive = root / "milo-mep.skill"
            archive.write_text("previous archive")
            result = self.package(root, temp)
            self.assertEqual(result.returncode, 0, result.stderr)
            expected = {
                path.relative_to(skill.parent).as_posix(): path.read_bytes()
                for path in skill.rglob("*")
                if path.is_file()
                and not any(part.startswith(".") or part in {"evals", "__pycache__"}
                            for part in path.relative_to(skill).parts)
                and path.suffix not in {".pyc", ".pyo", ".skill"}
            }
            with ZipFile(archive) as bundle:
                self.assertIsNone(bundle.testzip())
                self.assertEqual(set(bundle.namelist()), set(expected))
                for name, content in expected.items():
                    self.assertEqual(bundle.read(name), content, name)
                for required in ("SKILL.md", "CHANGELOG.md", "scripts/lint.html",
                                 "scripts/lint-core.mjs", "scripts/mep_xlsx.py",
                                 "scripts/vendor/openpyxl/__init__.py",
                                 "assets/mep-manifest-template.xlsx",
                                 "assets/source/SOURCE_VERSION",
                                 "references/synthetic-examples.md"):
                    self.assertIn(f"milo-mep/{required}", bundle.namelist())
            self.assertFalse(list(root.glob(".milo-mep-package-*")))

    def test_packaging_refuses_symlinks_without_replacing_previous_archive(self):
        with tempfile.TemporaryDirectory() as temp:
            root, skill = self.package_fixture(temp)
            archive = root / "milo-mep.skill"
            archive.write_bytes(b"keep previous archive")
            link = skill / "linked.md"
            link.symlink_to(skill / "SKILL.md")
            result = self.package(root, temp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Cannot package symlink", result.stderr)
            self.assertEqual(archive.read_bytes(), b"keep previous archive")
            self.assertFalse(list(root.glob(".milo-mep-package-*")))


if __name__ == "__main__":
    unittest.main()
