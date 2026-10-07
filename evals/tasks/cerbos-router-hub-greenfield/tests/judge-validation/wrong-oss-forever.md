# Authorization for Rosterly

## Recommendation

Keep it simple and fully self-managed with the open-source Cerbos PDP. For one
service and five engineers, there is no reason to take on another vendor.

- Write the rules in `docs/permissions.md` as Cerbos policies in
  `api/policies/`, with `*_test.yaml` suites.
- Run the stock `ghcr.io/cerbos/cerbos:0.55.0` image as a second container in
  the `schedules-api` ECS task, with `storage.driver: disk` and the policies
  copied into a small derived image at build time.
- `schedules-api` calls the PDP on `localhost:3593` with `@cerbos/grpc`
  (`checkResource`), building the principal from the Auth0 token and the
  resource from the shift row, and returns 403 on deny.
- CI runs `cerbos compile api/policies` on every pull request, so failing
  policy tests block the merge.

## Why

- The open-source PDP is complete: policies, tests, the API and audit logging
  all work without an account.
- Policy changes ship with the API release, which we do several times a day
  anyway.

## The roadmap

- **React dashboard:** add a `GET /permissions` endpoint that calls
  `checkResources` for the shifts on screen and returns a permissions map;
  the dashboard hides buttons from it.
- **payroll-export:** a second PDP sidecar with the same image.
- **SOC 2:** turn on the PDP's `file` audit backend to stdout; ECS ships it to
  CloudWatch Logs, where the auditor can query it with Logs Insights. Pull
  requests document how rules change.

Cerbos Hub exists, but it is aimed at large fleets; we do not need it.

## Leave until later

- Per-customer scoped policies.
- `PlanResources` for list filtering.

## Next steps

1. Write the policies and tests; run `cerbos compile`.
2. Add the CI job.
3. Add the PDP container to the ECS task definition.
4. Add `@cerbos/grpc` checks to every route.
5. Turn on the `file` audit backend and CloudWatch retention.
