# Ledgerly authorization design

## Summary

Move every permission rule out of React and Express into Cerbos policies. The
Express API becomes the enforcement point: each route asks a Cerbos **service
PDP** before it acts. The React app asks an **embedded PDP** (ePDP) running in
the browser which buttons to render, so the 500-row list needs no extra round
trips. Per-customer differences are **scoped policies**, one scope per tenant,
layered over shared defaults. **Cerbos Hub** compiles and tests the policies
once and pushes them to the service PDPs in dev, staging and prod, and serves the
ePDP bundle to the browser.

## Components

### 1. Policies: one `invoice` resource policy, with tenant scopes

- A base `invoice` resource policy (no scope) holds the defaults: `viewer` reads;
  `clerk` edits invoices with `status == "draft"`; `approver` approves;
  `finance_admin` does everything.
- Each customer that differs gets a **scoped** copy of the policy, scope = the
  tenant ID: `scope: "acme"` and `scope: "globex"`. A request carries
  `resource.scope = tenant_id`; Cerbos evaluates the most specific scope and
  falls back to its ancestors, ending at the base policy. Tenants without their
  own scope get the defaults.
  - **Acme** narrows the defaults: approving an invoice with
    `R.attr.amount > 10000` requires the `approver` role, and `delete` is denied
    when `R.attr.status == "sent"`. Use
    `scopePermissions: SCOPE_PERMISSIONS_REQUIRE_PARENTAL_CONSENT_FOR_ALLOWS` so
    the scope can only take access away.
  - **Globex** grants something extra: `clerk` may `approve` when
    `R.attr.amount <= 5000`. This scope uses
    `SCOPE_PERMISSIONS_OVERRIDE_PARENT`.
- A new customer variation is a new scoped policy file, reviewed and tested like
  code, and shipped without an API or web release.
- Every policy has a `_test.yaml` suite (`cerbos compile` runs them), including
  cases for each tenant scope.

Why: the rules live in one place and are evaluated identically by the API and
the browser. Scopes give shared defaults with per-tenant overrides; separate
Hub policy stores per tenant are only worth it if a customer needs hard
isolation, which nobody has asked for.

### 2. Cerbos Hub: one policy store, a deployment per environment

- Policies live in a git repo mirrored into a **Hub policy store**. Hub compiles
  and runs the policy tests on every change; a failing test blocks the build and
  the previous bundle keeps serving.
- One **deployment** each for dev, staging and prod. Promoting a policy change
  is a Hub action, not an application release, and Hub shows which bundle each
  PDP runs. Rollback is a deployment action too.

Why: we have three environments and six API replicas in prod. Without Hub every
PDP would fetch and compile policies itself and we would own the test pipeline.
The ePDP also exists only with Hub.

### 3. Service PDPs next to the API

- Run the Cerbos PDP as a **sidecar** in each API pod, configured with the
  environment's Hub deployment ID and client credential (from a Kubernetes
  secret). Sidecars keep the check on localhost.

### 4. API enforcement (PEP) — the source of truth

- Add `@cerbos/grpc` to the API and one helper that maps `req.user` (from the
  verified Okta token: `sub`, `roles`, `tenant_id`) to the Cerbos principal, and
  an invoice row to the resource (`kind: "invoice"`, `id`, `scope: tenant_id`,
  `attr: { amount, status, tenantId }`).
- `POST /:id/approve`, `PUT /:id` and `DELETE /:id` load the invoice, call
  `checkResource` / `isAllowed` for the action, and return 403 on a deny before
  touching the database. This closes the two endpoints from the security review.
- `GET /` keeps the tenant filter, and returns the list. If list visibility ever
  depends on more than the tenant, use `planResources` and turn the plan into a
  SQL `WHERE` clause instead of checking rows one by one.

The PDP is stateless and fetches nothing: the API must send every attribute a
rule reads (amount, status, roles, tenant). The API decision is the only one
that binds.

### 5. Browser: embedded PDP for button visibility

- In Hub, add an **ePDP rule** to each deployment, filtered to the `invoice`
  resource and its UI actions (`edit`, `approve`, `delete`), with scopes set to
  **Require specific scope at fetch time** so each browser downloads only its own
  tenant's scope (plus ancestors).
- In React, construct one `Embedded` client from `@cerbos/embedded-client` at
  module scope with `policies: { ruleId, scopes: [tenantId] }` and the WASM from
  `@cerbos/embedded-server/server.wasm?init` (Vite). Wrap the app in
  `CerbosProvider` from `@cerbos/react` with the signed-in principal, and gate
  each button with `useCheckResources` / `useCheckResource` on the same resource
  shape the API sends. Render nothing while loading or on error.
- Decisions are local WebAssembly evaluations, so 500 rows cost no network calls.
  The engine (~19 MB) is cached by the browser and only changes on SDK upgrades.

The browser check decides **what to render, never what is allowed**. A user can
edit the JavaScript; the API check above is what protects the data.

Alternative if the bundle size or disclosure is unwelcome: have `GET /invoices`
call `checkResources` once for the page and return a `permissions` map per
invoice. That is one batched PDP call per page, not per row.

## Approaches to avoid

- **Hard-coded role and tenant checks** in React components or Express routes
  (`user.tenantId === "acme" && ...`). This is the current state: rules drift
  between UI and API and every customer change is a release.
- **Treating the browser check as enforcement.** Hiding a button is not
  authorization; every mutating endpoint must check on the server.
- **Shipping Hub client credentials to the browser** to download the ePDP
  bundle. Browser JavaScript is readable. Keep the ePDP rule public (the invoice
  rules are not secret) or serve the bundle through the API (backend-for-frontend).
- **One policy copy or one deployment per tenant** for small rule differences.
  Scopes inherit the defaults; copies drift.
- **Calling the PDP per row** from the browser or the API for the list.
- **Expecting the PDP to read Postgres or Okta.** It evaluates only what the
  request carries.

## Next steps

1. Write the `invoice` resource policy, the `acme` and `globex` scoped policies
   and their test suites; run `cerbos compile` locally (cerbos-policy).
2. Create the Hub policy store from the policy repo, the dev/staging/prod
   deployments and their client credentials; deploy PDP sidecars with
   `storage.driver: hub` (cerbos-hub-setup).
3. Integrate the API: principal/resource mapping helper and `checkResource` in
   approve, edit and delete, returning 403 on deny; delete the old `if`
   statements (cerbos-pep-integration).
4. Create the ePDP rule with dynamic scopes and wire `@cerbos/embedded-client` +
   `@cerbos/react` into the React app to hide buttons (cerbos-embedded-pdp).
5. Remove the role checks from `InvoiceRow.tsx` and add tests that the API
   returns 403 for viewers on edit and delete.
6. Later, for compliance questions, turn on Hub audit log collection.
