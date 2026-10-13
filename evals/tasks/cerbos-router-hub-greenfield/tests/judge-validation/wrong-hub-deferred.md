# Authorization for Rosterly

## Recommendation

Start with the open-source Cerbos PDP and adopt Cerbos Hub later, when the
roadmap actually needs it.

- Write the rules in `docs/permissions.md` as Cerbos policies with
  `*_test.yaml` suites in a `policies/` git repository, and run
  `cerbos compile` on every pull request in CI.
- Run the stock `ghcr.io/cerbos/cerbos:0.55.0` image as a second container in
  the `schedules-api` ECS task with the `git` storage driver, polling the
  repository's `main` branch, so merged policy changes reach the PDP without an
  API release.
- `schedules-api` calls it on `localhost` with `@cerbos/grpc` (`checkResource`
  / `isAllowed`) before every protected action, returning 403 on deny.

The open-source PDP runs standalone with no account, and the policies are the
same ones Hub would use: moving to Hub later is a PDP configuration change
(`storage.driver: hub` and a deployment credential), not a rewrite.

## When to add Hub

- **Q1 dashboard:** if we want an embedded PDP in the browser, that needs Hub;
  otherwise return a permissions map from the API with `checkResources`.
- **Q3 SOC 2:** Hub audit log collection gives searchable decision history
  with masking. Revisit when the audit starts.
- Until then one PDP per environment reading git is enough for five
  engineers, and Hub would be one more thing to set up.

## Leave until later

- Cerbos Hub (see above).
- Scoped per-customer policies, `PlanResources`.

## Next steps

1. Write the policies and tests; run `cerbos compile`; add the CI job.
2. Add the PDP container with the `git` driver to the ECS task definition.
3. Add `@cerbos/grpc` checks to every route.
4. In Q1, decide between the API permissions map and Hub's embedded PDP.
5. In Q3, evaluate Hub for audit collection.
