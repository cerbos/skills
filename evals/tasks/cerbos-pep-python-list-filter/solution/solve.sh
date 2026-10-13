#!/usr/bin/env bash
set -euo pipefail
cp "$(dirname "$0")/app/authz.py" "$(dirname "$0")/app/main.py" /workspace/app/
