"""The policies ship with native test suites that actually exercise the migrated rules."""

import json
from pathlib import Path

REPORT = Path("/logs/verifier/compile_normal.log")
MIN_ASSERTIONS = 12
MIN_ACTIONS = 5


def main():
    try:
        report = json.loads(REPORT.read_text())
    except (OSError, ValueError) as error:
        raise SystemExit(f"No JSON test report from compile_normal: {error}")
    suites = report.get("suites") or []
    if not suites:
        raise SystemExit("No *_test.yaml suites ran under /workspace/policies")
    effects, actions, total = set(), set(), 0
    for suite in suites:
        if suite.get("summary", {}).get("overallResult") != "RESULT_PASSED":
            raise SystemExit(f"Suite did not pass: {suite.get('file')}")
        for case in suite.get("testCases") or []:
            for principal in case.get("principals") or []:
                for resource in principal.get("resources") or []:
                    for action in resource.get("actions") or []:
                        details = action.get("details") or {}
                        if details.get("result") != "RESULT_PASSED":
                            continue
                        total += 1
                        actions.add(action.get("name"))
                        effects.add((details.get("success") or {}).get("effect"))
    print(f"{len(suites)} suites, {total} passing assertions, actions {sorted(actions)}, effects {sorted(effects)}")
    if total < MIN_ASSERTIONS:
        raise SystemExit(f"Expected at least {MIN_ASSERTIONS} passing assertions")
    if len(actions) < MIN_ACTIONS:
        raise SystemExit(f"Expected tests across at least {MIN_ACTIONS} actions")
    if not {"EFFECT_ALLOW", "EFFECT_DENY"} <= effects:
        raise SystemExit("Tests must assert both allowed and denied decisions")
    print("PASS: generated_tests")


if __name__ == "__main__":
    main()
