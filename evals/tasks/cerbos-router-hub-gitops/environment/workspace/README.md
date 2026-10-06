# Freightline platform

Freightline tracks parcels for regional carriers. The `shipments-api` (Go) runs
on Kubernetes in three clusters: `dev`, `staging` and `prod` (12 replicas in
prod, across two regions).

Authorization has run on the open-source Cerbos PDP for about a year:

- Policies live in `policies/` in this repository (GitHub,
  `freightline/platform`) and are reviewed in pull requests.
- `deploy/pdp/Dockerfile` bakes them into a PDP image, built by the same
  release workflow as the API (`.github/workflows/release.yaml`).
- Every `shipments-api` pod runs that image as a sidecar on `localhost:3593`
  (`deploy/k8s/shipments-api.yaml`); the Go service calls it with the Cerbos Go
  SDK.

The release workflow promotes one image tag through dev, staging and prod by
hand, so each cluster runs whatever tag was last promoted there. See
`docs/incident-2026-08-14.md` for what went wrong last quarter.
