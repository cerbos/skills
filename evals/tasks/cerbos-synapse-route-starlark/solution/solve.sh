#!/usr/bin/env bash
set -euo pipefail
here="$(dirname "$0")"
mkdir -p /workspace/extensions
cp "$here/config.yaml" /workspace/config.yaml
cp -R "$here/extensions/." /workspace/extensions/
