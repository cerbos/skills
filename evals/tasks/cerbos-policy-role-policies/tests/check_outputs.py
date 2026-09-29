"""Verify preserved base policies, role-policy layout, and active test coverage."""

import copy
import hashlib
import json
import sys
from pathlib import Path

import yaml

from contract import allows

ROOT = Path("/workspace/policies")
REPORT = Path("/logs/verifier/compile_normal.log")
PRESERVED = Path("/tests/preserved.json")
SUITE = "role_policies/acme/acme_roles_test.yaml"
ROLE_POLICIES = {
    f"role_policies/acme/{role}.yaml": role for role in ("contractor", "auditor", "editor")
}
POLICY_KEYS = {
    "resourcePolicy",
    "rolePolicy",
    "principalPolicy",
    "derivedRoles",
    "exportVariables",
    "exportConstants",
}
REQUIRED = {
    ("acme", "contractor-view"),
    ("acme", "contractor-edit-flag-true"),
    ("acme", "contractor-edit-flag-false-denied"),
    ("acme", "contractor-edit-flag-absent-denied"),
    ("acme", "contractor-edit-other-department-denied"),
    ("acme", "contractor-invoice-denied"),
    ("acme", "contractor-delete-denied"),
    ("acme", "auditor-document-view"),
    ("acme", "auditor-invoice-view"),
    ("acme", "auditor-invoice-approve-denied"),
    ("acme", "auditor-document-edit-denied"),
    ("acme", "editor-own-department-edit"),
    ("acme", "editor-other-department-edit-denied"),
    ("", "editor-other-department-edit"),
    ("", "contractor-denied"),
    ("", "auditor-denied"),
    ("acme", "unaffected-role-base-permission"),
}


def read(path):
    value = yaml.safe_load(path.read_text())
    assert isinstance(value, dict), f"Expected mapping: {path}"
    return value


def architecture():
    for name, digest in json.loads(PRESERVED.read_text()).items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, (
            f"Base policy changed: {name}"
        )
    policies = {}
    for path in ROOT.rglob("*"):
        assert not path.is_symlink(), f"Bundle must be self-contained: {path}"
        if path.is_file() and path.suffix in {".yaml", ".yml"}:
            value = read(path)
            if set(value) & POLICY_KEYS:
                policies[path.relative_to(ROOT).as_posix()] = value
    expected = set(json.loads(PRESERVED.read_text())) | set(ROLE_POLICIES)
    assert set(policies) == expected, (
        f"Expected base policies and Acme role policies only, found {sorted(policies)}"
    )
    for relative, role in ROLE_POLICIES.items():
        policy = policies[relative].get("rolePolicy")
        assert isinstance(policy, dict), f"{relative} must be a role policy"
        assert policy.get("role") == role, f"{relative}: role must be {role}"
        assert policy.get("scope") == "acme", f"{relative}: scope must be acme"
        assert policy.get("version", "default") == "default", f"{relative}: version"
        assert policy.get("rules"), f"{relative}: rules required"


def labels(principal, resource, action):
    roles = principal["roles"]
    if len(roles) != 1:
        return set()
    role = roles[0]
    scope = resource.get("scope", "")
    kind = resource["kind"]
    attr = resource.get("attr", {})
    found = set()
    if role == "contractor":
        if scope == "":
            found.add("contractor-denied")
        elif kind == "invoice":
            found.add("contractor-invoice-denied")
        elif action == "view":
            found.add("contractor-view")
        elif action == "delete":
            found.add("contractor-delete-denied")
        elif action == "edit":
            flag = attr.get("contractor_editable", "absent")
            same = attr.get("department") == principal.get("attr", {}).get("department")
            if flag is True and not same:
                found.add("contractor-edit-other-department-denied")
            elif same:
                flag_labels = {
                    True: "contractor-edit-flag-true",
                    False: "contractor-edit-flag-false-denied",
                }
                found.add(flag_labels.get(flag, "contractor-edit-flag-absent-denied"))
    elif role == "auditor":
        if scope == "":
            found.add("auditor-denied")
        elif action == "view":
            found.add(f"auditor-{kind}-view")
        elif kind == "invoice" and action == "approve":
            found.add("auditor-invoice-approve-denied")
        elif kind == "document" and action == "edit":
            found.add("auditor-document-edit-denied")
    elif role == "editor" and kind == "document" and action == "edit":
        same = attr.get("department") == principal.get("attr", {}).get("department")
        if same and scope == "acme":
            found.add("editor-own-department-edit")
        elif not same:
            repaired = copy.deepcopy(resource)
            repaired.setdefault("attr", {})["department"] = principal["attr"].get("department")
            if allows(principal, repaired, action):
                found.add("editor-other-department-edit" + ("-denied" if scope else ""))
    elif scope == "acme" and role in {"viewer", "admin", "accountant"}:
        found.add("unaffected-role-base-permission")
    expected = allows(principal, resource, action)
    return {(scope, label) for label in found if label.endswith("-denied") != expected}


def generated_tests():
    report = {s["file"]: s for s in json.loads(REPORT.read_text()).get("suites", [])}
    assert SUITE in report, f"Missing executed suite: {SUITE}"
    suite_path = ROOT / SUITE
    suite = read(suite_path)
    fixtures = {}
    for name in ("principals", "resources"):
        shared = read(suite_path.parent / f"testdata/{name}.yaml").get(name, {})
        fixtures[name] = {**shared, **(suite.get(name) or {})}
    options = suite.get("options") or {}
    tests = {test.get("name"): test for test in suite.get("tests", [])}
    coverage = set()
    for case in report[SUITE].get("testCases", []):
        test_options = (tests.get(case.get("name")) or {}).get("options") or options
        for p_entry in case.get("principals", []):
            principal = fixtures["principals"][p_entry["name"]]
            for r_entry in p_entry.get("resources", []):
                resource = dict(fixtures["resources"][r_entry["name"]])
                resource["scope"] = resource.get("scope") or test_options.get("defaultScope", "")
                if len(principal["roles"]) != 1:
                    continue
                for action in r_entry.get("actions", []):
                    details = action["details"]
                    if details["result"] != "RESULT_PASSED":
                        continue
                    expected = allows(principal, resource, action["name"])
                    effect = "EFFECT_ALLOW" if expected else "EFFECT_DENY"
                    assert details["success"]["effect"] == effect, (
                        "Native test expectation contradicts contract: "
                        f"{case['name']} {p_entry['name']} {r_entry['name']} {action['name']}"
                    )
                    coverage |= labels(principal, resource, action["name"])
    missing = sorted(REQUIRED - coverage)
    assert not missing, f"Missing active test coverage: {missing}"


if __name__ == "__main__":
    {"architecture": architecture, "generated_tests": generated_tests}[sys.argv[1]]()
    print(f"PASS: {sys.argv[1]}")
