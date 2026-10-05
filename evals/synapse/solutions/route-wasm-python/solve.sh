#!/usr/bin/env bash
set -euo pipefail
here="$(dirname "$0")"
mkdir -p /workspace/extensions
cp "$here/config.yaml" /workspace/config.yaml
cp -R "$here/extensions/." /workspace/extensions/
# No host functions are imported, so the pdk-shim merge step is unnecessary.
extism-py /workspace/extensions/access/document_access.py -o /workspace/extensions/document_access.wasm
