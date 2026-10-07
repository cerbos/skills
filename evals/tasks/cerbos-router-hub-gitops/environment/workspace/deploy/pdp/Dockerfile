# Built by .github/workflows/release.yaml on every API release.
FROM ghcr.io/cerbos/cerbos:0.55.0
COPY policies/ /policies/
COPY deploy/pdp/.cerbos.yaml /config/.cerbos.yaml
CMD ["server", "--config=/config/.cerbos.yaml"]
