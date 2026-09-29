"""Verify preserved rules, the new flag rule, and asserted output coverage."""

import copy
import json
import sys
from pathlib import Path

import yaml

from contract import SRC, decide

ROOT = Path("/workspace/policies")
REPORT = Path("/logs/verifier/compile_normal.log")
SEED = Path("/tests/seed_policy.json")
POLICY = "resource_policies/payout.yaml"
SUITE = "resource_policies/payout_test.yaml"
# The instruction's "within the limit, including an amount equal to the limit"
# is satisfied by an at-limit case alone.
REQUIRED = {
    "approved-at-limit",
    "over-limit",
    "frozen-otherwise-approvable",
    "flag-normal-at-10000-clerk",
    "flag-normal-at-10000-manager",
    "flag-high-clerk",
    "flag-high-manager",
    "flag-frozen",
}


def read(path):
    value = yaml.safe_load(path.read_text())
    assert isinstance(value, dict), f"Expected mapping: {path}"
    return value


def preservation():
    seed = json.loads(SEED.read_text())
    policy = read(ROOT / POLICY)["resourcePolicy"]
    rules = {rule.get("name"): rule for rule in policy.get("rules", [])}
    assert len(rules) == len(policy.get("rules", [])), "Rule names must be unique"
    expected_names = {rule["name"] for rule in seed["rules"]} | {"flag-payouts"}
    assert set(rules) == expected_names, f"Expected rules {sorted(expected_names)}"
    for rule in seed["rules"]:
        current = copy.deepcopy(rules[rule["name"]])
        current.pop("output", None)
        assert current == rule, f"Rule {rule['name']} changed beyond adding an output"
    flag = rules["flag-payouts"]
    assert flag.get("actions") == ["flag"], "flag-payouts must cover only flag"
    assert set(flag.get("roles", [])) == {"clerk", "manager"}, "flag-payouts roles"
    assert flag.get("effect") == "EFFECT_ALLOW", "flag-payouts must allow"
    # A condition is allowed; pdp_decisions checks that it preserves behaviour.
    # Attribute schemas may be added; nothing else in the header may change.
    rest = {k: v for k, v in policy.items() if k not in {"rules", "schemas"}}
    assert rest == {k: v for k, v in seed.items() if k != "rules"}, "Policy header changed"
    for path in ROOT.rglob("*"):
        assert not path.is_symlink(), f"Bundle must be self-contained: {path}"


def listed(entry, singular):
    values = entry.get(singular + "s") or []
    return values + ([entry[singular]] if entry.get(singular) else [])


def labels(principal, resource, action, src, value):
    roles = set(principal["roles"])
    attr = resource["attr"]
    found = set()
    if src == SRC + "approve-within-limit" and action == "approve":
        limit = principal["attr"]["approval_limit"]
        if value.get("event") == "payout_approved":
            found.add("approved-at-limit" if attr["amount"] == limit else "approved-below-limit")
        elif value.get("reason") == "over_limit":
            found.add("over-limit")
    if src == SRC + "block-frozen-accounts":
        if action == "approve" and "manager" in roles and attr["amount"] <= principal["attr"]["approval_limit"]:
            found.add("frozen-otherwise-approvable")
        if action == "flag" and roles & {"clerk", "manager"}:
            found.add("flag-frozen")
    if src == SRC + "flag-payouts" and action == "flag" and len(roles) == 1:
        (role,) = roles
        if attr["amount"] == 10000 and value.get("priority") == "normal":
            found.add(f"flag-normal-at-10000-{role}")
        if attr["amount"] > 10000 and value.get("priority") == "high":
            found.add(f"flag-high-{role}")
    return found


def generated_tests():
    report = {s["file"]: s for s in json.loads(REPORT.read_text()).get("suites", [])}
    assert SUITE in report, f"Missing executed suite: {SUITE}"
    suite = read(ROOT / SUITE)
    fixtures = {}
    for name in ("principals", "resources"):
        shared = read(ROOT / f"resource_policies/testdata/{name}.yaml").get(name, {})
        fixtures[name] = {**shared, **(suite.get(name) or {})}
    passed = set()
    for case in report[SUITE].get("testCases", []):
        for p_entry in case.get("principals", []):
            principal = fixtures["principals"][p_entry["name"]]
            for r_entry in p_entry.get("resources", []):
                resource = fixtures["resources"][r_entry["name"]]
                for action in r_entry.get("actions", []):
                    details = action["details"]
                    if details["result"] != "RESULT_PASSED" or resource.get("kind") != "payout":
                        continue
                    allowed, _ = decide(principal, resource, action["name"])
                    effect = "EFFECT_ALLOW" if allowed else "EFFECT_DENY"
                    assert details["success"]["effect"] == effect, (
                        f"Native test expectation contradicts contract: {case['name']} {action['name']}"
                    )
                    passed.add((case["name"], p_entry["name"], r_entry["name"], action["name"]))
    coverage = set()
    for test in suite.get("tests", []):
        for entry in test.get("expected", []):
            for p_name in listed(entry, "principal"):
                for r_name in listed(entry, "resource"):
                    principal = fixtures["principals"][p_name]
                    resource = fixtures["resources"][r_name]
                    for block in entry.get("outputs") or []:
                        action = block.get("action")
                        if (test.get("name"), p_name, r_name, action) not in passed:
                            continue
                        _, outputs = decide(principal, resource, action)
                        for item in block.get("expected") or []:
                            asserted = (item.get("src"), item.get("val"))
                            assert asserted in outputs, (
                                f"Asserted output contradicts contract: {test.get('name')} {asserted}"
                            )
                            coverage |= labels(principal, resource, action, *asserted)
    missing = sorted(REQUIRED - coverage)
    assert not missing, f"Missing asserted output coverage: {missing}"


if __name__ == "__main__":
    {"preservation": preservation, "generated_tests": generated_tests}[sys.argv[1]]()
    print(f"PASS: {sys.argv[1]}")
