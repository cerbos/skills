"""Check the requested variable boundaries and generated test coverage."""

import re
import sys
from pathlib import Path

import yaml

ROOT = Path("/workspace/policies")


def documents():
    return [(p, yaml.safe_load(p.read_text())) for p in ROOT.rglob("*.yaml")]


def refs(value):
    return set(re.findall(r"\bV\.([A-Za-z_][A-Za-z_0-9]*)", str(value)))


def variables():
    docs = documents()
    exported = yaml.safe_load(
        (ROOT / "exported_variables/common_vars.yaml").read_text()
    )["exportVariables"]
    assert exported["name"] == "billing_common"
    definitions = exported["definitions"]
    dependent = {
        name
        for name, expression in definitions.items()
        if refs(expression) & definitions.keys()
    }
    assert dependent, "Shared eligibility must depend on shared variables through V.*"
    for kind in ("invoice", "expense"):
        policies = [
            d["resourcePolicy"]
            for _, d in docs
            if isinstance(d, dict)
            and d.get("resourcePolicy", {}).get("resource") == kind
        ]
        assert len(policies) == 1, f"Expected one {kind} policy"
        policy = policies[0]
        assert policy["version"] == "default"
        variables = policy["variables"]
        assert "billing_common" in variables["import"]
        local = variables["local"]
        assert local and not definitions.keys() & local.keys()
        reachable = refs(policy["rules"])
        pending = list(reachable)
        while pending:
            name = pending.pop()
            for dependency in refs({**definitions, **local}.get(name, "")) - reachable:
                reachable.add(dependency)
                pending.append(dependency)
        assert dependent & reachable, f"{kind} does not use shared eligibility"
        assert local.keys() & reachable, f"{kind} does not use local variables"
        assert not re.search(
            r"(?:P|R|request\.principal|request\.resource)\.attr\.(?:tenant|suspended)\b",
            str(policy),
        ), "Tenant and suspension checks belong in exported variables"
    print("PASS: exported dependencies, imports, local variables, and references")


def generated_tests():
    import json

    report = json.loads(Path("/logs/verifier/compile_normal.log").read_text())
    coverage = {kind: set() for kind in ("invoice", "expense")}
    effects = {kind: set() for kind in coverage}
    for suite in report.get("suites", []):
        path = ROOT / suite["file"]
        definition = yaml.safe_load(path.read_text())
        fixtures = {}
        for name in ("principals", "resources"):
            fixture_path = path.parent / f"testdata/{name}.yaml"
            external = (
                yaml.safe_load(fixture_path.read_text()).get(name, {})
                if fixture_path.exists()
                else {}
            )
            fixtures[name] = {**external, **definition.get(name, {})}
        for test in suite.get("testCases", []):
            for principal in test.get("principals", []):
                p = fixtures["principals"][principal["name"]]
                for resource in principal.get("resources", []):
                    r = fixtures["resources"][resource["name"]]
                    kind = r["kind"]
                    if kind not in coverage:
                        continue
                    pa, ra = p.get("attr", {}), r.get("attr", {})
                    limit = pa.get("approval_limit", 1000 if kind == "invoice" else 250)
                    eligible = (
                        "accountant" in p["roles"]
                        and pa["tenant"] == ra["tenant"]
                        and not pa.get("suspended", False)
                    )
                    approves = (
                        eligible
                        and ra["owner"] != p["id"]
                        and ra["status"] == "pending"
                        and not ra.get("blocked", False)
                        and ra["amount"] <= limit
                    )
                    for action in resource.get("actions", []):
                        details = action["details"]
                        if details["result"] != "RESULT_PASSED":
                            continue
                        actual = details["success"]["effect"]
                        allowed = (
                            eligible
                            if action["name"] == "view"
                            else approves
                            if action["name"] == "approve"
                            else False
                        )
                        assert actual == (
                            "EFFECT_ALLOW" if allowed else "EFFECT_DENY"
                        ), "Generated expectation contradicts requested behavior"
                        effects[kind].add(actual)
                        if action["name"] != "approve":
                            continue
                        covered = coverage[kind]
                        gates = {
                            "tenant": pa["tenant"] == ra["tenant"],
                            "owner": ra["owner"] != p["id"],
                            "blocked": not ra.get("blocked", False),
                            "suspended": not pa.get("suspended", False),
                            "amount": ra["amount"] <= limit,
                            "status": ra["status"] == "pending",
                            "role": "accountant" in p["roles"],
                        }
                        for gate in ("tenant", "owner", "blocked", "suspended"):
                            if not gates[gate] and all(
                                value for key, value in gates.items() if key != gate
                            ):
                                covered.add(gate)
                        if all(
                            value for key, value in gates.items() if key != "amount"
                        ):
                            if ra["amount"] == limit:
                                covered.add("boundary")
                            if ra["amount"] > limit:
                                covered.add("over")
                            default = 1000 if kind == "invoice" else 250
                            if "approval_limit" in pa and (ra["amount"] <= limit) != (
                                ra["amount"] <= default
                            ):
                                covered.add("override")
                        if approves:
                            for name in ("suspended", "approval_limit"):
                                if name not in pa:
                                    covered.add(f"absent_{name}")
                            if "blocked" not in ra:
                                covered.add("absent_blocked")
    required = {
        "tenant",
        "owner",
        "boundary",
        "over",
        "override",
        "blocked",
        "suspended",
        "absent_suspended",
        "absent_approval_limit",
        "absent_blocked",
    }
    for kind, covered in coverage.items():
        assert effects[kind] == {"EFFECT_ALLOW", "EFFECT_DENY"}, (
            f"{kind}: need active allowed and denied tests"
        )
        assert required <= covered, (
            f"{kind}: missing active coverage {required - covered}"
        )
    print("PASS: generated tests execute required behaviors for both kinds")


if __name__ == "__main__":
    {"variables": variables, "generated_tests": generated_tests}[sys.argv[1]]()
