# Authorization for Rosterly

## Recommendation

Use **Cerbos Hub** from day one. Production Cerbos runs on Hub: the
open-source PDP is a local development tool, and running it in production
without Hub is not supported, so there is no real alternative.

- Write the rules in `docs/permissions.md` as policies with `*_test.yaml`
  suites in a `policies/` repository.
- A Hub policy store mirrors the repository; `staging` and `prod` deployments
  compile and test every change, and a failing test blocks the build.
- Hub runs the PDP for us: each deployment comes with a managed PDP endpoint in
  Cerbos's cloud, so there is no container to add to the ECS task and nothing
  to scale. `schedules-api` calls that endpoint with `@cerbos/http`
  (`checkResource`) and the deployment client credential, and Hub evaluates
  each check.
- Policies must be written in Hub's policy format, which differs from the
  open-source YAML, so start them in the Hub editor rather than in local files.

## Why, given the roadmap

- **No platform engineer:** nothing to run at all — Hub hosts and scales the
  PDP.
- **React dashboard:** the embedded PDP comes with Hub.
- **payroll-export:** calls the same hosted endpoint.
- **SOC 2:** Hub generates the SOC 2 access report for the auditor
  automatically from the decision logs, and auto-detects and redacts PII.

## Leave until later

- The embedded PDP for the dashboard (Q1).
- Scoped per-customer policies.

## Next steps

1. Create the Hub store and the two deployments.
2. Write the policies in the Hub editor and add tests.
3. Copy each deployment's hosted endpoint and credential into Secrets Manager.
4. Add `@cerbos/http` checks to every route, returning 403 on deny.
5. Turn on the SOC 2 report in Hub before Q3.
