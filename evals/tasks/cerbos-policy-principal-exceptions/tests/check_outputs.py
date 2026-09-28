"""Verify the policy structure and active test coverage of time and JWT behaviour."""

import copy
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

from contract import AUDITOR, decide, has_mfa, resource_policy_allows

ROOT = Path("/workspace/policies")
REPORT = Path("/logs/verifier/compile_normal.log")
SEED = Path("/tests/seed_policy.json")
RESOURCE_POLICY = "resource_policies/ticket.yaml"
PRINCIPAL_POLICY = "principal_policies/ext-auditor-7.yaml"
SUITE = "resource_policies/ticket_test.yaml"
CLOSE_RULE = "managers-close-tickets"
POLICY_KEYS = {
    "resourcePolicy",
    "rolePolicy",
    "principalPolicy",
    "derivedRoles",
    "exportVariables",
    "exportConstants",
}
REQUIRED = {
    "auditor-view-active",
    "auditor-view-expired",
    "auditor-export-denied",
    "reporter-export-allowed",
    "close-mfa-allowed",
    "close-without-mfa-denied",
}


def read(path):
    value = yaml.safe_load(path.read_text())
    assert isinstance(value, dict), f"Expected mapping: {path}"
    return value


def check_resource_policy(policy):
    seed = json.loads(SEED.read_text())
    rules = policy.get("rules", [])
    by_name = {rule.get("name"): rule for rule in rules}
    assert len(by_name) == len(rules), "Rule names must be unique"
    for rule in seed["rules"]:
        assert rule["name"] in by_name, f"Seed rule removed or renamed: {rule['name']}"
        current = copy.deepcopy(by_name[rule["name"]])
        expected = copy.deepcopy(rule)
        if rule["name"] == CLOSE_RULE:
            # The MFA requirement may be added to the close rule's condition.
            current.pop("condition", None)
            expected.pop("condition", None)
        assert current == expected, f"Rule {rule['name']} changed beyond the close condition"
    seed_names = {rule["name"] for rule in seed["rules"]}
    for name, rule in by_name.items():
        if name in seed_names:
            continue
        # A separate rule may deny closing without MFA; nothing else may be added.
        assert rule.get("effect") == "EFFECT_DENY" and set(rule.get("actions", [])) <= {"close"}, (
            f"Unexpected rule in the ticket policy: {name}"
        )
    rest = {k: v for k, v in policy.items() if k not in {"rules", "schemas"}}
    assert rest == {k: v for k, v in seed.items() if k != "rules"}, "Policy header changed"


def check_principal_policy(policy):
    assert policy.get("principal") == AUDITOR, f"principal must be {AUDITOR}"
    assert policy.get("version", "default") == "default", "principal policy version must be default"
    assert not policy.get("scope"), "principal policy must be unscoped"
    entries = [
        action
        for rule in policy.get("rules", [])
        if rule.get("resource") == "ticket"
        for action in rule.get("actions", [])
    ]
    assert any(a.get("action") == "view" and a.get("effect") == "EFFECT_ALLOW" for a in entries), (
        "principal policy must allow view on ticket"
    )
    assert any(a.get("action") == "export" and a.get("effect") == "EFFECT_DENY" for a in entries), (
        "principal policy must deny export on ticket"
    )


def structure():
    policies = {}
    for path in ROOT.rglob("*"):
        assert not path.is_symlink(), f"Bundle must be self-contained: {path}"
        if path.is_file() and path.suffix in {".yaml", ".yml"}:
            value = read(path)
            if set(value) & POLICY_KEYS:
                policies[path.relative_to(ROOT).as_posix()] = value
    expected = {RESOURCE_POLICY, PRINCIPAL_POLICY}
    assert set(policies) == expected, (
        f"Expected the ticket policy and the auditor's principal policy only, found {sorted(policies)}"
    )
    resource = policies[RESOURCE_POLICY].get("resourcePolicy")
    assert isinstance(resource, dict), f"{RESOURCE_POLICY} must be a resource policy"
    check_resource_policy(resource)
    principal = policies[PRINCIPAL_POLICY].get("principalPolicy")
    assert isinstance(principal, dict), f"{PRINCIPAL_POLICY} must be a principal policy"
    check_principal_policy(principal)


