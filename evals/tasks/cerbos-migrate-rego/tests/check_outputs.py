"""Generated native tests agree with the Rego semantics and cover the ordering edge cases."""

import json
from pathlib import Path

import yaml

from contract import decide_cerbos

ROOT = Path("/workspace/policies")
REPORT = Path("/logs/verifier/compile_normal.log")
REQUIRED = {"contractor-override-deny", "legal-hold-admin-deny"}


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


def strict_option(suite, test):
    return bool(
        ((suite.get("options") or {}).get("strictEvaluation"))
        or ((test.get("options") or {}).get("strictEvaluation"))
    )


def labels(principal, resource, action, effect):
    roles = set(principal.get("roles") or [])
    p_attr, r_attr = principal.get("attr") or {}, resource.get("attr") or {}
    found = set()
    if effect != "EFFECT_DENY":
        return found
    if (
        "contractor" in roles
        and "admin" not in roles
        and len(roles) > 1
        and "department" in p_attr
        and "department" in r_attr
        and p_attr["department"] != r_attr["department"]
    ):
        # Only counts when the user's other roles would allow the action on their own.
        others = {**principal, "roles": sorted(roles - {"contractor"})}
        if decide_cerbos(others, resource, action):
            found.add("contractor-override-deny")
    if "admin" in roles and r_attr.get("legal_hold") is True and action != "view":
        found.add("legal-hold-admin-deny")
    return found


def main():
    try:
        report = {s["file"]: s for s in json.loads(REPORT.read_text()).get("suites", [])}
    except (OSError, ValueError) as error:
        raise SystemExit(f"No JSON test report from compile_normal: {error}")
    coverage, executed = set(), 0
    for file, suite, principals, resources in suites(ROOT):
        tests = {t.get("name"): t for t in suite.get("tests") or []}
        for case in (report.get(file) or {}).get("testCases", []):
            for p_entry in case.get("principals", []):
                principal = principals[p_entry["name"]]
                for r_entry in p_entry.get("resources", []):
                    resource = resources[r_entry["name"]]
                    for action in r_entry.get("actions", []):
                        details = action["details"]
                        if details.get("result") != "RESULT_PASSED" or resource.get("kind") != "expense":
                            continue
                        executed += 1
                        effect = details["success"]["effect"]
                        expected = "EFFECT_ALLOW" if decide_cerbos(principal, resource, action["name"]) else "EFFECT_DENY"
                        if effect != expected:
                            raise SystemExit(
                                f"Native test expectation contradicts the Rego policy: {case['name']} "
                                f"{p_entry['name']} {r_entry['name']} {action['name']} asserts {effect}"
                            )
                        if not strict_option(suite, tests.get(case["name"]) or {}):
                            coverage |= labels(principal, resource, action["name"], effect)
    if not executed:
        raise SystemExit("No passing native test assertions for resource kind expense")
    missing = sorted(REQUIRED - coverage)
    if missing:
        raise SystemExit(f"Missing executed coverage: {missing}")
    print(f"PASS: generated_tests ({executed} expense assertions agree with the Rego semantics)")


if __name__ == "__main__":
    main()
