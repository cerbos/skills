#!/usr/bin/env bash
set -euo pipefail
here="$(dirname "$0")"
cp "$here/app/app.py" /workspace/app/app.py
cp "$here/FINDINGS.md" /workspace/FINDINGS.md
