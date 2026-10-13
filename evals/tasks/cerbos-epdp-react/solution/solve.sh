#!/usr/bin/env bash
# Reference change: an embedded PDP shapes the UI; the API keeps its service PDP.
set -euo pipefail
here="$(dirname "$0")"
cd /workspace/app
cp "$here"/app/src/* src/
# Declare the SDK packages the browser code now imports; they are already in
# node_modules and the npm cache, so this also updates the lockfile offline.
npm install --prefer-offline --no-audit --no-fund --save-exact \
  @cerbos/embedded-client@0.8.1 @cerbos/embedded-server@0.7.2 @cerbos/react@0.5.1
npm run build
