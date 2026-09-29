"""Run every check in checks.py, keeping a score and log for each one."""

import json
from pathlib import Path
import subprocess
import sys

LOGS = Path('/logs/verifier')
LOGS.mkdir(parents=True, exist_ok=True)
(LOGS / 'reward.txt').unlink(missing_ok=True)
(LOGS / 'reward.json').write_text('{"reward": 0}\n')
(LOGS / 'checks.tsv').write_text('')
scores = {}


def check(name):
    try:
        result = subprocess.run(
            [sys.executable, '/tests/checks.py', name],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=240,
        )
        output, passed = result.stdout, result.returncode == 0
    except (OSError, subprocess.TimeoutExpired) as error:
        output, passed = f'Could not run {name}: {error}\n', False
    (LOGS / f'{name}.log').write_text(output)
    print(output, end='', flush=True)
    scores[name] = int(passed)
    with (LOGS / 'checks.tsv').open('a') as log:
        log.write(f'{name}\t{scores[name]}\n')


sys.path.insert(0, '/tests')
from checks import CHECKS  # noqa: E402

for name in CHECKS:
    check(name)

scores['reward'] = int(all(scores.values()))
(LOGS / 'reward.json').write_text(json.dumps(scores, indent=2) + '\n')
raise SystemExit(0 if scores['reward'] else 1)
