"""Run every check, keeping a score and log for each one."""

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


def check(name, *command):
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        output, passed = result.stdout, result.returncode == 0
    except OSError as error:
        output, passed = f"Could not run {name}: {error}\n", False
    (LOGS / f"{name}.log").write_text(output)
    print(f"== {name}: {'pass' if passed else 'FAIL'}\n{output}", end="", flush=True)
    scores[name] = int(passed)
    with (LOGS / "checks.tsv").open("a") as log:
        log.write(f"{name}\t{scores[name]}\n")


for name in (
    "compose_preserved",
    "config_preserved",
    "hub_storage",
    "secrets_out_of_files",
    "pdp_hub_handshake",
):
    check(name, sys.executable, "/tests/checks.py", name)

scores["reward"] = int(all(scores.values()))
(LOGS / "reward.json").write_text(json.dumps(scores, indent=2) + "\n")
raise SystemExit(0 if scores["reward"] else 1)
