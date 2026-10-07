#!/bin/bash
set -e
bash /solution/solve.sh
rm /workspace/app/src/cerbos.ts
cp /tests/judge-validation/per-render/App.tsx /workspace/app/src/
