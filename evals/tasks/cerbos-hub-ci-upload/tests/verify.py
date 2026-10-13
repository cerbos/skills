"""Simulate the workflows once, then run every check against the recording."""

import json
import subprocess
import sys
from pathlib import Path

LOGS = Path("/logs/verifier")
LOGS.mkdir(parents=True, exist_ok=True)
(LOGS / "reward.txt").unlink(missing_ok=True)
(LOGS / "reward.json").write_text('{"reward": 0}\n')
(LOGS / "checks.tsv").write_text("")
scores = {}


def run(name):
    try:
        result = subprocess.run(
            [sys.executable, "/tests/checks.py", name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        return result.stdout, result.returncode == 0
    except OSError as error:
        return f"Could not run {name}: {error}\n", False


def check(name):
    output, passed = run(name)
    (LOGS / f"{name}.log").write_text(output)
    print(f"== {name}: {'pass' if passed else 'FAIL'}\n{output}", end="", flush=True)
    scores[name] = int(passed)
    with (LOGS / "checks.tsv").open("a") as log:
        log.write(f"{name}\t{scores[name]}\n")


output, _ = run("simulate")
print(f"== simulate\n{output[-20000:]}", flush=True)

for name in (
    "workflows_valid",
    "pr_passes_valid_policies",
    "pr_catches_compile_error",
    "pr_catches_test_failure",
    "pr_catches_strict_only_failure",
    "no_upload_outside_main",
    "main_uploads_policies",
    "main_uses_store_credential",
):
    check(name)

scores["reward"] = int(all(scores.values()))
(LOGS / "reward.json").write_text(json.dumps(scores, indent=2) + "\n")
raise SystemExit(0 if scores["reward"] else 1)
