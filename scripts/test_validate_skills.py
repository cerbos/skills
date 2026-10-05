import importlib.util
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "validate_skills", Path(__file__).with_name("validate_skills.py")
)
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)

SKILL = """\
---
name: demo
description: Demo skill for validator tests.
metadata:
  version: "1.0"
---

# Demo

## Setup

Read [references/guide.md](references/guide.md) and `references/{alpha,beta}.md`.
Run `docker run ghcr.io/cerbos/cerbos:0.55.0 compile`.
"""


class ValidateSkillsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.skill = self.root / "cerbos" / "demo"
        self.write("SKILL.md", SKILL)
        self.write("references/guide.md", "# Guide\n\nSee [setup](../SKILL.md#setup) and `nested/deep.md`.\n")
        self.write("references/nested/deep.md", "# Deep\n")
        self.write("references/alpha.md", "# Alpha\n")
        self.write("references/beta.md", "# Beta\n")
        patches = [
            patch.object(validator, "ROOT", self.root),
            patch.object(validator, "SKILLS", self.root / "cerbos"),
            patch.object(validator, "DOCS", []),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, text):
        path = self.skill / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text))

    def errors(self, base=None):
        return validator.validate(base)[1]

    def test_valid_skill_passes(self):
        self.assertEqual(self.errors(), [])

    def test_unsupported_field_and_name_mismatch(self):
        self.write("SKILL.md", SKILL.replace("name: demo", "name: other\nversion: 2"))
        errors = "\n".join(self.errors())
        self.assertIn("unsupported frontmatter field 'version'", errors)
        self.assertIn("name 'other' must equal", errors)

    def test_missing_version(self):
        self.write("SKILL.md", SKILL.replace('  version: "1.0"\n', "  author: cerbos\n"))
        self.assertIn("metadata.version", "\n".join(self.errors()))

    def test_too_long(self):
        self.write("SKILL.md", SKILL + "line\n" * validator.MAX_SKILL_LINES)
        self.assertIn("exceeds 500", "\n".join(self.errors()))

    def test_orphan_file(self):
        self.write("references/orphan.md", "# Orphan\n")
        self.assertEqual(
            self.errors(),
            ["cerbos/demo/references/orphan.md: not referenced from SKILL.md or any file it references"],
        )

    def test_broken_link_and_anchor(self):
        self.write("references/guide.md", "# Guide\n\n[x](missing.md) [y](../SKILL.md#nope) `nested/deep.md`\n")
        errors = "\n".join(self.errors())
        self.assertIn("'missing.md' does not exist", errors)
        self.assertIn("'../SKILL.md#nope' names a heading", errors)

    def test_latest_tag(self):
        self.write("SKILL.md", SKILL.replace(":0.55.0", ":latest"))
        self.assertIn("ghcr.io/cerbos/cerbos:latest", "\n".join(self.errors()))

    def test_version_bump_required_for_changed_skill(self):
        def git(*args):
            subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True)

        git("init", "-q")
        git("add", ".")
        git("-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "base")
        self.write("references/alpha.md", "# Alpha\n\nChanged.\n")
        self.assertIn("not above 1.0", "\n".join(self.errors(base="HEAD")))
        self.write("SKILL.md", SKILL.replace('"1.0"', '"1.1"'))
        self.assertEqual(self.errors(base="HEAD"), [])


if __name__ == "__main__":
    unittest.main()
