# Policy delivery for shipments-api

## Recommendation

Move to **Cerbos Hub** and retire the sidecars. Hub runs managed PDPs for each
environment in Cerbos's cloud, so policy distribution, scaling and upgrades
stop being our problem.

## How it works

- A Hub policy store mirrors `freightline/platform` on `main`, directory
  `policies/`. Every push triggers a build: Hub compiles the policies and runs
  the `*_test.yaml` suites, and a failing test blocks the build.
- One Hub deployment per environment (dev, staging, prod). Each deployment
  exposes a hosted PDP endpoint (`<deployment-id>.pdp.cerbos.cloud:443`), and
  Hub evaluates our authorization checks there, so the latest bundle is always
  what answers.
- The Go service changes its Cerbos client address from `localhost:3593` to
  the environment's hosted endpoint and authenticates with the deployment
  client credential.
- Rollback and freeze are on each deployment: one click re-deploys the
  previous build.
- Before the first upload the policies must be converted to Hub's bundle
  format with `cerbosctl hub convert`, since Hub does not read plain
  open-source policy YAML.

## How it fixes the problems

- No API release for policy fixes: the hosted PDP updates itself.
- No drift: each environment's endpoint always serves its deployment's latest
  build, visible in Hub.
- Tests run on every change and failures block the build.
- Rollback is a Hub action that takes seconds.

## What changes

- Delete the `cerbos` sidecar container from `shipments-api.yaml` and the
  `shipments-pdp` image build from `release.yaml`.
- The API pods need outbound access to the Hub endpoint, and we accept the
  extra network hop for each check.
- Hub's change-approval workflow replaces our manual promotion: a staging
  build is promoted to prod once two approvers sign it off in Hub.

## Next steps

1. Convert the policies with `cerbosctl hub convert` and add tests.
2. Create the store and the three deployments.
3. Point the Go SDK at the dev hosted endpoint, then staging, then prod.
4. Remove the sidecars and the PDP image build.
5. Configure the approval workflow on the prod deployment.
