#!/usr/bin/env python3
"""Check that a Cerbos test run covers a saved coverage plan.

Usage:
    python3 coverage_audit.py --policies DIR --plan PLAN.yaml \
        --report normal.json [--report strict.json]

Each report is the stdout of `cerbos compile --output=json DIR` (add
`--strict-evaluation` for the strict report). The plan is YAML:

    rows:
      - id: document-owner-edit
        principal: alice_employee          # fixture key
        resource: document_owned_by_alice  # fixture key
        action: edit
        effect: EFFECT_ALLOW
      - id: document-missing-parent-role-edit
        principal: alice_reviewer_only
        resource: document_owned_by_alice
        action: edit
        effect: EFFECT_DENY
        control: document-owner-edit       # row id with the opposite effect
        change: principal.roles            # the one request field that differs
        path: document-owner               # grant path this row isolates
        prerequisite: parent-role          # which of the path's requirements
        facts:                             # values the resolved request must have
          resource.attr.owner: alice
    paths:
      - id: document-owner
        kind: document
        requires: [parent-role, tenant, ownership]

Optional row fields: `suite` (test file path relative to DIR) and `test`
(test case name) narrow the match. Field paths are `principal.id`,
`principal.roles`, `principal.attr.<name>`, `resource.kind`,
`resource.attr.<name>`, plus `scope` and `policyVersion` on either side.
`resource.id` is ignored when comparing a row with its control. `facts` maps
field paths to required values; use null for an absent attribute.

For every row the audit requires an executed, passing assertion with the
planned effect in every report. For a row with a control it also requires the
control to have the opposite effect, the same action and resource kind, and
resolved requests that differ at exactly the named field, and the resolved
request to have every value listed in `facts`. For every declared
path it requires, for each listed prerequisite, a passing row with that `path`,
`prerequisite` and a control, against a resource of the path's kind.
Requires PyYAML.
"""

import argparse
import json
import sys
from pathlib import Path

import yaml

ABSENT = "<absent>"
EFFECTS = {"EFFECT_ALLOW", "EFFECT_DENY"}


def load_yaml(path):
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text()) or {}


def fixtures(policies, suite_file, cache):
    """Resolve fixture keys for a suite: sibling testdata, then inline entries."""
    if suite_file in cache:
        return cache[suite_file]
    suite_path = policies / suite_file
    testdata = suite_path.parent / "testdata"
    suite = load_yaml(suite_path)
    resolved = {}
    for name in ("principals", "resources"):
        shared = {}
        for extension in ("yaml", "yml", "json"):
            shared.update(load_yaml(testdata / f"{name}.{extension}").get(name) or {})
        resolved[name] = {**shared, **(suite.get(name) or {})}
    cache[suite_file] = resolved
    return resolved


def flatten(principal, resource):
    fields = {
        "principal.id": principal.get("id"),
        "principal.roles": sorted(principal.get("roles") or []),
        "resource.kind": resource.get("kind"),
    }
    for side, value in (("principal", principal), ("resource", resource)):
        for key in ("scope", "policyVersion"):
            fields[f"{side}.{key}"] = value.get(key, ABSENT)
        for key, attr in (value.get("attr") or {}).items():
            fields[f"{side}.attr.{key}"] = attr
    return fields


def differences(left, right):
    keys = set(left) | set(right)
    return {
        key: (left.get(key, ABSENT), right.get(key, ABSENT))
        for key in sorted(keys)
        if left.get(key, ABSENT) != right.get(key, ABSENT)
    }


def executed(report):
    """Yield (suite file, test name, principal key, resource key, action, effect)."""
    for suite in report.get("suites", []):
        for case in suite.get("testCases", []):
            for principal in case.get("principals", []):
                for resource in principal.get("resources", []):
                    for action in resource.get("actions", []):
                        details = action.get("details", {})
                        if details.get("result") != "RESULT_PASSED":
                            continue
                        effect = details.get("success", {}).get("effect")
                        yield (
                            suite.get("file"),
                            case.get("name"),
                            principal.get("name"),
                            resource.get("name"),
                            action.get("name"),
                            effect,
                        )


def find(row, assertions):
    return [
        a
        for a in assertions
        if a[2] == row["principal"]
        and a[3] == row["resource"]
        and a[4] == row["action"]
        and a[5] == row["effect"]
        and row.get("suite") in (None, a[0])
        and row.get("test") in (None, a[1])
    ]


