FROM ghcr.io/cerbos/cerbos:0.55.0@sha256:4b9d3b58c4f11c1b8953bc798d8d086e64f276882253ab169625fddc7f432515 AS cerbos
FROM ghcr.io/cerbos/cerbosctl:0.55.0@sha256:76f13b6ef5cc872c1daacc747fbec2a515b256711956acda27035d891d6413da AS cerbosctl

# python:3.12-slim-bookworm
FROM python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir PyYAML==6.0.2

COPY --from=cerbos /cerbos /usr/local/bin/cerbos
COPY --from=cerbosctl /cerbosctl /usr/local/bin/cerbosctl
RUN cerbos --version && cerbosctl hub store --help >/dev/null

WORKDIR /workspace

COPY workspace/ /workspace/
RUN git config --global user.name "Billing Dev" \
    && git config --global user.email "dev@billing.example" \
    && git config --global init.defaultBranch main \
    && git config --global --add safe.directory '*' \
    && git init -q \
    && git add -A \
    && git commit -q -m "Billing service with invoice policies"
