"""Prove variables affect authorization, rather than decorating inline conditions."""

import copy
import json
import re
import shutil
import tempfile
from pathlib import Path

import check_resources as runtime
import yaml

suite = json.loads(runtime.CASES.read_text())
original = runtime.POLICIES
records = []


def decisions(store, expected):
    runtime.POLICIES = store
    attempt = []
    try:
        for strict in (False, True):
            runtime.run_mode(expected, strict, attempt)
    except RuntimeError as error:
        print(f"Candidate variable is not a numeric limit: {error}")
        return False
    finally:
        records.extend(attempt)
    return len(attempt) == 2 * len(expected["cases"]) and all(
        item["passed"] for item in attempt
    )


with tempfile.TemporaryDirectory(prefix="variable-effects-") as directory:
    store = Path(directory) / "shared"
    shutil.copytree(original, store)
    path = store / "exported_variables/common_vars.yaml"
    doc = yaml.safe_load(path.read_text())
    definitions = doc["exportVariables"]["definitions"]
    for name, expression in definitions.items():
        if re.search(r"\bV\.", str(expression)):
            definitions[name] = "false"
    path.write_text(yaml.safe_dump(doc))
    expected = copy.deepcopy(suite)
    for case in expected["cases"]:
        case["expected"]["approve"] = "EFFECT_DENY"
        case["expected"]["view"] = "EFFECT_DENY"
    shared_passed = decisions(store, expected)

    # Try individual locals: helper variables may legitimately be booleans.
    # A numeric limit must be independently replaceable without changing view.
    local_passed = {}
    for source in original.rglob("*.yaml"):
        doc = yaml.safe_load(source.read_text())
        if not isinstance(doc, dict) or "resourcePolicy" not in doc:
            continue
        policy = doc["resourcePolicy"]
        kind = policy["resource"]
        expected = copy.deepcopy(suite)
        expected["cases"] = [
            case
            for case in expected["cases"]
            if expected["resources"][case["resource"]]["kind"] == kind
        ]
        if not expected["cases"]:
            continue
        for case in expected["cases"]:
            case["expected"]["approve"] = "EFFECT_DENY"
        local_passed[kind] = False
        for index, name in enumerate(policy["variables"]["local"]):
            store = Path(directory) / f"{kind}-{index}"
            shutil.copytree(original, store)
            changed = copy.deepcopy(doc)
            changed["resourcePolicy"]["variables"]["local"][name] = "-1"
            (store / source.relative_to(original)).write_text(yaml.safe_dump(changed))
            if decisions(store, expected):
                local_passed[kind] = True
                break

runtime.POLICIES = original
(runtime.LOGS / "variable-effects.json").write_text(
    json.dumps(records, indent=2) + "\n"
)
assert shared_passed, "Shared eligibility does not control every grant"
assert local_passed == {"invoice": True, "expense": True}, (
    "Local numeric limits do not control approvals independently of view"
)
