# Policy delivery for shipments-api

## Recommendation

Decouple policies from the API image with a self-managed GitOps pipeline built
on the open-source PDP's own features. Policies stay in `policies/` with
pull-request review; a new GitHub Actions workflow tests them; the sidecars read
them straight from git with the PDP's `git` storage driver.

## Pipeline

- New workflow `policies.yaml`, triggered on pull requests that touch
  `policies/`: download the Cerbos binary and run `cerbos compile policies/`,
  which compiles every policy and runs every `*_test.yaml` suite. Make it a
  required status check so a failing test blocks the merge.
- Environments are branches: `env/dev`, `env/staging` and `env/prod`.
  Promoting a policy is a fast-forward merge from one branch to the next,
  done by a second workflow with a manual approval on the prod environment.

## PDPs

- Change `deploy/pdp/.cerbos.yaml` to `storage.driver: git` with the
  repository URL, `branch: env/<environment>`, `subDir: policies`,
  `checkoutDir: /tmp/policies` and `updatePollInterval: 30s`, plus a read-only
  deploy key mounted from a Kubernetes secret.
- Each sidecar polls the branch and recompiles when it changes, so policy
  changes reach every pod within about a minute without an API release.
- The sidecar becomes the stock Cerbos image, and the `shipments-pdp` image
  build is removed from `release.yaml`.

## How it fixes the problems

- Policy fixes no longer need an API release: the sidecars pull from git.
- Drift is visible: each environment is exactly the head of its branch.
- Tests gate every merge in CI.
- Rollback is `git revert` on the environment branch; the sidecars pick it up
  on their next poll, a couple of minutes instead of 47.

## What about Cerbos Hub?

Hub is a hosted alternative, but everything we need is available from the
open-source PDP and GitHub Actions we already run, so we do not need it.

## Next steps

1. Write `_test.yaml` suites, including a driver denied `cancel`.
2. Add the `policies.yaml` CI workflow and make it a required check.
3. Create the three environment branches and the promotion workflow.
4. Create a deploy key and the Kubernetes secrets.
5. Switch the sidecar config to the `git` driver, dev first, then staging,
   then prod.
6. Remove the policy copy from the PDP image build.
