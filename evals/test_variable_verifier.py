"""Coverage may prove optional defaults in separate executed requests."""

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml


spec = importlib.util.spec_from_file_location(
    "variable_outputs",
    Path(__file__).parent / "tasks/cerbos-policy-variables/tests/check_outputs.py",
)
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


class OptionalDefaultCoverageTests(unittest.TestCase):
    def check_coverage(self, omitted=None, denied=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            suites = []
            for kind, limit in (("invoice", 1000), ("expense", 250)):
                principal = {
                    "id": "alice", "roles": ["accountant"],
                    "attr": {"tenant": "acme", "suspended": False, "approval_limit": limit},
                }
                resource = {
                    "id": "record", "kind": kind,
                    "attr": {"tenant": "acme", "owner": "bob", "status": "pending",
                             "amount": limit, "blocked": False},
                }
                cases = []

                def case(name, changes, allow):
                    p, r = copy.deepcopy(principal), copy.deepcopy(resource)
                    for target, key, value in changes:
                        attr = (p if target == "p" else r)["attr"]
                        if value is None:
                            attr.pop(key)
                        else:
                            attr[key] = value
                    cases.append((name, p, r, allow))

                case("boundary", [], True)
                case("over", [("r", "amount", limit + 1)], False)
                case("tenant", [("p", "tenant", "globex")], False)
                case("owner", [("r", "owner", "alice")], False)
                case("blocked", [("r", "blocked", True)], False)
                case("suspended", [("p", "suspended", True)], False)
                case("override", [("p", "approval_limit", limit + 1), ("r", "amount", limit + 1)], True)
                for name, target in (("suspended", "p"), ("approval_limit", "p"), ("blocked", "r")):
                    if name == omitted:
                        continue
                    changes = [(target, name, None)]
                    if denied:
                        changes.append(("r", "status", "approved"))
                    case(f"absent_{name}", changes, not denied)

                definition = {"principals": {}, "resources": {}}
                executed = []
                for name, p, r, allow in cases:
                    definition["principals"][name] = p
                    definition["resources"][name] = r
                    executed.append({"name": name, "principals": [{"name": name, "resources": [{
                        "name": name, "actions": [{"name": "approve", "details": {
                            "result": "RESULT_PASSED",
                            "success": {"effect": "EFFECT_ALLOW" if allow else "EFFECT_DENY"},
                        }}],
                    }]}]})
                filename = f"{kind}_test.yaml"
                (root / filename).write_text(yaml.safe_dump(definition))
                suites.append({"file": filename, "testCases": executed})
            report = root / "report.json"
            report.write_text(json.dumps({"suites": suites}))
            with patch.object(verifier, "ROOT", root), patch.object(verifier, "Path", return_value=report):
                verifier.generated_tests()

    def test_distributed_absence_covers_all_defaults(self):
        self.check_coverage()

    def test_every_missing_default_still_fails(self):
        for name in ("suspended", "approval_limit", "blocked"):
            with self.subTest(name=name), self.assertRaisesRegex(AssertionError, f"absent_{name}"):
                self.check_coverage(omitted=name)

    def test_unrelated_denials_cannot_prove_safe_defaults(self):
        with self.assertRaisesRegex(AssertionError, "absent_"):
            self.check_coverage(denied=True)


if __name__ == "__main__":
    unittest.main()
