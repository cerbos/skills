# Gateway access by employment type

Our ~40 internal services sit behind one Envoy gateway (`/workspace/gateway/envoy.yaml`,
background in `/workspace/README.md`). Security wants access decided by
employment type, at the gateway, for every service:

- **Employees** may call everything.
- **Contractors** may not call anything under `/finance/` or `/hr/`; everything
  else is allowed.
- **Interns** get read-only access everywhere: `GET` and `HEAD` only.
- Anyone who is not an active person in HR is denied.

The catch: employment type is not in the token. Okta tokens carry only `sub`
and `email`, the identity team won't add HR data to them, and the source of
truth is the HR Postgres database (`/workspace/hr/schema.sql`). We can't change
the 40 services, and the rules will change (security already wants to restrict
`/deploy/` for contractors next quarter) without redeploying anything.

We've chosen Cerbos for authorization, but nobody here has used it. Write
`/workspace/DESIGN.md` for the platform team that:

1. recommends which parts of Cerbos to use and how they fit with Envoy, Okta
   and the HR database,
2. explains why each part is the right fit,
3. calls out the approaches we should avoid, and
4. lists the concrete next implementation steps, in order.

Do not implement anything yet; the design document is the deliverable. Cerbos
0.55.0 is installed in this sandbox if you want to try something; Docker is not
available.
