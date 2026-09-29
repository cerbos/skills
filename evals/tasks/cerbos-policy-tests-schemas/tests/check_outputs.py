"""Verify preserved rules, schema wiring, fixture styles, and active test coverage."""

import copy
import json
import sys
from pathlib import Path

import yaml

from contract import decide, policy_allows, principal_issues, resource_issues

ROOT = Path("/workspace/policies")
REPORT = Path("/logs/verifier/compile_normal.log")
SEED = Path("/tests/seed_policies.json")
POLICIES = {
    "expense": "resource_policies/finance/expense.yaml",
    "leave_request": "resource_policies/hr/leave_request.yaml",
}
SUITES = {
    "expense": "resource_policies/finance/expense_test.yaml",
    "leave_request": "resource_policies/hr/leave_request_test.yaml",
}
REQUIRED = {
    "owner-view",
    "other-view-denied",
    "manager-approve",
    "other-department-approve-denied",
    "create-allowed",
    "invalid-principal-denied",
    "missing-attribute-denied",
    "invalid-value-denied",
    "unknown-attribute-denied",
    "incomplete-create-allowed",
}
ISSUE_LABELS = {
    "missing": "missing-attribute-denied",
    "invalid-value": "invalid-value-denied",
    "unknown": "unknown-attribute-denied",
}


def read(path):
    value = yaml.safe_load(path.read_text())
    assert isinstance(value, dict), f"Expected mapping: {path}"
    return value


def policy(kind):
    return read(ROOT / POLICIES[kind])["resourcePolicy"]


def preservation():
    seed = json.loads(SEED.read_text())
    for kind in POLICIES:
        current = copy.deepcopy(policy(kind))
        current.pop("schemas", None)
        assert current == seed[kind], f"{POLICIES[kind]} changed beyond adding schemas"
    for path in ROOT.rglob("*"):
        assert not path.is_symlink(), f"Bundle must be self-contained: {path}"


def schemas():
    files = ["_schemas/principal.json"] + [f"_schemas/resources/{k}.json" for k in POLICIES]
    for relative in files:
        value = json.loads((ROOT / relative).read_text())
        assert isinstance(value, dict), f"Expected a JSON schema object: {relative}"
    for kind in POLICIES:
        block = policy(kind).get("schemas") or {}
        principal = block.get("principalSchema") or {}
        resource = block.get("resourceSchema") or {}
        assert principal.get("ref") == "cerbos:///principal.json", f"{kind}: principal schema ref"
        assert resource.get("ref") == f"cerbos:///resources/{kind}.json", f"{kind}: resource schema ref"
        ignored = set((resource.get("ignoreWhen") or {}).get("actions") or [])
        assert ignored == {"create"}, f"{kind}: resource validation must be skipped only for create"


def fixtures():
    finance = ROOT / "resource_policies/finance"
    for name in ("principals", "resources"):
        shared = read(finance / f"testdata/{name}.yaml").get(name)
        assert shared, f"finance/testdata/{name}.yaml must define {name}"
    suite = read(ROOT / SUITES["expense"])
    assert not suite.get("principals") and not suite.get("resources"), (
        "The finance suite must take fixtures from testdata only"
    )
    hr = ROOT / "resource_policies/hr"
    assert not (hr / "testdata").exists(), "The HR suite must not use a testdata directory"
    suite = read(ROOT / SUITES["leave_request"])
    assert suite.get("principals") and suite.get("resources"), (
        "The HR suite must define principals and resources inline"
    )


def labels(principal, resource, action, actions):
    roles = set(principal["roles"])
    p_bad = principal_issues(principal)
    r_bad = resource_issues(resource)
    create_only = all(a == "create" for a in actions)
    allowed = decide(principal, resource, actions)[0][action]
    found = set()
    # An employee create check counts whether or not the new record is complete.
    if roles == {"employee"} and action == "create" and not p_bad and (create_only or not r_bad):
        found.add("create-allowed")
    if not p_bad and not r_bad:
        attr = resource["attr"]
        own = attr.get("owner") == principal["id"]
        if roles == {"employee"} and action == "view":
            found.add("owner-view" if own else "other-view-denied")
        if roles == {"manager"} and action == "approve":
            found.add("manager-approve")
            if attr.get("department") != principal["attr"].get("department"):
                repaired = copy.deepcopy(resource)
                repaired["attr"]["department"] = principal["attr"].get("department")
                if policy_allows(principal, repaired, action):
                    found.add("other-department-approve-denied")
    elif p_bad and not r_bad and policy_allows(principal, resource, action):
        found.add("invalid-principal-denied")
    elif not p_bad and len(r_bad) == 1:
        (issue,) = r_bad
        if create_only and issue == "missing":
            found.add("incomplete-create-allowed")
        elif not create_only and policy_allows(principal, resource, action):
            found.add(ISSUE_LABELS[issue])
    return {label for label in found if label.endswith("-denied") != allowed}


def resolve(suite_path, suite):
    resolved = {}
    for name in ("principals", "resources"):
        shared_path = suite_path.parent / f"testdata/{name}.yaml"
        shared = read(shared_path).get(name, {}) if shared_path.exists() else {}
        resolved[name] = {**shared, **(suite.get(name) or {})}
    return resolved


def generated_tests():
    report = {s["file"]: s for s in json.loads(REPORT.read_text()).get("suites", [])}
    for kind, relative in SUITES.items():
        assert relative in report, f"Missing executed suite: {relative}"
        suite_path = ROOT / relative
        fixtures_ = resolve(suite_path, read(suite_path))
        coverage = set()
        for case in report[relative].get("testCases", []):
            for p_entry in case.get("principals", []):
                principal = fixtures_["principals"][p_entry["name"]]
                for r_entry in p_entry.get("resources", []):
                    resource = fixtures_["resources"][r_entry["name"]]
                    if resource.get("kind") != kind:
                        continue
                    actions = [a["name"] for a in r_entry.get("actions", [])]
                    expected = decide(principal, resource, actions)[0]
                    for action in r_entry.get("actions", []):
                        details = action["details"]
                        if details["result"] != "RESULT_PASSED":
                            continue
                        effect = "EFFECT_ALLOW" if expected[action["name"]] else "EFFECT_DENY"
                        assert details["success"]["effect"] == effect, (
                            "Native test expectation contradicts contract: "
                            f"{relative} {case['name']} {p_entry['name']} {r_entry['name']} {action['name']}"
                        )
                        coverage |= labels(principal, resource, action["name"], actions)
        missing = sorted(REQUIRED - coverage)
        assert not missing, f"{relative}: missing active test coverage {missing}"


if __name__ == "__main__":
    {
        "preservation": preservation,
        "schemas": schemas,
        "fixtures": fixtures,
        "generated_tests": generated_tests,
    }[sys.argv[1]]()
    print(f"PASS: {sys.argv[1]}")
