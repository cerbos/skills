"""Role-policy coverage credits isolated, single-role evidence only."""

import importlib.util
import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).parent / "tasks/cerbos-policy-role-policies/tests"
sys.path.insert(0, str(TESTS))
# Each task has its own contract module; drop another task's cached copy.
sys.modules.pop("contract", None)
spec = importlib.util.spec_from_file_location("role_outputs", TESTS / "check_outputs.py")
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)
sys.path.remove(str(TESTS))


def principal(role, department="eng"):
    return {"id": "u", "roles": [role], "attr": {"department": department}}


def document(scope="acme", department="eng", **attr):
    resource = {"kind": "document", "id": "d", "attr": {"department": department, **attr}}
    if scope:
        resource["scope"] = scope
    return resource


class RoleLabelTests(unittest.TestCase):
    def test_contractor_inherits_acme_department_rule(self):
        editable = document(department="sales", contractor_editable=True)
        self.assertEqual(
            verifier.labels(principal("contractor"), editable, "edit"),
            {("acme", "contractor-edit-other-department-denied")},
        )

    def test_flag_labels_need_matching_department(self):
        self.assertEqual(
            verifier.labels(principal("contractor"), document(contractor_editable=True), "edit"),
            {("acme", "contractor-edit-flag-true")},
        )
        self.assertEqual(
            verifier.labels(principal("contractor"), document(department="sales"), "edit"),
            set(),
        )

    def test_editor_department_rule_is_scope_specific(self):
        other = principal("editor", "sales")
        self.assertEqual(
            verifier.labels(other, document(), "edit"),
            {("acme", "editor-other-department-edit-denied")},
        )
        self.assertEqual(
            verifier.labels(other, document(scope=None), "edit"),
            {("", "editor-other-department-edit")},
        )

    def test_multi_role_principals_are_ignored(self):
        both = {"id": "u", "roles": ["editor", "contractor"], "attr": {"department": "eng"}}
        self.assertEqual(verifier.labels(both, document(contractor_editable=True), "edit"), set())

    def test_unaffected_role_needs_a_base_grant(self):
        self.assertEqual(
            verifier.labels(principal("admin"), document(), "delete"),
            {("acme", "unaffected-role-base-permission")},
        )
        self.assertEqual(verifier.labels(principal("viewer"), document(), "edit"), set())


if __name__ == "__main__":
    unittest.main()
