#!/usr/bin/env bash
set -euo pipefail
cp -R /solution/policies/. /workspace/policies/
cerbos compile /workspace/policies
cerbos compile --strict-evaluation /workspace/policies
