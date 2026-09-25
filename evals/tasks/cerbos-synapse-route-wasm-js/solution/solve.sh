#!/usr/bin/env bash
set -euo pipefail
here="$(dirname "$0")"
mkdir -p /workspace/extensions
cp "$here/config.yaml" /workspace/config.yaml
cp -R "$here/extensions/." /workspace/extensions/
cd /workspace/extensions/access
npm install --prefer-offline --no-audit --no-fund
npm run build
