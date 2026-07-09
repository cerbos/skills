#!/usr/bin/env bash
# Run an eval suite, optionally targeting a SUBSET of cases — for surgical
# iteration on a single failure without paying for the whole suite.
#
# Usage:
#   scripts/eval.sh policy                      # whole policy suite
#   scripts/eval.sh policy multi-role           # only cases whose description matches /multi-role/i
#   scripts/eval.sh synapse envoy               # only synapse envoy cases
#   scripts/eval.sh calibration deny-hole       # only calibration fixtures matching
#   scripts/eval.sh policy --failing policy.json  # rerun ONLY the previous run's failures
#
# The suite is one of: policy | synapse | calibration.
set -euo pipefail
cd "$(dirname "$0")/.."

suite="${1:?usage: eval.sh <policy|synapse|calibration> [pattern | --failing <prior.json>]}"
shift || true

args=(promptfoo eval -c "promptfoo.${suite}.yaml" --no-cache --output "${suite}.json")

if [ "${1:-}" = "--failing" ]; then
  args+=(--filter-failing "${2:?--failing needs a path to a prior *.json}")
elif [ -n "${1:-}" ]; then
  args+=(--filter-pattern "$1")   # matches against the test description (regex)
fi

echo "→ npx ${args[*]}"
exec npx "${args[@]}"
