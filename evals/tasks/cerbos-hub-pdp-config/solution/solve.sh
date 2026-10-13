#!/usr/bin/env bash
set -euo pipefail
cp "$(dirname "$0")/workspace/docker-compose.yaml" /workspace/docker-compose.yaml
cp "$(dirname "$0")/workspace/config.yaml" /workspace/config.yaml
