import importlib.util
import json
import sys
import tempfile
import textwrap
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import yaml

SCRIPT = Path(__file__).resolve().parent.parent / "skills" / "cerbos-policy" / "scripts" / "coverage_audit.py"


def load_audit(with_pyyaml):
    """Import coverage_audit.py, optionally as if PyYAML were not installed."""
    blocked = {} if with_pyyaml else {"yaml": None}
    with patch.dict(sys.modules, blocked):
        spec = importlib.util.spec_from_file_location("coverage_audit", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


audit_pyyaml = load_audit(with_pyyaml=True)
audit_stdlib = load_audit(with_pyyaml=False)

PRINCIPALS = """\
# yaml-language-server: $schema=https://api.cerbos.dev/latest/cerbos/policy/v1/TestFixture/Principals.schema.json
principals:
  alice_employee:
    id: alice
    roles: [employee]  # base role
    attr: {department: "finance", tenant: acme}
  alice_reviewer_only:
    id: alice
    roles:
    - reviewer
    attr:
      department: finance
      tenant: acme
"""

SUITE = """\
---
name: DocumentSuite
description: >
  Checks owner edits, and that someone else's roles
  do not grant them.
principals:
  bob_outsider:
    id: bob
    roles: ['employee']
    attr:
      department: 'sales'
      tenant: "acme"
resources:
  document_owned_by_alice:
    kind: document
    id: doc1
    attr:
      owner: alice
      tenant: acme
      created: 2024-01-01
      limit: 1_000
      ratio: 0.5
      archived: no
      notes: |
        first line
        second line
tests:
  - name: owner edits
    input:
      principals: [alice_employee, alice_reviewer_only]
      resources: [document_owned_by_alice]
      actions: [edit]
    expected:
      - principal: alice_employee
        resource: document_owned_by_alice
        actions: {edit: EFFECT_ALLOW}
"""


def report(assertions, overall="RESULT_PASSED"):
    """Build a `cerbos compile --output=json` report from (principal, resource, action, effect)."""
    principals = {}
    for principal, resource, action, effect in assertions:
        principals.setdefault(principal, {}).setdefault(resource, []).append(
            {"name": action, "details": {"result": "RESULT_PASSED", "success": {"effect": effect}}}
        )
    return {
        "suites": [{
            "file": "document_test.yaml",
            "name": "DocumentSuite",
            "testCases": [{
                "name": "owner edits",
                "principals": [
                    {"name": p, "resources": [{"name": r, "actions": a} for r, a in rs.items()]}
                    for p, rs in principals.items()
                ],
            }],
        }],
        "summary": {"overallResult": overall},
    }


PLAN = {
    "paths": [{"id": "document-owner", "kind": "document", "requires": ["parent-role"]}],
    "rows": [
        {"id": "owner-edit", "principal": "alice_employee", "resource": "document_owned_by_alice",
         "action": "edit", "effect": "EFFECT_ALLOW", "facts": {"resource.attr.created": "2024-01-01"}},
        {"id": "missing-parent-role", "principal": "alice_reviewer_only", "resource": "document_owned_by_alice",
         "action": "edit", "effect": "EFFECT_DENY", "control": "owner-edit", "change": "principal.roles",
         "path": "document-owner", "prerequisite": "parent-role"},
    ],
}

ASSERTIONS = [
    ("alice_employee", "document_owned_by_alice", "edit", "EFFECT_ALLOW"),
    ("alice_reviewer_only", "document_owned_by_alice", "edit", "EFFECT_DENY"),
]


class SubsetReaderTest(unittest.TestCase):
    def assertReadsLikePyYAML(self, text):
        expected = yaml.load(text, Loader=audit_pyyaml._Loader)
        self.assertEqual(audit_stdlib.SubsetReader(text, "test.yaml").document(), expected)

    def test_fixture_and_suite_files(self):
        self.assertReadsLikePyYAML(PRINCIPALS)
        self.assertReadsLikePyYAML(SUITE)

    def test_scalars_and_layouts(self):
        self.assertReadsLikePyYAML(textwrap.dedent("""\
            a: ~
            b: -3
            c: 1e3
            d: "tab\\tquote\\" \\u00e9"
            e: 'it''s'
            f: http://example.com/x#frag
            g: value # comment
            h: [1, "two", {three: 3, four: [4]}, ]
            i: {k: v,
                l: [x, y]}
            j:
              - - nested
                - - key: deeper
              - key: value
                other:
                - deep
            k: long plain scalar that
              wraps onto a second line
            l: |-
              kept
                indented
            m: >+
              folded
              text

            n: ""
            """))

    def test_dates_stay_strings(self):
        self.assertEqual(audit_stdlib.SubsetReader("d: 2024-01-01\n", "t").document(), {"d": "2024-01-01"})
        self.assertEqual(yaml.load("d: 2024-01-01\n", Loader=audit_pyyaml._Loader), {"d": "2024-01-01"})

    def test_unsupported_yaml_is_reported(self):
        for text in ("a: &x 1\nb: *x\n", "a: !!str 1\n", "base: {}\n<<: {a: 1}\n", "a: 1\n---\nb: 2\n"):
            with self.subTest(text=text), self.assertRaises(audit_stdlib.Unreadable):
                audit_stdlib.SubsetReader(text, "t").document()


class AuditTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "policies" / "testdata").mkdir(parents=True)
        (self.root / "policies" / "testdata" / "principals.yaml").write_text(PRINCIPALS)
        (self.root / "policies" / "document_test.yaml").write_text(SUITE)

    def tearDown(self):
        self.tmp.cleanup()

    def run_audit(self, module, plan=PLAN, assertions=ASSERTIONS):
        plan_path = self.root / "coverage-plan.json"
        plan_path.write_text(plan if isinstance(plan, str) else json.dumps(plan))
        report_path = self.root / "normal.json"
        report_path.write_text(json.dumps(report(assertions)))
        args = Namespace(policies=str(self.root / "policies"), plan=str(plan_path), report=[str(report_path)])
        errors, passes = module.audit(args)
        return errors, "\n".join(passes)

    def test_passes_with_and_without_pyyaml(self):
        for module in (audit_pyyaml, audit_stdlib):
            with self.subTest(pyyaml=module.yaml is not None):
                errors, out = self.run_audit(module)
                self.assertEqual(errors, [])
                self.assertIn("principal.roles ['employee'] -> ['reviewer']", out)
                self.assertIn("PASS path document-owner (document) prerequisite parent-role", out)

    def test_missing_assertion_and_confounded_control_fail(self):
        for module in (audit_pyyaml, audit_stdlib):
            with self.subTest(pyyaml=module.yaml is not None):
                errors, _ = self.run_audit(module, assertions=ASSERTIONS[:1])
                self.assertTrue(any("no passing EFFECT_DENY assertion" in e for e in errors))
                self.assertTrue(any("prerequisite parent-role: no passing isolated row" in e for e in errors))

                plan = json.loads(json.dumps(PLAN))
                plan["rows"][1]["principal"] = "bob_outsider"
                errors, _ = self.run_audit(module, plan, [ASSERTIONS[0], ("bob_outsider",) + ASSERTIONS[1][1:]])
                self.assertTrue(any("expected only principal.roles to differ" in e for e in errors))

    def test_unknown_field_path_is_rejected(self):
        plan = json.loads(json.dumps(PLAN))
        plan["rows"][0]["facts"] = {"scope": "acme"}
        errors, _ = self.run_audit(audit_stdlib, plan)
        self.assertEqual(len(errors), 1)
        self.assertIn("unknown field path 'scope'", errors[0])

    def test_scoped_rules_need_a_boundary_row(self):
        (self.root / "policies" / "emea.yaml").write_text(textwrap.dedent("""\
            apiVersion: api.cerbos.dev/v1
            resourcePolicy:
              resource: document
              version: default
              scope: emea
              rules:
                - actions: [edit]
                  roles: [employee]
                  effect: EFFECT_DENY
            """))
        suite = self.root / "policies" / "document_test.yaml"
        suite.write_text(SUITE.replace(
            "tests:",
            "  document_in_emea:\n    kind: document\n    id: doc2\n    scope: emea\n"
            "    attr: {owner: alice, tenant: acme, created: 2024-01-01, limit: 1_000, ratio: 0.5,"
            " archived: no, notes: \"first line\\nsecond line\\n\"}\ntests:",
        ))
        union_exempt = {**PLAN, "roleUnionExemption": {"reason": "single-role bundle"}}
        errors, _ = self.run_audit(audit_stdlib, union_exempt)
        self.assertEqual(len(errors), 1)
        self.assertIn("FAIL scope emea (document, role employee) vs the unscoped base", errors[0])

        plan = json.loads(json.dumps(union_exempt))
        plan["rows"].append({"id": "emea-edit", "principal": "alice_employee", "resource": "document_in_emea",
                             "action": "edit", "effect": "EFFECT_DENY", "control": "owner-edit",
                             "change": "resource.scope"})
        assertions = ASSERTIONS + [("alice_employee", "document_in_emea", "edit", "EFFECT_DENY")]
        errors, out = self.run_audit(audit_stdlib, plan, assertions)
        self.assertEqual(errors, [])
        self.assertIn("PASS scope emea (document, role employee) vs the unscoped base: emea-edit", out)

        plan = json.loads(json.dumps(union_exempt))
        plan["scopeExemptions"] = [{"scope": "emea", "role": "employee", "reason": "restates the parent"}]
        errors, out = self.run_audit(audit_stdlib, plan)
        self.assertEqual(errors, [])
        self.assertIn("NOTE scope emea (document, role employee) vs the unscoped base: exempted", out)

        # A descendant with its own policy inherits the rule, and a sibling branch replaces the base.
        for name, scope in (("emea_de.yaml", "emea.de"), ("apac.yaml", "apac")):
            (self.root / "policies" / name).write_text(
                f"apiVersion: api.cerbos.dev/v1\nresourcePolicy:\n  resource: document\n"
                f"  version: default\n  scope: {scope}\n  rules: []\n"
            )
        errors, _ = self.run_audit(audit_stdlib, union_exempt)
        self.assertEqual(
            sorted(e.split(":")[0] for e in errors),
            ["FAIL scope emea (document, role employee) vs `apac`",
             "FAIL scope emea.de (document, role employee) vs `apac`"],
        )

    def test_scoped_role_rules_need_a_role_union_row(self):
        (self.root / "policies" / "emea.yaml").write_text(
            "apiVersion: api.cerbos.dev/v1\nresourcePolicy:\n  resource: document\n  version: default\n"
            "  scope: emea\n  rules: []\n"
        )
        (self.root / "policies" / "emea_roles.yaml").write_text(
            "apiVersion: api.cerbos.dev/v1\nrolePolicy:\n  role: employee\n  scope: emea\n"
            "  rules:\n    - resource: document\n      allowActions: [view]\n"
        )
        plan = json.loads(json.dumps(PLAN))
        plan["scopeExemptions"] = [{"scope": "emea", "role": "employee", "reason": "boundary tested elsewhere"}]
        errors, _ = self.run_audit(audit_stdlib, plan)
        self.assertEqual([e.split(":")[0] for e in errors], ["FAIL role union"])

        # alice_both holds employee and reviewer; reviewer alone (alice_reviewer_only) is denied.
        (self.root / "policies" / "testdata" / "principals.yaml").write_text(
            PRINCIPALS + "  alice_both:\n    id: alice\n    roles: [employee, reviewer]\n"
            "    attr: {department: finance, tenant: acme}\n"
        )
        plan["rows"].append({"id": "both-edit", "principal": "alice_both", "resource": "document_owned_by_alice",
                             "action": "edit", "effect": "EFFECT_ALLOW", "control": "missing-parent-role",
                             "change": "principal.roles"})
        assertions = ASSERTIONS + [("alice_both", "document_owned_by_alice", "edit", "EFFECT_ALLOW")]
        errors, out = self.run_audit(audit_stdlib, plan, assertions)
        self.assertEqual(errors, [])
        self.assertIn("PASS role union: both-edit", out)

    def test_unread_principal_id_does_not_confound_a_control(self):
        (self.root / "policies" / "testdata" / "principals.yaml").write_text(
            PRINCIPALS.replace("  alice_reviewer_only:\n    id: alice", "  alice_reviewer_only:\n    id: someone-else")
        )
        errors, out = self.run_audit(audit_stdlib)
        self.assertEqual(errors, [])
        (self.root / "policies" / "owner.yaml").write_text("rule: R.attr.owner == P.id\n")
        errors, _ = self.run_audit(audit_stdlib)
        self.assertTrue(any("expected only principal.roles to differ" in e for e in errors))

    def test_compile_digest_lists_failures_and_compile_errors(self):
        failing = {"suites": [{"file": "d_test.yaml", "testCases": [{"name": "t", "principals": [{"name": "u",
                   "resources": [{"name": "d", "actions": [
                       {"name": "view", "details": {"result": "RESULT_PASSED", "success": {"effect": "EFFECT_ALLOW"}}},
                       {"name": "edit", "details": {"result": "RESULT_FAILED",
                                                    "failure": {"expected": "EFFECT_ALLOW", "actual": "EFFECT_DENY"}}},
                   ]}]}]}]}], "summary": {"overallResult": "RESULT_FAILED"}}
        lines, compiled = audit_stdlib.compile_digest("normal.json", json.dumps(failing))
        self.assertTrue(compiled)
        self.assertEqual(lines, ["TEST normal.json: d_test.yaml :: t :: u / d / edit: expected EFFECT_ALLOW got EFFECT_DENY"])
        broken = {"lintErrors": {"load_failures": [{"file": "doc.yaml", "error": "invalid enum value"}]}}
        lines, compiled = audit_stdlib.compile_digest("normal.json", json.dumps(broken))
        self.assertFalse(compiled)
        self.assertEqual(lines, ["COMPILE normal.json: doc.yaml: invalid enum value"])

    def test_non_json_plan_is_unreadable(self):
        with self.assertRaises(audit_stdlib.Unreadable):
            self.run_audit(audit_stdlib, plan="rows:\n  - id: owner-edit\n")


if __name__ == "__main__":
    unittest.main()
