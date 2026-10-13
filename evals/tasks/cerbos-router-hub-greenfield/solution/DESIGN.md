# Authorization for Rosterly

## Recommendation

Start on **Cerbos Hub** from day one, with a **service PDP** running next to
`schedules-api` in our own AWS account.

- The rules in `docs/permissions.md` become Cerbos **policies** in a git
  repository, with `*_test.yaml` suites, reviewed in pull requests.
- A Hub **policy store** mirrors that repository. Hub **deployments** for
  `staging` and `prod` compile the policies and run the tests on every change;
  a failing test blocks the build and the previous bundle keeps serving. A
  passing build is pushed as a signed bundle to the connected PDPs within
  seconds.
- The **PDP** is the stock `ghcr.io/cerbos/cerbos:0.55.0` image as a second
  container in the `schedules-api` ECS task, configured with
  `storage.driver: hub`, the environment's deployment ID and a deployment
  client credential from Secrets Manager. It needs outbound HTTPS to Hub only to
  fetch bundles; checks are evaluated in the container, so schedule data never
  leaves our VPC. Hub does not run the PDP for us; it delivers policies to it.
- `schedules-api` calls the PDP on `localhost` with `@cerbos/grpc`
  (`checkResource` / `isAllowed`) before every read and write, building the
  principal from the Auth0 token (`sub`, `roles`, `org_id`, `location_ids`) and
  the resource from the shift row (`orgId`, `locationId`, `status`,
  `assigneeId`, `startsAt`).

## Why Hub now, given the roadmap

- **No platform engineer.** Without Hub we would build and run the policy test
  gate and the distribution to every PDP ourselves. Hub gives us both, plus
  rollback and freeze when a rule goes wrong, and shows which build each PDP
  runs.
- **Rules will keep changing.** "Senior staff approve swaps" and "managers edit
  only 48 hours out" become policy pull requests that reach prod without an API
  release.
- **Q1 React dashboard.** An **embedded PDP** in the browser can hide buttons
  for a few hundred shifts with no round trips, and it exists only with Hub
  (an ePDP rule on the deployment). The API still enforces.
- **Q2 payroll-export.** Its PDP points at the same deployment; its rules are a
  new policy in the same store.
- **Q3 SOC 2.** Hub **audit log collection** gives a searchable record of every
  decision across all PDPs, with sensitive fields masked at the PDP; pull
  requests plus Hub build history show how rules were changed and reviewed.

## Honest trade-offs

The open-source PDP runs fine standalone, reading policies from disk or git,
and needs no account. The policies and the PDP image are identical either way:
moving onto or off Hub is a PDP configuration change, not a rewrite. We choose
Hub because otherwise we would build the pipeline, rollout and audit
collection ourselves.

## Leave until later

- Embedded PDP rule and `@cerbos/embedded-client` — with the dashboard in Q1.
- Audit log collection to Hub — turn on before the SOC 2 window opens (Q2–Q3);
  it needs a Read & write deployment credential and a persistent buffer volume.
- Scoped (per-customer) policies — only when a customer's rules diverge.
- `PlanResources` for list filtering — when list endpoints need it.

## Avoid

- `if` checks in route handlers duplicating `permissions.md`.
- Treating the dashboard's hidden buttons as security.

## Next steps

1. Prototype the `shift` and `schedule` policies in the Hub playground, then
   commit them with test suites to a `policies/` repository and run
   `cerbos compile` (cerbos-policy).
2. In the Hub console, create the policy store connected to that repository,
   then `staging` and `prod` deployments, each with a read-only client
   credential stored in Secrets Manager (cerbos-hub-setup).
3. Add the Cerbos sidecar container to the ECS task definition with
   `storage.driver: hub`; deploy to staging and confirm it appears on the
   deployment's Decision points tab.
4. Add `@cerbos/grpc` to `schedules-api` and check every route listed in
   `permissions.md` before acting, returning 403 on deny
   (cerbos-pep-integration). Then roll out to prod.
5. Q1: ePDP rule and dashboard integration (cerbos-embedded-pdp).
6. Before SOC 2: audit collection with masking (cerbos-audit-insights).
