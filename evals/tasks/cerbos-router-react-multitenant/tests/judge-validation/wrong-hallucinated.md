# Ledgerly authorization design

## Summary

Adopt Cerbos with three parts: the Cerbos PDP connected to our Postgres
database, the `@cerbos/react-guard` component library in the web app, and the
Cerbos Tenant Manager in Cerbos Hub for per-customer rules.

## Components

### PDP with the Postgres attribute driver

Run the PDP as a sidecar in each API pod and configure
`storage.driver: postgres` with `attributeSource: invoices` so the PDP loads each
invoice's `amount`, `status` and `tenant_id` and the user's roles directly from
our database when a check arrives. The API then only sends the invoice ID and
user ID, which keeps the Express code tiny.

### API enforcement

In Express, call `cerbos.isAllowed({ principal: { id }, resource: { kind:
"invoice", id }, action })` before approve, edit and delete, and return 403 on a
deny. The API is the source of truth; the UI only hides buttons.

### Per-tenant rules with the Tenant Manager

Cerbos Hub's Tenant Manager stores a rule overlay per tenant (Acme: approver
above $10,000, no deleting sent invoices; Globex: clerks approve up to $5,000)
and merges it into the bundle at request time based on the `X-Cerbos-Tenant`
header, so we never write scoped policies.

### React

Install `@cerbos/react-guard` and wrap each button in
`<CerbosGuard action="approve" resource={invoice}>`. The guard downloads the
embedded PDP bundle using the Hub client ID and secret from
`VITE_CERBOS_CLIENT_ID` / `VITE_CERBOS_CLIENT_SECRET` and hides the button when
the action is denied. The browser check is presentational; the API still
enforces.

## Approaches to avoid

- Hard-coded `if` checks in React or Express.
- Trusting the browser: the API must enforce every action.

## Next steps

1. Configure the PDP's Postgres attribute driver.
2. Create the tenant overlays in the Tenant Manager.
3. Add `isAllowed` to the API routes.
4. Add `@cerbos/react-guard` to the web app.
