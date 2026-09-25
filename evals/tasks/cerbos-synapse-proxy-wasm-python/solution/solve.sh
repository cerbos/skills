#!/usr/bin/env bash
set -euo pipefail
here="$(dirname "$0")"
mkdir -p /workspace/extensions
cp "$here/config.yaml" /workspace/config.yaml
cp -R "$here/extensions/." /workspace/extensions/
# No host functions are imported, so the pdk-shim merge step is unnecessary.
extism-py /workspace/extensions/enrich/enrich_principal.py -o /workspace/extensions/enrich_principal.wasm
