"""Merge deterministic and judged checks into one reward.json.

Each judged criterion in tests/judge/judge.toml becomes its own binary key,
passing when a majority of the three judge runs pass it. A run that did not
score a criterion (crash, timeout, missing output) counts as a fail.
"""

import json
import tomllib
from pathlib import Path

LOGS = Path("/logs/verifier")
RUBRIC = Path("/tests/judge/judge.toml")
RUNS = sorted((LOGS / "judge").glob("run*/reward-details.json"))
JUDGE_RUNS = 3


def judged_scores() -> dict[str, int]:
    """Majority verdict per criterion over the judge runs; a missing verdict is a fail."""
    names = [c["name"] for c in tomllib.loads(RUBRIC.read_text())["criterion"]]
    verdicts: dict[str, list[tuple[bool, str]]] = {name: [] for name in names}
    for details in RUNS:
        found = {}
        for detail in json.loads(details.read_text()).values():
            for criterion in detail.get("criteria", []):
                found[criterion.get("name")] = criterion
        for name in names:
            criterion = found.get(name)
            passed = criterion is not None and float(criterion.get("value") or 0) >= 1.0
            verdicts[name].append((passed, (criterion or {}).get("reasoning") or "no score"))
    scores = {}
    for name in names:
        votes = verdicts[name]
        passed = sum(p for p, _ in votes) * 2 > JUDGE_RUNS
        scores[name] = int(passed)
        lines = [f"run {i + 1}: {'PASS' if p else 'FAIL'}: {r}" for i, (p, r) in enumerate(votes)]
        if not votes:
            lines = ["judge produced no score for this criterion; see judge-run*.log"]
        tally = f"{sum(p for p, _ in votes)}/{JUDGE_RUNS}"
        (LOGS / f"{name}.log").write_text(f"{'PASS' if passed else 'FAIL'} (judge, {tally} runs)\n" + "\n".join(lines) + "\n")
    return scores


def main() -> None:
    deterministic_path = LOGS / "deterministic.json"
    # verify.py seeds every deterministic check at 0 before running any, so a
    # missing file means the verifier itself never ran.
    if deterministic_path.is_file():
        scores = json.loads(deterministic_path.read_text())
    else:
        scores = {"deterministic_verifier": 0}
    judged = judged_scores()
    with (LOGS / "checks.tsv").open("a") as log:
        for name, score in judged.items():
            log.write(f"{name}\t{score}\n")
    scores.update(judged)
    scores["reward"] = int(bool(scores) and all(scores.values()))
    (LOGS / "reward.json").write_text(json.dumps(scores, indent=2) + "\n")
    print(json.dumps(scores, indent=2))


if __name__ == "__main__":
    main()