def audit(args):
    policies = Path(args.policies)
    plan = load_yaml(Path(args.plan))
    rows = plan.get("rows") or []
    if not rows:
        return ["plan has no rows"]
    by_id = {}
    errors = []
    for row in rows:
        missing = {"id", "principal", "resource", "action", "effect"} - set(row)
        if missing:
            errors.append(f"row {row!r} is missing {sorted(missing)}")
            continue
        if row["effect"] not in EFFECTS:
            errors.append(f"{row['id']}: effect must be EFFECT_ALLOW or EFFECT_DENY")
        if row["id"] in by_id:
            errors.append(f"{row['id']}: duplicate row id")
        by_id[row["id"]] = row
    if errors:
        return errors

    reports = []
    for path in args.report:
        report = json.loads(Path(path).read_text())
        overall = report.get("summary", {}).get("overallResult")
        if overall != "RESULT_PASSED":
            errors.append(f"{path}: overall result is {overall}")
        reports.append((path, list(executed(report))))

    cache = {}
    requests = {}
    passed = set()
    for row in rows:
        for path, assertions in reports:
            matches = find(row, assertions)
            if not matches:
                errors.append(
                    f"FAIL {row['id']}: no passing {row['effect']} assertion for "
                    f"{row['principal']} / {row['resource']} / {row['action']} in {path}"
                )
                continue
            suite_file = matches[0][0]
            resolved = fixtures(policies, suite_file, cache)
            principal = resolved["principals"].get(row["principal"])
            resource = resolved["resources"].get(row["resource"])
            if principal is None or resource is None:
                errors.append(f"FAIL {row['id']}: fixture keys not found for {suite_file}")
                continue
            requests[row["id"]] = flatten(principal, resource)

    for row in rows:
        if row["id"] not in requests:
            continue
        request = requests[row["id"]]
        wrong = {
            path: request.get(path, ABSENT)
            for path, value in (row.get("facts") or {}).items()
            if request.get(path, ABSENT) != (ABSENT if value is None else value)
        }
        if wrong:
            detail = ", ".join(f"{k}={v!r} (planned {row['facts'][k]!r})" for k, v in wrong.items())
            errors.append(f"FAIL {row['id']}: fixture facts differ from the plan: {detail}")
            continue
        line = (
            f"{row['id']}: {request['resource.kind']} {row['action']} "
            f"{row['principal']} / {row['resource']} -> {row['effect']}"
        )
        control_id = row.get("control")
        if control_id is None:
            if "change" in row:
                errors.append(f"FAIL {line}; `change` needs a `control`")
            else:
                print(f"PASS {line}")
                passed.add(row["id"])
            continue
        control = by_id.get(control_id)
        change = row.get("change")
        if control is None or control_id not in requests:
            errors.append(f"FAIL {line}; control {control_id!r} is not a passing row")
            continue
        if not isinstance(change, str):
            errors.append(f"FAIL {line}; `change` must name exactly one field")
            continue
        problems = []
        if control["effect"] == row["effect"]:
            problems.append(f"control {control_id} has the same effect")
        if control["action"] != row["action"]:
            problems.append(f"control {control_id} uses action {control['action']}")
        diff = differences(requests[control_id], request)
        diff.pop("resource.id", None)
        if set(diff) != {change}:
            detail = ", ".join(f"{k}: {a!r} -> {b!r}" for k, a, b in
                               ((k, *v) for k, v in diff.items())) or "nothing"
            problems.append(f"expected only {change} to differ, found {detail}")
        if problems:
            errors.append(f"FAIL {line}; " + "; ".join(problems))
        else:
            before, after = diff[change]
            print(f"PASS {line}; vs {control_id}: {change} {before!r} -> {after!r}")
            passed.add(row["id"])

    for path in plan.get("paths") or []:
        for prerequisite in path.get("requires") or []:
            isolated = [
                row["id"]
                for row in rows
                if row.get("path") == path.get("id")
                and row.get("prerequisite") == prerequisite
                and row.get("control")
                and row["id"] in passed
                and requests[row["id"]]["resource.kind"] == path.get("kind")
            ]
            label = f"path {path.get('id')} ({path.get('kind')}) prerequisite {prerequisite}"
            if isolated:
                print(f"PASS {label}: {', '.join(isolated)}")
            else:
                errors.append(f"FAIL {label}: no passing isolated row with a control")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--policies", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--report", action="append", required=True)
    errors = audit(parser.parse_args())
    for error in errors:
        print(error)
    print("coverage audit " + ("FAILED" if errors else "passed"))
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
