#!/usr/bin/env bash
# Reference migration: Cerbos policies with tests, and the app's guards replaced by PDP calls.
set -euo pipefail
here="$(dirname "$0")"
mkdir -p /workspace/policies
cp -R "$here/policies/." /workspace/policies/
cp "$here"/app/*.py /workspace/app/
