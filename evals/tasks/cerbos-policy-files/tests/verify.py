"""Run all nine checks, keeping a score and log for each one."""

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


def check(name, *command):
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        output, passed = result.stdout, result.returncode == 0
    except OSError as error:
        output, passed = f'Could not run {name}: {error}\n', False
    (LOGS / f'{name}.log').write_text(output)
    print(output, end='', flush=True)
    scores[name] = int(passed)
    with (LOGS / 'checks.tsv').open('a') as log:
        log.write(f'{name}\t{scores[name]}\n')


check('files', sys.executable, '/tests/check_outputs.py', 'files')
check('folder_structure', sys.executable, '/tests/check_outputs.py', 'folder_structure')
check('resource_policies', sys.executable, '/tests/check_outputs.py', 'resource_policies')
check('schemas', sys.executable, '/tests/check_outputs.py', 'schemas')
check('fixtures', sys.executable, '/tests/check_outputs.py', 'fixtures')
check('compile_normal', 'cerbos', 'compile', '--output=json', '/workspace/policies')
check('generated_tests', sys.executable, '/tests/check_outputs.py', 'generated_tests')
check('compile_strict', 'cerbos', 'compile', '--strict-evaluation', '/workspace/policies')
check('pdp_decisions', sys.executable, '/tests/check_resources.py')

scores['reward'] = int(all(scores.values()))
(LOGS / 'reward.json').write_text(json.dumps(scores, indent=2) + '\n')
raise SystemExit(0 if scores['reward'] else 1)
