"""Repair checks accept equivalent fixes while rejecting weakened or strict-only tests."""

import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

TASK = Path(__file__).parent / "tasks/cerbos-policy-repair"
TESTS = TASK / "tests"
sys.path.insert(0, str(TESTS))
# Each task has its own contract module; drop another task's cached copy.
sys.modules.pop("contract", None)
spec = importlib.util.spec_from_file_location("repair_outputs", TESTS / "check_outputs.py")
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)
sys.path.remove(str(TESTS))
sys.modules.pop("contract", None)

POLICY = "resource_policies/document.yaml"
SUITE = "resource_policies/document_test.yaml"
RESOURCES = "resource_policies/testdata/resources.yaml"


def passing_report(root):
    """Build a compile report in which every asserted decision executed and passed."""
    report = {"suites": []}
    for file, suite, _, _ in verifier.suites(root):
        cases = []
        for test in suite.get("tests") or []:
            effects = {}
            for entry in test.get("expected") or []:
                for action, effect in entry["actions"].items():
                    effects[(entry["principal"], entry["resource"], action)] = effect
            data = test["input"]
            principals = [
                {
                    "name": p,
                    "resources": [
                        {
                            "name": r,
                            "actions": [
                                {
                                    "name": a,
                                    "details": {
                                        "result": "RESULT_PASSED",
                                        "success": {"effect": effects.get((p, r, a), "EFFECT_DENY")},
                                    },
                                }
                                for a in data["actions"]
                            ],
                        }
                        for r in data["resources"]
                    ],
                }
                for p in data["principals"]
            ]
            cases.append({"name": test["name"], "principals": principals})
        report["suites"].append({"file": file, "testCases": cases})
    return report


class RepairVerifierTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name) / "policies"
        shutil.copytree(TASK / "solution/policies", self.root)
        self.saved = verifier.ROOT, verifier.TESTS, verifier.REPORT
        verifier.ROOT, verifier.TESTS = self.root, TESTS
        verifier.REPORT = Path(self.directory.name) / "compile_normal.log"

    def tearDown(self):
        verifier.ROOT, verifier.TESTS, verifier.REPORT = self.saved
        self.directory.cleanup()

    def edit(self, relative, old, new):
        path = self.root / relative
        text = path.read_text()
        self.assertIn(old, text)
        path.write_text(text.replace(old, new))

    def generated_tests(self):
        verifier.REPORT.write_text(json.dumps(passing_report(self.root)))
        verifier.generated_tests()

    def test_reference_solution_passes(self):
        verifier.preservation()
        self.generated_tests()

    def test_equivalent_repairs_are_accepted(self):
        # Renaming the definition instead of the reference, and a De Morgan guard.
        self.edit("derived_roles/document_roles.yaml", "name: document_owner", "name: owner")
        self.edit(POLICY, '["document_owner"]', '["owner"]')
        self.edit(
            POLICY,
            "'!has(R.attr.classification) || R.attr.classification != \"public\"'",
            "'!(has(R.attr.classification) && R.attr.classification == \"public\")'",
        )
        verifier.preservation()

    def test_changed_seed_fixture_is_rejected(self):
        self.edit(RESOURCES, "size_mb: 25", "size_mb: 24")
        with self.assertRaisesRegex(AssertionError, "employee download size limit"):
            verifier.preservation()

    def test_skipped_seed_test_is_rejected(self):
        self.edit(SUITE, "  - name: owner edits own document\n", "  - name: owner edits own document\n    skip: true\n")
        with self.assertRaisesRegex(AssertionError, "owner edits own document"):
            verifier.preservation()

    def test_implicit_deny_counts_as_an_unchanged_expectation(self):
        # Dropping an explicit DENY entry keeps the same expectation.
        self.edit(
            SUITE,
            "      - principal: eli\n        resource: erin_notes\n        actions:\n          edit: EFFECT_DENY\n",
            "",
        )
        verifier.preservation()

    def test_changed_intact_rule_is_rejected(self):
        self.edit(POLICY, 'roles: ["manager"]\n\n    - name: deny', 'roles: ["manager", "employee"]\n\n    - name: deny')
        with self.assertRaisesRegex(AssertionError, "delete-documents"):
            verifier.preservation()

    def test_deny_rule_cannot_become_an_allow(self):
        self.edit(POLICY, "effect: EFFECT_DENY", "effect: EFFECT_ALLOW")
        with self.assertRaisesRegex(AssertionError, "deny-contractor-non-public"):
            verifier.preservation()

    def test_strict_only_regression_test_is_not_credited(self):
        self.edit(SUITE, "tests:\n", "options:\n  strictEvaluation: true\ntests:\n")
        with self.assertRaisesRegex(AssertionError, "unclassified-contractor-view-deny"):
            self.generated_tests()

    def test_missing_regression_test_is_rejected(self):
        suite = yaml.safe_load((self.root / SUITE).read_text())
        suite["tests"] = [t for t in suite["tests"] if "unclassified" not in t["name"]]
        (self.root / SUITE).write_text(yaml.safe_dump(suite, sort_keys=False))
        with self.assertRaisesRegex(AssertionError, "unclassified-contractor-view-deny"):
            self.generated_tests()

    def test_labels_need_an_absent_classification(self):
        contractor = {"id": "c", "roles": ["contractor"], "attr": {}}
        absent = {"kind": "document", "attr": {"owner": "x", "size_mb": 1}}
        internal = {"kind": "document", "attr": {"owner": "x", "size_mb": 1, "classification": "internal"}}
        self.assertEqual(
            verifier.labels(contractor, absent, "view", "EFFECT_DENY"), {"unclassified-contractor-view-deny"}
        )
        self.assertEqual(verifier.labels(contractor, internal, "view", "EFFECT_DENY"), set())

    def test_contract_combines_roles_like_cerbos(self):
        # A role-scoped DENY does not remove another role's ALLOW (observed on 0.55.0).
        both = {"id": "b", "roles": ["employee", "contractor"], "attr": {}}
        internal = {"kind": "document", "attr": {"owner": "x", "size_mb": 1, "classification": "internal"}}
        self.assertTrue(verifier.decide(both, internal, "view"))


if __name__ == "__main__":
    unittest.main()
