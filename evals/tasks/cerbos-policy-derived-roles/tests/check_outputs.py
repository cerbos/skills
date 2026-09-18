"""Verify shared derived-role architecture and active native test coverage."""

import json
import sys
from pathlib import Path

import yaml

ROOT = Path("/workspace/policies")
KINDS = ("document", "expense")
ROLE_NAMES = {"employee_owner", "department_reviewer"}


def read(path):
    value = yaml.safe_load(path.read_text())
    assert isinstance(value, dict), f"Expected mapping: {path}"
    return value


def architecture():
    expected = {ROOT / "derived_roles/tenant_roles.yaml"} | {
        ROOT / f"resource_policies/{kind}.yaml" for kind in KINDS
    }
    found = set()
    for path in ROOT.rglob("*"):
        assert not path.is_symlink(), f"Bundle must be self-contained: {path}"
        if path.is_file() and path.suffix in {".yaml", ".yml", ".json"}:
            data = read(path)
            fields = set(data) & {
                "resourcePolicy",
                "derivedRoles",
                "principalPolicy",
                "rolePolicy",
                "exportVariables",
                "exportConstants",
            }
            if fields:
                assert len(fields) == 1, f"Multiple policy types: {path}"
                found.add(path)
    assert found == expected, (
        "Expected two resource policies and one shared derived-role policy"
    )
    roles = read(ROOT / "derived_roles/tenant_roles.yaml")["derivedRoles"]
    assert roles["name"] == "tenant_roles"
    definitions = roles["definitions"]
    assert len(definitions) == 2 and {d["name"] for d in definitions} == ROLE_NAMES
    for definition in definitions:
        parent = "employee" if definition["name"] == "employee_owner" else "reviewer"
        assert definition["parentRoles"] == [parent], "Incorrect parent-role gating"
        assert definition.get("condition"), "Derived roles must be conditional"
    for kind in KINDS:
        policy = read(ROOT / f"resource_policies/{kind}.yaml")["resourcePolicy"]
        assert policy["resource"] == kind and policy["version"] == "default"
        assert not policy.get("scope"), "Use unscoped policies"
        assert policy.get("importDerivedRoles") == ["tenant_roles"]
        used = set()
        for rule in policy["rules"]:
            if rule["effect"] == "EFFECT_ALLOW":
                assert not rule.get("roles"), "Grants must use derived roles"
                assert not rule.get("condition"), (
                    "Keep relationship conditions in shared policy"
                )
                assert rule.get("derivedRoles"), "Grant missing derived roles"
                used.update(rule["derivedRoles"])
        assert used == ROLE_NAMES, f"Both derived roles must be used by {kind}"


def relationship(p, r):
    same = p["attr"]["tenant"] == r["attr"]["tenant"]
    owner = p["id"] == r["attr"]["owner"]
    department = p["attr"]["department"] == r["attr"]["department"]
    roles = set(p["roles"])
    is_owner = same and owner and "employee" in roles
    is_reviewer = same and department and "reviewer" in roles
    labels = set()
    if is_owner:
        labels.add("owner")
    if is_reviewer:
        labels.add("reviewer")
    if is_owner and is_reviewer:
        labels.add("overlap")
    if same and owner and "employee" not in roles:
        labels.add("wrong_owner_parent")
    if same and department and "reviewer" not in roles:
        labels.add("wrong_reviewer_parent")
    if not same and owner and "employee" in roles:
        labels.add("foreign_owner")
    if not same and department and "reviewer" in roles:
        labels.add("foreign_reviewer")
    if same and not owner and "employee" in roles:
        labels.add("nonowner")
    if same and not department and "reviewer" in roles:
        labels.add("wrong_department")
    return is_owner, is_reviewer, labels


def generated_tests():
    report = json.loads(Path("/logs/verifier/compile_normal.log").read_text())
    suites = {s["file"]: s for s in report.get("suites", [])}
    for kind in KINDS:
        filename = f"resource_policies/{kind}_test.yaml"
        suite = suites[filename]
        assert suite["summary"]["overallResult"] == "RESULT_PASSED"
        definition = read(ROOT / filename)
        fixture_dir = ROOT / "resource_policies/testdata"
        principals = read(fixture_dir / "principals.yaml")["principals"]
        resources = read(fixture_dir / "resources.yaml")["resources"]
        principals.update(definition.get("principals", {}))
        resources.update(definition.get("resources", {}))
        coverage = set()
        for test in suite.get("testCases", []):
            for principal in test.get("principals", []):
                p = principals[principal["name"]]
                for resource in principal.get("resources", []):
                    r = resources[resource["name"]]
                    assert r["kind"] == kind
                    assert r.get("policyVersion", "default") == "default"
                    owner, reviewer, labels = relationship(p, r)
                    for action in resource.get("actions", []):
                        details = action["details"]
                        if details["result"] != "RESULT_PASSED":
                            continue
                        name = action["name"]
                        allowed = (owner and name in {"view", "edit"}) or (
                            reviewer and name in {"view", "approve"}
                        )
                        expected = "EFFECT_ALLOW" if allowed else "EFFECT_DENY"
                        assert details["success"]["effect"] == expected, (
                            "Native test expectation contradicts contract"
                        )
                        coverage.update((label, name) for label in labels)
                        if name == "delete":
                            coverage.add(("default_deny", name))
        required = {
            ("owner", "edit"),
            ("reviewer", "approve"),
            ("overlap", "edit"),
            ("overlap", "approve"),
            ("wrong_owner_parent", "edit"),
            ("wrong_reviewer_parent", "approve"),
            ("foreign_owner", "edit"),
            ("foreign_reviewer", "approve"),
            ("nonowner", "edit"),
            ("wrong_department", "approve"),
            ("default_deny", "delete"),
        }
        assert required <= coverage, (
            f"Missing active {kind} test coverage: {required - coverage}"
        )


if __name__ == "__main__":
    {"architecture": architecture, "generated_tests": generated_tests}[sys.argv[1]]()
    print(f"PASS: {sys.argv[1]}")
