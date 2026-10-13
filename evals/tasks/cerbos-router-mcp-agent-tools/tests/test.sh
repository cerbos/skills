#!/usr/bin/env bash
# Deterministic sanity check, then the Codex judge three times, merged into one reward.json.
set -uo pipefail
mkdir -p /logs/verifier/judge
python3 /tests/verify.py
# Three independent judge runs in parallel; merge.py takes the majority verdict per criterion,
# so one noisy verdict on a borderline answer cannot flip the reward.
for run in 1 2 3; do
  mkdir -p /logs/verifier/judge/run$run
  PATH="/opt/judge/node_modules/.bin:/opt/judge/node/bin:$PATH" /opt/rewardkit/bin/rewardkit /tests/judge \
    --workspace /workspace --output /logs/verifier/judge/run$run/reward.json \
    > /logs/verifier/judge-run$run.log 2>&1 || echo "judge run $run exited non-zero; see judge-run$run.log" &
done
wait
python3 /tests/merge.py
