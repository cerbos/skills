"""Verify the scope hierarchy's structure and active native test coverage."""

import copy
import json
import sys
from pathlib import Path

import yaml

from contract import BASE, allows

ROOT = Path("/workspace/policies")
REPORT = Path("/logs/verifier/compile_normal.log")
CONSENT = "SCOPE_PERMISSIONS_REQUIRE_PARENTAL_CONSENT_FOR_ALLOWS"
OVERRIDE = "SCOPE_PERMISSIONS_OVERRIDE_PARENT"
POLICIES = {
    "resource_policies/report.yaml": "",
    "resource_policies/acme/report.yaml": "acme",
    "resource_policies/acme/eu/report.yaml": "acme.eu",
    "resource_policies/globex/report.yaml": "globex",
}
# Mirrors the instruction's coverage list. "*" labels may come from any scope;
# "outside-globex" labels from any scope other than globex.
REQUIRED = {
    ("", "inherited"),
    ("acme", "inherited"),
    ("acme.eu", "inherited"),
    ("globex", "inherited"),
    ("acme", "editor-edit-draft"),
    ("acme", "editor-edit-nondraft-denied"),
    ("acme.eu", "editor-edit-draft"),
    ("acme.eu", "editor-edit-nondraft-denied"),
    ("acme.eu", "region-denied"),
    ("outside-globex", "contractor-visible-denied"),
    ("globex", "contractor-visible-view"),
    ("globex", "contractor-absent-denied"),
    ("globex", "admin-delete-denied"),
    ("globex", "editor-edit-nondraft"),
    ("*", "multirole"),
}


def read(path):
    value = yaml.safe_load(path.read_text())
    assert isinstance(value, dict), f"Expected mapping: {path}"
    return value


def architecture():
    found = {}
    for path in ROOT.rglob("*"):
        assert not path.is_symlink(), f"Bundle must be self-contained: {path}"
        if not path.is_file() or path.suffix not in {".yaml", ".yml"}:
            continue
        policy = read(path).get("resourcePolicy")
        if isinstance(policy, dict) and policy.get("resource") == "report":
            found[path.relative_to(ROOT).as_posix()] = policy
    assert set(found) == set(POLICIES), (
        f"Expected report policies at {sorted(POLICIES)}, found {sorted(found)}"
    )
    for relative, scope in POLICIES.items():
        policy = found[relative]
        assert policy.get("version") == "default", f"Wrong version: {relative}"
        assert (policy.get("scope") or "") == scope, f"Wrong scope in {relative}"
        permissions = policy.get("scopePermissions")
        if scope.startswith("acme"):
            assert permissions == CONSENT, (
                f"{scope} policies must only narrow their parent's permissions"
            )
        elif scope == "globex":
            assert permissions in (None, OVERRIDE), (
                "globex must be able to override its parent"
            )


def resolve_scope(resource, test, suite):
    for source in (resource, (test or {}).get("options") or {}, suite.get("options") or {}):
        scope = source.get("scope") if source is resource else source.get("defaultScope")
        if scope:
            return scope
    return ""


def labels(principal, resource, action):
    scope = resource.get("scope", "")
    roles = set(principal["roles"])
    attr = resource.get("attr", {})
    region = principal.get("attr", {}).get("region")
    draft = attr.get("status") == "draft"
    visible = attr.get("contractor_visible", False) is True
    only = next(iter(roles)) if len(roles) == 1 else None
    found = set()
    if any(action in BASE.get(role, set()) for role in roles):
        found.add("inherited")
    if only == "editor" and action == "edit":
        if draft:
            found.add("editor-edit-draft")
        else:
            found.add("editor-edit-nondraft")
            found.add("editor-edit-nondraft-denied")
    if only == "admin" and action == "delete" and scope == "globex":
        found.add("admin-delete-denied")
    if only == "contractor" and action == "view":
        if visible:
            found.add("contractor-visible-denied")
            found.add("contractor-visible-view")
        elif "contractor_visible" not in attr:
            found.add("contractor-absent-denied")
    union = len(roles) > 1 and any(
        not allows({**principal, "roles": [role]}, resource, action) for role in roles
    )
    if union:
        found.add("multirole")
    if scope == "acme.eu" and region != "eu":
        # A non-EU principal is denied by residency, so other denials are confounded.
        found.clear()
        counterfactual = copy.deepcopy(principal)
        counterfactual.setdefault("attr", {})["region"] = "eu"
        if allows(counterfactual, resource, action):
            found.add("region-denied")
    # Keep only labels whose outcome demonstrates the named behaviour.
    expected = allows(principal, resource, action)
    denied = {label for label in found if label.endswith("-denied")}
    kept = {label for label in found if (label in denied) != expected}
    result = set()
    for label in kept:
        if label == "multirole":
            result.add(("*", label))
        elif label == "contractor-visible-denied" and scope != "globex":
            result.add(("outside-globex", label))
        else:
            result.add((scope, label))
    return result


def generated_tests():
    report = json.loads(REPORT.read_text())
    coverage = set()
    for summary in report.get("suites", []):
        path = ROOT / summary["file"]
        suite = read(path)
        fixtures = {}
        for name in ("principals", "resources"):
            shared_path = path.parent / f"testdata/{name}.yaml"
            shared = read(shared_path).get(name, {}) if shared_path.exists() else {}
            fixtures[name] = {**shared, **(suite.get(name) or {})}
        tests = {test.get("name"): test for test in suite.get("tests", [])}
        for case in summary.get("testCases", []):
            for principal_entry in case.get("principals", []):
                principal = fixtures["principals"][principal_entry["name"]]
                for resource_entry in principal_entry.get("resources", []):
                    resource = dict(fixtures["resources"][resource_entry["name"]])
                    if resource.get("kind") != "report":
                        continue
                    assert resource.get("policyVersion", "default") == "default"
                    resource["scope"] = resolve_scope(
                        resource, tests.get(case.get("name")), suite
                    )
                    for action in resource_entry.get("actions", []):
                        details = action["details"]
                        if details["result"] != "RESULT_PASSED":
                            continue
                        name = action["name"]
                        expected = allows(principal, resource, name)
                        actual = details["success"]["effect"]
                        assert actual == ("EFFECT_ALLOW" if expected else "EFFECT_DENY"), (
                            "Native test expectation contradicts contract: "
                            f"{principal_entry['name']} {resource_entry['name']} {name}"
                        )
                        coverage |= labels(principal, resource, name)
    missing = sorted(REQUIRED - coverage)
    assert not missing, f"Missing active test coverage: {missing}"


if __name__ == "__main__":
    {"architecture": architecture, "generated_tests": generated_tests}[sys.argv[1]]()
    print(f"PASS: {sys.argv[1]}")
