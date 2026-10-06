"""Deterministic sanity check: /workspace/DESIGN.md exists and is substantive.

Writes /logs/verifier/deterministic.json; tests/merge.py folds it together with
the judge's scores into reward.json.
"""

import json
import re
from pathlib import Path

LOGS = Path("/logs/verifier")
DESIGN = Path("/workspace/DESIGN.md")
MIN_WORDS = 250

LOGS.mkdir(parents=True, exist_ok=True)
(LOGS / "reward.txt").unlink(missing_ok=True)
(LOGS / "reward.json").write_text('{"reward": 0}\n')
(LOGS / "deterministic.json").write_text('{"design_doc": 0}\n')

if not DESIGN.is_file():
    passed, message = False, f"{DESIGN} does not exist"
else:
    text = DESIGN.read_text(errors="replace")
    words = len(re.findall(r"\w+", text))
    headings = len(re.findall(r"^#{1,6}\s+\S", text, flags=re.MULTILINE))
    passed = words >= MIN_WORDS
    message = f"{DESIGN}: {words} words, {headings} headings (need at least {MIN_WORDS} words)"

(LOGS / "design_doc.log").write_text(f"{'PASS' if passed else 'FAIL'}: {message}\n")
(LOGS / "checks.tsv").write_text(f"design_doc\t{int(passed)}\n")
(LOGS / "deterministic.json").write_text(json.dumps({"design_doc": int(passed)}, indent=2) + "\n")
print(f"design_doc: {'PASS' if passed else 'FAIL'}: {message}")
