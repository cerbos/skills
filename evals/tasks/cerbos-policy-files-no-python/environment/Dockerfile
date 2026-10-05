FROM ghcr.io/cerbos/cerbos:0.55.0@sha256:4b9d3b58c4f11c1b8953bc798d8d086e64f276882253ab169625fddc7f432515 AS cerbos

# python:3.12-slim-bookworm
FROM python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254

# ripgrep is preinstalled with Node below so Harbor's agent setup finds every
# command it needs and never runs `apt-get install npm`, which would pull in
# Debian's python3.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl git ripgrep \
    && rm -rf /var/lib/apt/lists/*

# Official Node.js build (bundles npm; no Python dependency).
ARG NODE_VERSION=22.23.3
RUN set -eu; \
    case "$(dpkg --print-architecture)" in \
      amd64) arch=x64; sha=1084aa36196bba4c3a5e69a1ee388a6e4ff729dad09445fbcd434b28fe3c24af ;; \
      arm64) arch=arm64; sha=5ced2d48d1d7198739b7f86804de0171aefb6823b684b12341d3321afc3cb0b2 ;; \
      *) echo "unsupported architecture" >&2; exit 1 ;; \
    esac; \
    curl -fsSLo /tmp/node.tar.gz "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-${arch}.tar.gz"; \
    echo "${sha}  /tmp/node.tar.gz" | sha256sum -c -; \
    tar -xzf /tmp/node.tar.gz -C /usr/local --strip-components=1 --no-same-owner \
      --exclude=CHANGELOG.md --exclude=LICENSE --exclude=README.md; \
    rm /tmp/node.tar.gz; \
    node --version; npm --version

RUN pip install --no-cache-dir PyYAML==6.0.2

COPY --from=cerbos /cerbos /usr/local/bin/cerbos
RUN cerbos --version

# Hide Python from the agent. The interpreter moves out of PATH for the verifier
# (tests/test.sh); every other entry point is removed, and apt may not install
# a replacement python.
RUN set -eu; \
    mkdir -p /usr/local/libexec; \
    mv /usr/local/bin/python3.12 /usr/local/libexec/verifier-python; \
    rm -f /usr/local/bin/python* /usr/local/bin/pip* /usr/local/bin/pydoc* \
      /usr/local/bin/idle* /usr/local/bin/2to3*; \
    printf 'Package: python* libpython* pypy*\nPin: release *\nPin-Priority: -1\n' \
      > /etc/apt/preferences.d/no-python; \
    /usr/local/libexec/verifier-python -c 'import json, yaml, sys; print(sys.version.split()[0], yaml.__version__)'; \
    if ls /usr/bin/python* /usr/local/bin/python* /usr/local/bin/pip* 2>/dev/null; then exit 1; fi; \
    if command -v python3 || command -v python || command -v pip || command -v pip3; then exit 1; fi

WORKDIR /workspace
