"""Check generated bundle structure and semantic coverage independently by stage."""

import argparse
import json
from pathlib import Path

import yaml

DOMAINS = {"content": "document", "billing": "invoice"}
ROLES = {"reader", "editor", "accountant", "visitor"}
EXPECTED = ["_schemas/principal.json"] + [
    path
    for domain, kind in DOMAINS.items()
    for path in (
        f"_schemas/resources/{kind}.json",
        f"resource_policies/{domain}/{kind}.yaml",
        f"resource_policies/{domain}/{kind}_test.yaml",
        f"resource_policies/{domain}/testdata/principals.yaml",
        f"resource_policies/{domain}/testdata/resources.yaml",
    )
]


def read_yaml(path):
    value = yaml.safe_load(path.read_text())
    assert isinstance(value, dict), f"Expected YAML mapping: {path}"
    return value


def files(root):
    for relative in EXPECTED:
        path = root / relative
        assert path.is_file() and path.read_text().strip(), f"Missing/empty: {relative}"


def folder_structure(root):
    for relative in EXPECTED:
        assert (root / relative).parent.is_dir(), (
            f"Missing folder: {Path(relative).parent}"
        )
    for path in root.rglob("*"):
        assert not path.is_symlink(), (
            f"Bundle must contain its files, not symlinks: {path}"
        )


def policy(root, domain, kind):
    value = read_yaml(root / f"resource_policies/{domain}/{kind}.yaml")
    result = value.get("resourcePolicy")
    assert isinstance(result, dict), f"Missing resourcePolicy for {kind}"
    return result


def resource_policies(root):
    expected_paths = {
        root / f"resource_policies/{domain}/{kind}.yaml"
        for domain, kind in DOMAINS.items()
    }
    actual_paths = set()
    for path in root.rglob("*"):
        if path.suffix not in {".yaml", ".yml", ".json"} or not path.is_file():
            continue
        value = (
            json.loads(path.read_text()) if path.suffix == ".json" else read_yaml(path)
        )
        if not isinstance(value, dict):
            continue
        policy_fields = set(value) & {
            "resourcePolicy",
            "principalPolicy",
            "rolePolicy",
            "derivedRoles",
            "exportVariables",
            "exportConstants",
        }
        if policy_fields:
            assert policy_fields == {"resourcePolicy"}, (
                f"Unexpected policy type in {path}"
            )
            actual_paths.add(path)
    assert actual_paths == expected_paths, (
        "Expected exactly the two resource policies in their domains"
    )
    for domain, kind in DOMAINS.items():
        value = policy(root, domain, kind)
        assert value.get("resource") == kind, f"Wrong resource kind for {domain}"
        assert value.get("version") == "default", f"Wrong policy version for {kind}"
        assert not value.get("scope"), f"Unexpected scoped policy: {kind}"


def schemas(root):
    for relative in (
        "_schemas/principal.json",
        "_schemas/resources/document.json",
        "_schemas/resources/invoice.json",
    ):
        value = json.loads((root / relative).read_text())
        assert isinstance(value, dict) and value.get("type") == "object", (
            f"Expected attribute-object schema: {relative}"
        )
        assert not value.get("required"), f"No attributes are required: {relative}"
        assert not value.get("properties"), f"No attributes are defined: {relative}"
    for domain, kind in DOMAINS.items():
        value = policy(root, domain, kind).get("schemas", {})
        for field, relative in (
            ("principalSchema", "principal.json"),
            ("resourceSchema", f"resources/{kind}.json"),
        ):
            assert value.get(field, {}).get("ref") == f"cerbos:///{relative}", (
                f"Wrong/unresolved {field} reference for {kind}"
            )
            assert (root / "_schemas" / relative).is_file(), (
                f"Missing schema: {relative}"
            )


def load_fixtures(root, domain):
    path = root / f"resource_policies/{domain}/testdata"
    principals = read_yaml(path / "principals.yaml").get("principals", {})
    resources = read_yaml(path / "resources.yaml").get("resources", {})
    assert isinstance(principals, dict) and principals, f"Empty principals in {domain}"
    assert isinstance(resources, dict) and resources, f"Empty resources in {domain}"
    return principals, resources


def validate_principal(value):
    assert isinstance(value, dict) and value.get("id"), "Missing principal ID"
    roles = value.get("roles")
    assert (
        isinstance(roles, list)
        and roles
        and all(isinstance(role, str) and role for role in roles)
    ), "Missing principal roles"
    assert not value.get("attr"), "Principal fixtures must have empty attributes"
    return roles


def validate_resource(value, kind):
    assert isinstance(value, dict) and value.get("id"), "Missing resource ID"
    assert value.get("kind") == kind, "Wrong fixture resource kind"
    assert value.get("policyVersion", "default") == "default", (
        "Wrong fixture policy version"
    )
    assert not value.get("attr"), "Resource fixtures must have empty attributes"


def fixtures(root):
    for domain, kind in DOMAINS.items():
        principals, resources = load_fixtures(root, domain)
        for value in principals.values():
            validate_principal(value)
        for value in resources.values():
            validate_resource(value, kind)


def expected_effect(kind, roles, action):
    allowed = {
        "document": {"reader": {"view"}, "editor": {"view", "edit"}},
        "invoice": {"accountant": {"view", "approve"}},
    }
    return (
        "EFFECT_ALLOW"
        if any(action in allowed[kind].get(role, set()) for role in roles)
        else "EFFECT_DENY"
    )


def generated_tests(root):
    report = json.loads(Path("/logs/verifier/compile_normal.log").read_text())
    suites = {suite["file"]: suite for suite in report.get("suites", [])}
    for domain, kind in DOMAINS.items():
        filename = f"resource_policies/{domain}/{kind}_test.yaml"
        suite = suites[filename]
        assert suite["summary"]["overallResult"] == "RESULT_PASSED", (
            f"Generated tests did not pass: {kind}"
        )
        # Cerbos resolves selectors, groups, skips and default expectations.
        # Resolve only the reported fixture names to check the business contract.
        definition = read_yaml(root / filename)
        principals, resources = load_fixtures(root, domain)
        principals.update(definition.get("principals", {}))
        resources.update(definition.get("resources", {}))
        effects = set()
        for test in suite.get("testCases", []):
            for principal in test.get("principals", []):
                roles = validate_principal(principals[principal["name"]])
                for resource in principal.get("resources", []):
                    validate_resource(resources[resource["name"]], kind)
                    for action in resource.get("actions", []):
                        details = action["details"]
                        if details["result"] != "RESULT_PASSED":
                            continue
                        effect = details["success"]["effect"]
                        assert effect == expected_effect(kind, roles, action["name"]), (
                            f"Incorrect expectation for {kind}/{roles}/{action['name']}"
                        )
                        effects.add(effect)
        assert effects == {"EFFECT_ALLOW", "EFFECT_DENY"}, (
            f"Missing active ALLOW/DENY test coverage for {kind}"
        )


STAGES = {
    name: globals()[name]
    for name in (
        "files",
        "folder_structure",
        "resource_policies",
        "schemas",
        "generated_tests",
        "fixtures",
    )
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=STAGES)
    parser.add_argument("--root", type=Path, default=Path("/workspace/policies"))
    args = parser.parse_args()
    STAGES[args.stage](args.root)
    print(f"PASS: {args.stage}")
