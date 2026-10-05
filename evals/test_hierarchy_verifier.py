"""Hierarchy coverage credits isolated evidence only."""

import importlib.util
import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).parent / "tasks/cerbos-policy-hierarchy/tests"
sys.path.insert(0, str(TESTS))
# Each task has its own contract module; drop another task's cached copy.
sys.modules.pop("contract", None)
spec = importlib.util.spec_from_file_location("hierarchy_outputs", TESTS / "check_outputs.py")
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)
sys.path.remove(str(TESTS))


def principal(*roles, region="eu"):
    return {"id": "sam", "roles": list(roles), "attr": {"region": region}}


def report(scope, status="published", **attr):
    return {"kind": "report", "id": "r", "scope": scope, "attr": {"status": status, **attr}}


class HierarchyLabelTests(unittest.TestCase):
    def test_eu_region_denial_is_isolated(self):
        labels = verifier.labels(principal("editor", region="us"), report("acme.eu", "draft"), "edit")
        self.assertEqual(labels, {("acme.eu", "region-denied")})

    def test_region_confounds_other_eu_denials(self):
        visible = report("acme.eu", contractor_visible=True)
        self.assertEqual(verifier.labels(principal("contractor", region="us"), visible, "view"), set())
        self.assertEqual(verifier.labels(principal("editor", region="us"), report("acme.eu"), "edit"), set())

    def test_acme_draft_restriction_needs_editor_only(self):
        self.assertIn(
            ("acme", "editor-edit-nondraft-denied"),
            verifier.labels(principal("editor"), report("acme"), "edit"),
        )
        self.assertNotIn(
            ("acme", "editor-edit-nondraft-denied"),
            verifier.labels(principal("editor", "admin"), report("acme"), "edit"),
        )

    def test_multirole_requires_a_union(self):
        self.assertIn(
            ("*", "multirole"),
            verifier.labels(principal("editor", "admin"), report("acme"), "edit"),
        )
        self.assertIn(
            ("*", "multirole"),
            verifier.labels(principal("editor", "contractor"), report("globex"), "edit"),
        )
        # Both roles allow viewing, so the request does not show a union.
        self.assertNotIn(
            ("*", "multirole"),
            verifier.labels(principal("viewer", "editor"), report(""), "view"),
        )

    def test_any_base_grant_counts_as_inherited(self):
        self.assertIn(
            ("acme.eu", "inherited"),
            verifier.labels(principal("admin"), report("acme.eu"), "view"),
        )
        self.assertNotIn(
            ("globex", "inherited"),
            verifier.labels(principal("contractor"), report("globex", contractor_visible=True), "view"),
        )

    def test_contractor_denial_counts_in_any_non_globex_scope(self):
        visible = report("acme", contractor_visible=True)
        self.assertIn(
            ("outside-globex", "contractor-visible-denied"),
            verifier.labels(principal("contractor"), visible, "view"),
        )

    def test_absent_and_false_flags_are_distinct(self):
        self.assertIn(
            ("globex", "contractor-absent-denied"),
            verifier.labels(principal("contractor"), report("globex"), "view"),
        )
        self.assertNotIn(
            ("globex", "contractor-absent-denied"),
            verifier.labels(principal("contractor"), report("globex", contractor_visible=False), "view"),
        )

    def test_default_scope_option_resolves(self):
        resource = {"kind": "report", "attr": {}}
        self.assertEqual(
            verifier.resolve_scope(resource, {"options": {"defaultScope": "globex"}}, {}), "globex"
        )
        self.assertEqual(verifier.resolve_scope(resource, None, {}), "")


if __name__ == "__main__":
    unittest.main()
