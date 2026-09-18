#!/usr/bin/env bash
set -euo pipefail
mkdir -p /workspace/policies
cp -R "$(dirname "$0")/policies/." /workspace/policies/
