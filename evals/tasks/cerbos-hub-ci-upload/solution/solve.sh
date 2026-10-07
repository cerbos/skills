#!/usr/bin/env bash
set -euo pipefail
mkdir -p /workspace/.github/workflows
cp "$(dirname "$0")/workflows/policies.yaml" /workspace/.github/workflows/policies.yaml
