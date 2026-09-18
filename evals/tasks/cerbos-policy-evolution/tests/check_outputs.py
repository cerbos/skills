"""Verify preservation and active, executed regression coverage."""

import hashlib
import json
import sys
from pathlib import Path

import yaml

ROOT = Path("/workspace/policies")


def preservation():
    for name, digest in json.loads(Path("/tests/preserved.json").read_text()).items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
    policy = yaml.safe_load((ROOT / "invoice.yaml").read_text())["resourcePolicy"]
    assert policy["resource"] == "invoice" and policy["version"] == "default"
    assert not policy.get("scope")
    for path in ROOT.rglob("*"):
        assert not path.is_symlink(), path


def matches_regression(principal, resource, contract):
    """Preserve a scenario's meaning without fixing fixture names or IDs."""
    attr = resource["attr"]
    minimum = contract["min_amount_exclusive"]
    return (
        resource.get("kind") == "invoice"
        and resource.get("policyVersion", "default") == "default"
        and set(principal["roles"]) == {contract["role"]}
        and attr["status"] == contract["status"]
        and (attr["tenant"] == principal["attr"]["tenant"]) == contract["same_tenant"]
        and attr["owner"] != principal["id"]
        and not attr.get("on_hold", False)
        and attr["amount"] <= contract["max_amount"]
        and (minimum is None or attr["amount"] > minimum)
    )


def coverage():
    report = json.loads(Path("/logs/verifier/compile_normal.log").read_text())
    suite = next(s for s in report["suites"] if s["file"] == "invoice_test.yaml")
    assert suite["summary"]["overallResult"] == "RESULT_PASSED"
    definition = yaml.safe_load((ROOT / "invoice_test.yaml").read_text())
    principals, resources = {}, {}
    for key, target in [("principals", principals), ("resources", resources)]:
        fixture = ROOT / "testdata" / (key + ".yaml")
        if fixture.exists():
            target.update(yaml.safe_load(fixture.read_text()).get(key, {}))
        target.update(definition.get(key, {}))
    required_tests = json.loads(Path("/tests/seed-test-names.json").read_text())
    active_tests, covered = {}, set()
    for test in suite.get("testCases", []):
        active_actions = set()
        for p in test.get("principals", []):
            principal = principals[p["name"]]
            roles = set(principal["roles"])
            for r in p.get("resources", []):
                resource = resources[r["name"]]
                attr = resource["attr"]
                for action in r.get("actions", []):
                    if action["details"]["result"] != "RESULT_PASSED":
                        continue
                    effect = action["details"]["success"]["effect"]
                    contract = required_tests.get(test["name"])
                    if (
                        contract is not None
                        and matches_regression(principal, resource, contract)
                        and contract["actions"].get(action["name"]) == effect
                    ):
                        active_actions.add(action["name"])
                    if action["name"] != "approve":
                        continue
                    common = (
                        attr["tenant"] == principal["attr"]["tenant"]
                        and attr["owner"] != principal["id"]
                        and attr["status"] == "submitted"
                    )
                    if common and not attr.get("on_hold", False):
                        if roles == {"accountant"} and attr["amount"] in (5000, 5001):
                            expected = (
                                "EFFECT_ALLOW"
                                if attr["amount"] == 5000
                                else "EFFECT_DENY"
                            )
                            if effect == expected:
                                covered.add(str(attr["amount"]))
                        if (
                            "finance_admin" in roles
                            and attr["amount"] > 5000
                            and effect == "EFFECT_ALLOW"
                        ):
                            covered.add("mixed" if "accountant" in roles else "admin")
                        if (
                            roles == {"accountant"}
                            and attr.get("on_hold") is False
                            and effect == "EFFECT_ALLOW"
                        ):
                            covered.add("clear")
                    for role in ("accountant", "finance_admin"):
                        if roles != {role} or effect != "EFFECT_DENY":
                            continue
                        if (
                            common
                            and attr.get("on_hold") is True
                            and (role == "finance_admin" or attr["amount"] <= 5000)
                        ):
                            covered.add(role + "-held")
                        if (
                            attr["tenant"] == principal["attr"]["tenant"]
                            and attr["owner"] == principal["id"]
                            and attr["status"] == "submitted"
                            and not attr.get("on_hold", False)
                            and (role == "finance_admin" or attr["amount"] <= 5000)
                        ):
                            covered.add(role + "-self")
                    if (
                        roles == {"finance_admin"}
                        and attr["tenant"] == principal["attr"]["tenant"]
                        and attr["owner"] != principal["id"]
                        and not attr.get("on_hold", False)
                        and attr["status"] in ("draft", "paid")
                        and effect == "EFFECT_DENY"
                    ):
                        covered.add(attr["status"])
        active_tests.setdefault(test["name"], set()).update(active_actions)
    for name, contract in required_tests.items():
        assert set(contract["actions"]) <= active_tests.get(name, set()), (
            f"Missing active regression scenario or expected effects: {name}"
        )
    required = {
        "5000",
        "5001",
        "admin",
        "mixed",
        "clear",
        "accountant-held",
        "finance_admin-held",
        "accountant-self",
        "finance_admin-self",
        "draft",
        "paid",
    }
    assert required <= covered, required - covered


if __name__ == "__main__":
    {"preservation": preservation, "coverage": coverage}[sys.argv[1]]()
    print("PASS:", sys.argv[1])
