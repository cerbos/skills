"""Regression tests for action-specific parent-role coverage classification."""

import runpy
import unittest
from pathlib import Path


relationship = runpy.run_path(
    str(Path(__file__).parent / "tasks/cerbos-policy-derived-roles/tests/check_outputs.py")
)["relationship"]


class ParentRoleCoverageTests(unittest.TestCase):
    def labels(self, roles, principal_id="alice", tenant="acme", department="engineering"):
        principal = {
            "id": principal_id,
            "roles": roles,
            "attr": {"tenant": tenant, "department": department},
        }
        resource = {
            "attr": {"owner": "alice", "tenant": "acme", "department": "engineering"}
        }
        return relationship(principal, resource)[2]

    def test_other_base_role_is_a_valid_owner_parent_negative(self):
        labels = self.labels(["reviewer"], department="sales")
        self.assertIn("wrong_owner_parent", labels)

    def test_other_base_role_is_a_valid_reviewer_parent_negative(self):
        labels = self.labels(["employee"], principal_id="bob")
        self.assertIn("wrong_reviewer_parent", labels)

    def test_unrelated_roles_can_cover_both_missing_parents(self):
        labels = self.labels(["auditor"])
        self.assertIn("wrong_owner_parent", labels)
        self.assertIn("wrong_reviewer_parent", labels)

    def test_present_parent_roles_do_not_count_as_missing(self):
        labels = self.labels(["employee", "reviewer"])
        self.assertNotIn("wrong_owner_parent", labels)
        self.assertNotIn("wrong_reviewer_parent", labels)

    def test_tenant_mismatch_cannot_prove_parent_gating(self):
        labels = self.labels(["auditor"], tenant="globex")
        self.assertNotIn("wrong_owner_parent", labels)
        self.assertNotIn("wrong_reviewer_parent", labels)

    def test_owner_mismatch_cannot_prove_owner_parent_gating(self):
        self.assertNotIn("wrong_owner_parent", self.labels(["reviewer"], principal_id="bob"))

    def test_department_mismatch_cannot_prove_reviewer_parent_gating(self):
        self.assertNotIn("wrong_reviewer_parent", self.labels(["employee"], department="sales"))

    def test_extra_roles_do_not_hide_action_specific_relationship_negatives(self):
        self.assertIn("nonowner", self.labels(["employee", "reviewer"], principal_id="bob"))
        self.assertIn("wrong_department", self.labels(["employee", "reviewer"], department="sales"))

    def test_matching_relationships_do_not_count_as_negatives(self):
        labels = self.labels(["employee", "reviewer"])
        self.assertNotIn("nonowner", labels)
        self.assertNotIn("wrong_department", labels)


if __name__ == "__main__":
    unittest.main()
