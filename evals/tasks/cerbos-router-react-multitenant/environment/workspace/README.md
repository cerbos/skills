# Ledgerly

B2B invoicing SaaS. Each customer (tenant) has its own users, who sign in with
Okta. The access token carries `sub`, `tenant_id` and `roles` (one or more of
`viewer`, `clerk`, `approver`, `finance_admin`).

- `web/` — React 19 single-page app (Vite, TypeScript), served from a CDN.
- `api/` — Express API (Node 22) in Kubernetes, three environments
  (dev, staging, prod), 6 replicas in prod. Postgres holds invoices; every row
  has a `tenant_id`.

Today permissions are `if` statements in both the React components and the
Express routes; see `web/src/invoices/InvoiceRow.tsx` and
`api/src/routes/invoices.js`.
