"""Verify preserved rules and seed tests, and executed coverage of the repairs."""

import json
import sys
from pathlib import Path

import yaml

from contract import DOWNLOAD_LIMIT_MB, decide

ROOT = Path("/workspace/policies")
TESTS = Path("/tests")
REPORT = Path("/logs/verifier/compile_normal.log")
POLICY = "resource_policies/document.yaml"
# Rules seeded with a defect may change anything except name, actions and effect.
REPAIRABLE = {"edit-own-documents", "download-within-limit", "deny-contractor-non-public"}
REQUIRED = {"unclassified-contractor-view-deny", "download-at-limit-allow", "download-over-limit-deny"}


def read(path):
    value = yaml.safe_load(path.read_text())
    assert isinstance(value, dict), f"Expected mapping: {path}"
    return value


def suites(root):
    """Yield (relative path, suite, principals, resources) with shared fixtures merged."""
    for path in sorted(root.rglob("*_test.yaml")) + sorted(root.rglob("*_test.yml")):
        suite = read(path)
        fixtures = {}
        for name in ("principals", "resources"):
            shared = {}
            for suffix in (".yaml", ".yml", ".json"):
                candidate = path.parent / "testdata" / (name + suffix)
                if candidate.exists():
                    shared = read(candidate).get(name) or {}
                    break
            fixtures[name] = {**shared, **(suite.get(name) or {})}
        yield path.relative_to(root).as_posix(), suite, fixtures["principals"], fixtures["resources"]


def names(entry, kind, groups):
    """Fixture names from singular, plural and group fields of an input or expectation."""
    values = list(entry.get(kind + "s") or [])
    if entry.get(kind):
        values.append(entry[kind])
    for group in entry.get(kind + "Groups") or []:
        values.extend((groups.get(group) or {}).get(kind + "s") or [])
    return values


def signature(principal, resource, action, effect):
    """Describe a decision by fixture contents rather than fixture names or IDs."""
    attr = dict(resource.get("attr") or {})
    owned = attr.pop("owner", None) == principal.get("id")
    return canonical(
        {
            "roles": sorted(principal.get("roles") or []),
            "principalAttr": principal.get("attr") or {},
            "kind": resource.get("kind"),
            "policyVersion": resource.get("policyVersion", "default"),
            "resourceAttr": attr,
            "ownedByPrincipal": owned,
            "action": action,
            "effect": effect,
        }
    )


def canonical(value):
    return json.dumps(value, sort_keys=True)


def seed_tests():
    tests = json.loads((TESTS / "seed-test-names.json").read_text())
    return {name: {canonical(item) for item in items} for name, items in tests.items()}


def expectations(root):
    """Map each test name to the signatures of every decision it asserts."""
    found = {}
    for _, suite, principals, resources in suites(root):
        p_groups, r_groups = suite.get("principalGroups") or {}, suite.get("resourceGroups") or {}
        for test in suite.get("tests") or []:
            if suite.get("skip") or test.get("skip"):
                continue
            data = test.get("input") or {}
            effects = {}
            for entry in test.get("expected") or []:
                for p in names(entry, "principal", p_groups):
                    for r in names(entry, "resource", r_groups):
                        for action, effect in (entry.get("actions") or {}).items():
                            effects[(p, r, action)] = effect
            sigs = found.setdefault(test.get("name"), set())
            for p in names(data, "principal", p_groups):
                for r in names(data, "resource", r_groups):
                    for action in data.get("actions") or []:
                        effect = effects.get((p, r, action), "EFFECT_DENY")
                        sigs.add(signature(principals[p], resources[r], action, effect))
    return found


