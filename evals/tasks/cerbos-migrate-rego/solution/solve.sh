#!/usr/bin/env bash
# Reference translation of opa/expenses.rego into Cerbos policies with a test suite.
set -euo pipefail
mkdir -p /workspace/policies
cp -R "$(dirname "$0")/policies/." /workspace/policies/
