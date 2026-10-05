FROM ghcr.io/cerbos/cerbos:0.55.0@sha256:4b9d3b58c4f11c1b8953bc798d8d086e64f276882253ab169625fddc7f432515 AS cerbos

# node:22-bookworm-slim (Node 22.23.3)
FROM node:22-bookworm-slim@sha256:43ac6c60b8f89723f746e8a92ce91abd5017e627ce1ddfe4238355d3a30b772c AS node

# python:3.12-slim-bookworm
FROM python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl git \
    && rm -rf /var/lib/apt/lists/*

COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && node --version && npm --version

COPY --from=cerbos /cerbos /usr/local/bin/cerbos
RUN cerbos --version
ENV CERBOS_NO_TELEMETRY=1

# Verifier-only judge tooling, kept off the agent's PATH: Reward Kit and the
# Codex CLI it drives as the judge.
COPY judge-requirements.txt /opt/judge-requirements.txt
RUN python -m venv /opt/rewardkit \
    && /opt/rewardkit/bin/pip install --no-cache-dir -r /opt/judge-requirements.txt
RUN npm install --prefix /opt/judge --no-audit --no-fund @openai/codex@0.157.0 \
    && /opt/judge/node_modules/.bin/codex --version

WORKDIR /workspace
COPY cerbos/ /workspace/cerbos/
COPY app/ /workspace/app/

# The app's own dependencies from the lockfile, plus the Cerbos browser SDK
# packages at pinned versions (present in node_modules and the npm cache, not yet
# declared in package.json).
RUN cd /workspace/app \
    && npm ci --no-audit --no-fund \
    && npm install --no-save --no-audit --no-fund \
       @cerbos/embedded-client@0.8.1 @cerbos/embedded-server@0.7.2 @cerbos/react@0.5.1 \
    && npm run build && rm -rf dist