def preservation():
    seed = json.loads((TESTS / "seed_policy.json").read_text())
    policy = read(ROOT / POLICY)["resourcePolicy"]
    assert policy.get("resource") == seed["resource"], "Resource kind changed"
    assert policy.get("version") == seed["version"], "Policy version changed"
    assert not policy.get("scope"), "Policy must not gain a scope"
    rules = {}
    for rule in policy.get("rules") or []:
        assert rule.get("name") not in rules, f"Duplicate rule name: {rule.get('name')}"
        rules[rule.get("name")] = rule
    for rule in seed["rules"]:
        current = rules.get(rule["name"])
        assert current is not None, f"Rule removed or renamed: {rule['name']}"
        if rule["name"] in REPAIRABLE:
            for key in ("actions", "effect"):
                assert current.get(key) == rule[key], f"Rule {rule['name']} changed its {key}"
        else:
            assert current == rule, f"Rule {rule['name']} changed but was not defective"
    current = expectations(ROOT)
    for name, sigs in seed_tests().items():
        assert name in current, f"Seed test removed, renamed or skipped: {name}"
        missing = sigs - current[name]
        assert not missing, f"Seed test {name} lost or changed expectations: {sorted(missing)}"
    for path in ROOT.rglob("*"):
        assert not path.is_symlink(), f"Bundle must be self-contained: {path}"


def strict_option(suite, test):
    return bool(((suite.get("options") or {}).get("strictEvaluation")) or ((test.get("options") or {}).get("strictEvaluation")))


def labels(principal, resource, action, effect):
    roles, attr = set(principal.get("roles") or []), resource.get("attr") or {}
    found = set()
    if resource.get("kind") != "document":
        return found
    if roles == {"contractor"} and action == "view" and "classification" not in attr and effect == "EFFECT_DENY":
        found.add("unclassified-contractor-view-deny")
    if roles == {"employee"} and action == "download":
        if attr.get("size_mb") == DOWNLOAD_LIMIT_MB and effect == "EFFECT_ALLOW":
            found.add("download-at-limit-allow")
        if attr.get("size_mb", 0) > DOWNLOAD_LIMIT_MB and effect == "EFFECT_DENY":
            found.add("download-over-limit-deny")
    return found


def generated_tests():
    report = {s["file"]: s for s in json.loads(REPORT.read_text()).get("suites", [])}
    executed, coverage = {}, set()
    for file, suite, principals, resources in suites(ROOT):
        tests = {t.get("name"): t for t in suite.get("tests") or []}
        for case in (report.get(file) or {}).get("testCases", []):
            for p_entry in case.get("principals", []):
                principal = principals[p_entry["name"]]
                for r_entry in p_entry.get("resources", []):
                    resource = resources[r_entry["name"]]
                    for action in r_entry.get("actions", []):
                        details = action["details"]
                        if details.get("result") != "RESULT_PASSED" or resource.get("kind") != "document":
                            continue
                        effect = details["success"]["effect"]
                        expected = "EFFECT_ALLOW" if decide(principal, resource, action["name"]) else "EFFECT_DENY"
                        assert effect == expected, (
                            f"Native test expectation contradicts requirements: {case['name']} "
                            f"{p_entry['name']} {r_entry['name']} {action['name']}"
                        )
                        executed.setdefault(case["name"], set()).add(
                            signature(principal, resource, action["name"], effect)
                        )
                        # Coverage must hold under default evaluation, not only a strict option.
                        if not strict_option(suite, tests.get(case["name"]) or {}):
                            coverage |= labels(principal, resource, action["name"], effect)
    for name, sigs in seed_tests().items():
        missing = sigs - executed.get(name, set())
        assert not missing, f"Seed test {name} did not execute and pass: {sorted(missing)}"
    missing = sorted(REQUIRED - coverage)
    assert not missing, f"Missing executed coverage: {missing}"


def snapshot(policies):
    """Write the seed fixtures used by preservation (run once against environment/policies)."""
    root = Path(policies)
    policy = read(root / POLICY)["resourcePolicy"]
    (Path(__file__).with_name("seed_policy.json")).write_text(json.dumps(policy, indent=2) + "\n")
    tests = {name: [json.loads(sig) for sig in sorted(sigs)] for name, sigs in expectations(root).items()}
    (Path(__file__).with_name("seed-test-names.json")).write_text(json.dumps(tests, indent=2) + "\n")


if __name__ == "__main__":
    if sys.argv[1] == "snapshot":
        snapshot(sys.argv[2])
    else:
        {"preservation": preservation, "generated_tests": generated_tests}[sys.argv[1]]()
    print(f"PASS: {sys.argv[1]}")
