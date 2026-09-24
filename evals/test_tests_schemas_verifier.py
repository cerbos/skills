"""Schema coverage credits only denials that schema validation explains."""

import importlib.util
import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).parent / "tasks/cerbos-policy-tests-schemas/tests"
sys.path.insert(0, str(TESTS))
# Each task has its own contract module; drop another task's cached copy.
sys.modules.pop("contract", None)
spec = importlib.util.spec_from_file_location("schema_outputs", TESTS / "check_outputs.py")
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)
sys.path.remove(str(TESTS))


def employee(**attr):
    return {"id": "ana", "roles": ["employee"], "attr": {"department": "finance", **attr}}


def expense(owner="ana", drop=(), **attr):
    values = {"owner": owner, "department": "finance", "amount": 50, "status": "draft", **attr}
    for key in drop:
        values.pop(key)
    return {"kind": "expense", "id": "e", "attr": values}


class SchemaLabelTests(unittest.TestCase):
    def test_missing_attribute_denial_needs_a_policy_grant(self):
        self.assertEqual(
            verifier.labels(employee(), expense(drop=("amount",)), "view", ["view"]),
            {"missing-attribute-denied"},
        )
        # Someone else's expense is denied by policy anyway.
        self.assertEqual(
            verifier.labels(employee(), expense(owner="ben", drop=("amount",)), "view", ["view"]),
            set(),
        )

    def test_mixed_issues_are_not_isolated(self):
        resource = expense(drop=("amount",), tenant="acme")
        self.assertEqual(verifier.labels(employee(), resource, "view", ["view"]), set())

    def test_incomplete_create_only_counts_when_create_only(self):
        incomplete = {"kind": "expense", "id": "new", "attr": {"owner": "ana"}}
        self.assertEqual(
            verifier.labels(employee(), incomplete, "create", ["create"]),
            {"incomplete-create-allowed", "create-allowed"},
        )
        # With another action in the check, validation applies and denies create.
        self.assertEqual(
            verifier.labels(employee(), incomplete, "create", ["create", "view"]),
            {"missing-attribute-denied"},
        )

    def test_invalid_principal_with_valid_resource(self):
        self.assertEqual(
            verifier.labels(employee(department="legal"), expense(), "view", ["view"]),
            {"invalid-principal-denied"},
        )
        self.assertEqual(
            verifier.labels(employee(tenant="acme"), expense(), "view", ["view"]),
            {"invalid-principal-denied"},
        )


if __name__ == "__main__":
    unittest.main()
