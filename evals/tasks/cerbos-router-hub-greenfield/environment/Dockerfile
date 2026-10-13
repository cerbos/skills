FROM ghcr.io/cerbos/cerbos:0.55.0@sha256:4b9d3b58c4f11c1b8953bc798d8d086e64f276882253ab169625fddc7f432515 AS cerbos

# node:22-bookworm-slim (Node 22.23.3), only to run the judge's Codex CLI
FROM node:22-bookworm-slim@sha256:43ac6c60b8f89723f746e8a92ce91abd5017e627ce1ddfe4238355d3a30b772c AS node

# python:3.12-slim-bookworm
FROM python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir PyYAML==6.0.2

COPY --from=cerbos /cerbos /usr/local/bin/cerbos
RUN cerbos --version
ENV CERBOS_NO_TELEMETRY=1

# Verifier-only judge tooling, kept off the agent's PATH: Reward Kit and the
# Codex CLI it drives as the judge.
COPY --from=node /usr/local/bin/node /opt/judge/node/bin/node
COPY judge-requirements.txt /opt/judge-requirements.txt
RUN python -m venv /opt/rewardkit \
    && /opt/rewardkit/bin/pip install --no-cache-dir -r /opt/judge-requirements.txt
COPY --from=node /usr/local/lib/node_modules/npm /opt/judge/node/lib/node_modules/npm
RUN PATH=/opt/judge/node/bin:$PATH node /opt/judge/node/lib/node_modules/npm/bin/npm-cli.js \
       install --prefix /opt/judge --no-audit --no-fund @openai/codex@0.157.0 \
    && PATH=/opt/judge/node/bin:$PATH /opt/judge/node_modules/.bin/codex --version

WORKDIR /workspace
COPY workspace/ /workspace/
