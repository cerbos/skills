# Policy delivery for shipments-api

## Recommendation

Fix the delivery problem with the open-source PDP's built-in features first.
Policies stay in git with PR review; a CI job tests them; the sidecars load
them from a versioned object-storage bucket rather than from the image.

## Design

- **Test gate.** A GitHub Actions job runs `cerbos compile policies/` on every
  pull request that touches `policies/`. `cerbos compile` compiles every policy
  and runs the `*_test.yaml` suites, so a failing test blocks the merge.
- **Publishing.** On merge, CI uploads the `policies/` directory to
  `s3://freightline-policies/<environment>/`, starting with dev. Promoting to
  staging and prod is a manual workflow run that copies the same commit's files
  to the next prefix.
- **PDPs.** The sidecars switch to the stock Cerbos image with
  `storage.driver: blob`, the bucket URL for their environment, and
  `updatePollInterval: 30s`. They pick up a new upload without restarting.
- **Rollback.** Re-run the publish workflow for the previous commit. Enable
  bucket versioning as a fallback.

## How it fixes the problems

- Policy fixes ship without an API release.
- Each environment's prefix holds a known commit, recorded by CI.
- Tests block bad merges.
- Rollback is a re-publish, a few minutes.

## Later: Cerbos Hub

Cerbos Hub could replace the CI job and bucket later on: a policy store,
deployments per environment, signed bundles and rollback in the console. It is
an option to evaluate next year once the pipeline above is stable; nothing in
this design depends on it.

## Next steps

1. Add `_test.yaml` suites, including a driver denied `cancel`.
2. Add the CI test job as a required check.
3. Create the bucket and the publish/promote workflows.
4. Switch the sidecars to the `blob` driver in dev, then staging, then prod.
5. Remove the policy copy from the PDP image.
