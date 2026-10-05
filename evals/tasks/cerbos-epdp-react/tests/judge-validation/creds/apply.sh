#!/bin/bash
set -e
bash /solution/solve.sh
cp /tests/judge-validation/creds/cerbos.ts /workspace/app/src/cerbos.ts
cp /tests/judge-validation/creds/env /workspace/app/.env
cd /workspace/app && npm run build
