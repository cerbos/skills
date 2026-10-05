#!/usr/bin/env bash
set -euo pipefail
here="$(dirname "$0")"
mkdir -p /workspace/extensions
cp "$here/config.yaml" /workspace/config.yaml
cp -R "$here/extensions/." /workspace/extensions/
cd /workspace/extensions/access
GOOS=wasip1 GOARCH=wasm go build -buildmode=c-shared -o /workspace/extensions/document_access.wasm .