def to_time(value):
    """RFC 3339 string (or a YAML-parsed timestamp) as an aware datetime."""
    if isinstance(value, date) and not isinstance(value, datetime):
        value = datetime(value.year, value.month, value.day)
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert isinstance(value, datetime), f"Not a timestamp: {value!r}"
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def normalise(principal):
    """Parse the auditor's engagement end so the contract compares datetimes."""
    principal = copy.deepcopy(principal)
    attr = principal.get("attr") or {}
    if "engagement_ends" in attr:
        attr["engagement_ends"] = to_time(attr["engagement_ends"]).isoformat()
    principal["attr"] = attr
    principal.setdefault("roles", [])
    return principal


def labels(principal, resource, action, now, jwt):
    """Behaviours an executed assertion demonstrates; now is None when unpinned."""
    roles = set(principal["roles"])
    found = set()
    if principal["id"] == AUDITOR:
        ends = principal["attr"].get("engagement_ends")
        # The view must come from the principal policy, not from a team role.
        if action == "view" and now is not None and ends is not None:
            if not resource_policy_allows(principal, resource, action, jwt):
                found.add("auditor-view-active" if now < to_time(ends) else "auditor-view-expired")
        # The DENY must override a real grant: the auditor holds the reporter role.
        if action == "export" and "reporter" in roles:
            found.add("auditor-export-denied")
        return found
    if action == "export" and "reporter" in roles:
        found.add("reporter-export-allowed")
    team = principal["attr"].get("team")
    if action == "close" and "manager" in roles and team is not None and resource["attr"].get("team") == team:
        if jwt is None:
            found.add("close-no-token-denied")
        elif has_mfa(jwt):
            found.add("close-mfa-allowed")
        else:
            found.add("close-without-mfa-denied")
    return found


def fixtures(suite):
    merged = {}
    for name, key in (("principals", "principals"), ("resources", "resources"), ("auxdata", "auxData")):
        shared = {}
        for suffix in (".yaml", ".yml", ".json"):
            path = ROOT / Path(SUITE).parent / "testdata" / f"{name}{suffix}"
            if path.is_file():
                shared = read(path).get(key) or {}
                break
        merged[key] = {**shared, **(suite.get(key) or {})}
    return merged


def generated_tests():
    report = {s["file"]: s for s in json.loads(REPORT.read_text()).get("suites", [])}
    assert SUITE in report, f"Missing executed suite: {SUITE}"
    suite = read(ROOT / SUITE)
    fx = fixtures(suite)
    tests = {test.get("name"): test for test in suite.get("tests", [])}
    wall_clock = datetime.now(timezone.utc)
    coverage = set()
    for case in report[SUITE].get("testCases", []):
        test = tests.get(case.get("name")) or {}
        # A test's options replace the suite's options rather than merging.
        options = test.get("options") if test.get("options") is not None else suite.get("options") or {}
        now = to_time(options["now"]) if options.get("now") is not None else None
        aux_key = (test.get("input") or {}).get("auxData")
        jwt = (fx["auxData"].get(aux_key) or {}).get("jwt") if aux_key else None
        for p_entry in case.get("principals", []):
            principal = normalise(fx["principals"][p_entry["name"]])
            for r_entry in p_entry.get("resources", []):
                resource = fx["resources"][r_entry["name"]]
                if resource.get("kind") != "ticket":
                    continue
                resource = {**resource, "attr": resource.get("attr") or {}}
                for action in r_entry.get("actions", []):
                    details = action["details"]
                    if details["result"] != "RESULT_PASSED":
                        continue
                    allowed = decide(principal, resource, action["name"], now or wall_clock, jwt)
                    effect = "EFFECT_ALLOW" if allowed else "EFFECT_DENY"
                    assert details["success"]["effect"] == effect, (
                        "Native test expectation contradicts contract: "
                        f"{case['name']} {p_entry['name']} {r_entry['name']} {action['name']}"
                    )
                    coverage |= labels(principal, resource, action["name"], now, jwt)
    missing = sorted(REQUIRED - coverage)
    assert not missing, f"Missing active test coverage: {missing}"


if __name__ == "__main__":
    {"structure": structure, "generated_tests": generated_tests}[sys.argv[1]]()
    print(f"PASS: {sys.argv[1]}")
