# Gateway authorization by employment type

## Summary

Put **Cerbos Synapse** behind Envoy's `ext_authz` filter. For every request,
Envoy asks Synapse; a Synapse **Envoy extension** maps the request (path, method,
the verified `sub`) to a Cerbos check; a Synapse **data source** looks up the
caller's `employment_type` and `active` flag in the HR database and adds them to
the principal; Synapse's PDP evaluates **Cerbos policies** and Envoy allows or
returns 403. The 40 services are untouched, and rule changes are policy changes
shipped through **Cerbos Hub** without redeploying Envoy, Synapse or the services.

## Components

### 1. Envoy `ext_authz` → Synapse Envoy extension

- Add the `envoy.filters.http.ext_authz` filter after `jwt_authn` in
  `gateway/envoy.yaml`, pointing at Synapse's ext_authz endpoint (gRPC), with
  `failure_mode_allow: false` so a Synapse outage fails closed.
- In Synapse, configure the Envoy integration (`envoyExternalAuthz`) with an
  Envoy extension that builds the check: principal ID from the verified JWT
  payload (`sub`), resource kind `route` with attributes `prefix` (`finance`,
  `hr`, `wiki`, `deploy`, ...) and `path`, and the action from the HTTP method
  (`GET`/`HEAD` → `read`, everything else → `write`). It maps a Cerbos deny to a
  403 for Envoy.

Why: the requirement is enforcement at the gateway with no changes to the
services. Synapse's Envoy integration is the Cerbos component built for exactly
this.

### 2. Synapse data source for HR attributes

- The token has no employment data, and a Cerbos PDP is stateless: it evaluates
  only the attributes in the request and never queries a database itself. So
  the attributes must be fetched before the PDP is asked.
- Add a Synapse **data source** that looks up `people` by `okta_user_id = sub` on
  the HR read replica — the built-in SQL data source (`system://sqldb`) fits a
  single-table lookup, or a small Starlark/WASM data source if logic grows — and
  the Envoy extension calls it to set `principal.attr.employment_type`,
  `principal.attr.active` and `principal.attr.department`.
- Use a read-only database user scoped to the `people` table and cache lookups
  for a short TTL so the gateway does not query Postgres on every request.

Why: enrichment in Synapse happens once, at the decision point, for every
service, and the HR database stays the single source of truth.

### 3. Policies

- One resource policy for kind `route`, using principal attributes:
  - deny everything when `P.attr.active != true` (or the person is unknown);
  - `employee`: allow `read` and `write` on every route;
  - `contractor`: allow `read` and `write` unless `R.attr.prefix in ["finance", "hr"]`;
  - `intern`: allow `read` only.
- Policy test suites (`*_test.yaml`) cover each employment type, an inactive
  person, and the finance/hr prefixes. Restricting `/deploy/` for contractors
  next quarter is a one-line policy change plus a test.

### 4. Cerbos Hub

- Keep the policies in git, mirrored into a Hub policy store, with a deployment
  per environment (dev, staging, prod). Hub compiles and runs the tests on every
  change and pushes the signed bundle to Synapse's PDP within seconds; a failing
  test keeps the previous bundle serving. That is how rules change "without
  redeploying anything".
- Optionally enable Hub audit log collection to answer "who was denied access
  to /finance/ and why".

## Approaches to avoid

- **Looking up the HR database in each service** (or in per-service
  middleware). It means changing 40 services, duplicating the lookup in three
  languages, and enforcing inconsistently — exactly what the gateway is for.
- **Expecting the Cerbos PDP to query Postgres.** The PDP has no attribute
  fetching; its storage drivers load policies, not user data. Enrichment belongs
  in Synapse.
- **Putting the rules in Envoy** (RBAC filter, Lua filter querying Postgres).
  Rules in gateway config are hard to test and change with a redeploy.
- **Pushing employment type into tokens** via a custom IdP hook — ruled out by
  the identity team, and it would go stale when someone converts or leaves.
- **Failing open** (`failure_mode_allow: true`) when Synapse is unavailable.

## Next steps

1. Write the `route` resource policy and its test suite for each employment
   type, inactive people and each restricted prefix; run `cerbos compile`
   (cerbos-policy).
2. Build the Synapse configuration: the SQL data source against the HR read
   replica and the Envoy extension that maps path/method/`sub` to the check and
   enriches the principal; prove it with Synapse extension tests
   (cerbos-synapse-extension).
3. Set up the Hub policy store and per-environment deployments, and point
   Synapse's PDP at them (cerbos-hub-setup).
4. Add the `ext_authz` filter to `envoy.yaml` in dev, verify each employment
   type end to end, then roll through staging to prod.
5. Turn on audit log collection for denied requests.
