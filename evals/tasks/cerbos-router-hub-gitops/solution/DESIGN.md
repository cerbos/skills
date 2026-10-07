# Policy delivery for shipments-api

## Recommendation

Keep the policies in `policies/` in git with pull-request review, and put
**Cerbos Hub** between git and the PDPs. A Hub **policy store** mirrors the
repository; a Hub **deployment** per environment compiles and tests every
change and pushes a signed bundle to that environment's sidecar PDPs. The
sidecars stop carrying policies in their image and fetch them from Hub
instead. Nothing else about Cerbos changes: same PDP, same policies, same Go
SDK calls on `localhost:3593`.

## How it fixes each problem

| Problem | With Hub |
| --- | --- |
| A policy fix needs an API release | Policies are no longer in the image. A merged policy change is built by Hub and pushed to the running sidecars within seconds, with no restart and no API deploy. |
| Environments drift; nobody knows what is live | Each environment has its own deployment. Its **Builds** tab shows which build is live and when it went live, and the **Decision points** tab lists every connected PDP with the build it is running and when it was last seen. |
| A bad policy reached prod untested | Hub compiles the policies and runs every `*_test.yaml` suite on every change. A compile or test failure blocks the build, and the previous bundle keeps serving. The August change would have failed a test asserting that drivers cannot `cancel`. |
| Rollback took 47 minutes | **Roll back** on the prod deployment re-deploys the previous build to every PDP in seconds and freezes the deployment so the bad build does not come back. **Freeze** also holds prod during a change window. API code is untouched. |

## What changes and what stays the same

Stays the same:

- The sidecar PDPs keep running in our own clusters, one per API pod; checks
  stay on localhost and request data never leaves our network. Hub distributes
  policies; it does not run our PDPs or evaluate our checks.
- The policy files are reused as they are; nothing is rewritten.
- The Go service and its Cerbos SDK calls.

Changes:

- `deploy/pdp/.cerbos.yaml` switches from the `disk` driver to `storage.driver: hub`
  with `storage.hub.remote.deploymentID` for the environment and a `cacheDir`.
  The deployment's client ID and secret come from a Kubernetes secret as
  `CERBOS_HUB_CLIENT_ID` / `CERBOS_HUB_CLIENT_SECRET`. The PDP needs outbound
  HTTPS to `api.cerbos.cloud` and `cdn.cerbos.cloud`, and keeps serving its
  cached bundle if the connection drops.
- The sidecar becomes the stock `ghcr.io/cerbos/cerbos:0.55.0` image. The
  `shipments-pdp` image build leaves the release workflow, so API and policy
  releases are independent.

## Environments

One store mirrors `main`. Three deployments: dev and staging follow it
directly; prod follows it too but stays **frozen**, and we promote a build to
prod after it has run in staging. Alternatively, give prod its own store on a
`release` branch; either way each environment's version is visible in Hub.

## Avoid

- Building our own CI pipeline plus a git-polling driver on every PDP: we
  would own the test gate, signing and rollback, and each PDP would still
  compile on its own schedule.
- Keeping policies in the application image.

## Next steps

1. Add `_test.yaml` suites for `shipment`, including "a driver cannot cancel"
   (the August regression); run `cerbos compile policies/` locally
   (cerbos-policy).
2. In the Hub console, create a policy store connected to
   `freightline/platform` on `main`, directory `policies/` (cerbos-hub-setup).
3. Create dev, staging and prod deployments on that store, confirm a green
   build, and generate a read-only client credential per deployment; store
   each in that cluster as a Kubernetes secret.
4. Change the sidecar to the stock Cerbos image with `storage.driver: hub` and
   the environment's deployment ID; roll out in dev, check the PDP appears on
   the Decision points tab, then staging, then prod.
5. Remove the `shipments-pdp` build from `release.yaml` and the `COPY policies/`
   Dockerfile.
6. Freeze prod and write the runbook: promote after staging, roll back from the
   Builds tab.
