# Ledgerly authorization design

## Summary

Use a Cerbos PDP to authorize the API, and keep the React app fast by mirroring
the rules in a small TypeScript permissions module. Tenant-specific rules move
into a `tenant_rules` JSON column so customers can be configured without a
release.

## Components

### Cerbos PDP for the API

Run the Cerbos PDP as a central service in the cluster, reading policies from a
git repository. Write an `invoice` resource policy with the default rules:
viewers read, clerks edit drafts, approvers approve, finance admins do anything.

In Express, add `@cerbos/http` and call `isAllowed` before approve, edit and
delete, returning 403 when denied. This fixes the endpoints from the security
review, because the API now enforces every rule.

### Per-tenant rules

Store each tenant's overrides in `tenants.rules` (JSON), for example
`{"approveLimit": 10000, "approverRoleRequired": true, "deleteSent": false}` for
Acme and `{"clerkApproveLimit": 5000}` for Globex. The API reads the tenant row
and adds these values to the principal's attributes, and the base policy's
conditions compare `R.attr.amount` against `P.attr.approveLimit`. New customer
variations are a database update rather than a policy change.

### React: shared permissions module

Calling Cerbos for each of 500 rows would be slow, so add
`web/src/permissions.ts`, a `can(user, action, invoice, tenantRules)` function
that implements the same matrix in TypeScript. `InvoiceRow` hides Edit, Approve
and Delete when `can` returns false. Because the API enforces with Cerbos, any
drift between the two only affects which buttons show.

## Approaches to avoid

- Leaving endpoints unprotected: every mutating route must check with Cerbos.
- Calling the PDP from the browser for each row.

## Next steps

1. Write the `invoice` policy and tests.
2. Deploy the central PDP and point it at the git repo.
3. Add `isAllowed` to the API routes.
4. Add the `tenant_rules` column and admin screen.
5. Write `permissions.ts` and use it in `InvoiceRow.tsx`, with unit tests that
   mirror the policy tests.
