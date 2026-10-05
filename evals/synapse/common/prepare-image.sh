#!/usr/bin/env bash
# Pull the licensed Synapse image once and tag it locally for the Synapse tasks' Dockerfiles.
# Usage: CERBOS_DISTRIBUTION_REPO=<your distribution repository> ./prepare-image.sh
set -euo pipefail

: "${CERBOS_DISTRIBUTION_REPO:?Set CERBOS_DISTRIBUTION_REPO to the repository URL issued with your Synapse licence}"
VERSION=0.10.2
INDEX=sha256:8a0893315b860a68c8a568a54ce5826843b74673fdf9a71cd075460f66ac6bc8
# linux/amd64 manifest inside INDEX: the Python WASM tasks build amd64 images because
# extism-py ships for x86_64 only.
AMD64=sha256:067001eec16764dac51128c9265f337e71e1f1267886fe8662c260bfa26cf2c1
IMAGE="$CERBOS_DISTRIBUTION_REPO/synapse/synapse"

docker pull "$IMAGE:$VERSION@$INDEX"
docker tag "$IMAGE:$VERSION@$INDEX" "localhost/cerbos-synapse:$VERSION"
docker pull --platform linux/amd64 "$IMAGE@$AMD64"
docker tag "$IMAGE@$AMD64" "localhost/cerbos-synapse:$VERSION-amd64"
echo "Tagged localhost/cerbos-synapse:$VERSION and localhost/cerbos-synapse:$VERSION-amd64"
