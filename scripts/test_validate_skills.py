import importlib.util
import json
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
        self.skill = self.root / "skills" / "demo"
        self.write("SKILL.md", SKILL)
        self.write("references/guide.md", "# Guide\n\nSee [setup](../SKILL.md#setup) and `nested/deep.md`.\n")
        self.write("references/nested/deep.md", "# Deep\n")
        self.write("references/alpha.md", "# Alpha\n")
        self.write("references/beta.md", "# Beta\n")
        patches = [
            patch.object(validator, "ROOT", self.root),
            patch.object(validator, "SKILLS", self.root / "skills"),
            patch.object(validator, "DOCS", []),
            patch.object(validator, "check_manifests", lambda errors: None),
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
            ["skills/demo/references/orphan.md: not referenced from SKILL.md or any file it references"],
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


class ManifestsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for name in validator.PLUGIN_MANIFESTS:
            self.write(name, {"name": "cerbos-skills", "version": "1.0.0"})
        for name in validator.MARKETPLACES:
            self.write(name, {"plugins": [{"name": "cerbos-skills"}]})

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))

    def errors(self):
        errors = []
        with patch.object(validator, "ROOT", self.root):
            validator.check_manifests(errors)
        return errors

    def test_consistent_manifests_pass(self):
        self.assertEqual(self.errors(), [])

    def test_version_mismatch(self):
        self.write(".codex-plugin/plugin.json", {"name": "cerbos-skills", "version": "1.1.0"})
        self.write(".claude-plugin/marketplace.json", {"plugins": [{"name": "cerbos-skills", "version": "0.9.0"}]})
        errors = "\n".join(self.errors())
        self.assertIn("plugin versions disagree", errors)
        self.assertIn(".codex-plugin/plugin.json=1.1.0", errors)

    def test_missing_entry_and_wrong_name(self):
        self.write(".agents/plugins/marketplace.json", {"plugins": []})
        self.write("gemini-extension.json", {"name": "other", "version": "1.0.0"})
        errors = "\n".join(self.errors())
        self.assertIn(".agents/plugins/marketplace.json: no 'cerbos-skills' plugin entry", errors)
        self.assertIn("gemini-extension.json: name must be", errors)


if __name__ == "__main__":
    unittest.main()
