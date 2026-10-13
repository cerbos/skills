#!/bin/bash
set -e
bash /solution/solve.sh
cp /tests/judge-validation/no-api/index.mjs /workspace/app/server/index.mjs
