You are grading an authorization design document, `DESIGN.md`, in your working
directory. A team asked for it before implementing anything; the rest of the
directory is their project (`README.md`, `gateway/envoy.yaml`, `hr/schema.sql`)
for context.

The request: about 40 internal services sit behind one Envoy gateway that
validates Okta tokens. Access must be decided at the gateway by employment type
(employees everything; contractors nothing under `/finance/` or `/hr/`; interns
`GET`/`HEAD` only; inactive or unknown people denied). Employment type is not in
the token — Okta tokens carry only `sub` and `email` and the identity team will
not add HR data — and the source of truth is the HR Postgres database. The 40
services cannot change, and rules must change without redeploying anything.
They have chosen Cerbos. The document had to recommend Cerbos components,
explain why, say what to avoid, and list ordered next steps.

Reference facts about Cerbos for this grading:
- Real components: policies (resource, derived roles, principal, role
  policies) evaluated by a PDP; the open-source service PDP; PEP SDKs; Cerbos
  Hub (policy stores, deployments, audit log collection, Insights); embedded
  PDPs; and Cerbos Synapse, which sits in front of a PDP and runs extensions:
  call mappers, data sources (including the built-in SQL data source
  `system://sqldb`), proxy extensions that enrich CheckResources requests,
  route extensions, and Envoy ext_authz extensions (`envoyExternalAuthz`).
- The PDP is stateless: it evaluates only the attributes in the request and
  never fetches data from databases, IdPs or APIs. Its storage drivers (disk,
  git, blob, database, hub) load policies, not user data, and CEL has no
  database functions. When a rule needs data the caller does not hold, the
  Cerbos answer is a Synapse data source or proxy extension.
- Envoy integration in Cerbos is through Synapse's ext_authz support: Envoy's
  `ext_authz` filter calls Synapse, whose Envoy extension or declarative
  `envoyExternalAuthz` call mapper builds the CheckResources request; Synapse
  extensions are written in CEL, Starlark or WASM and tested with Synapse test
  suites; data sources can cache lookups.
- Cerbos Hub mirrors policies from git into a policy store, compiles them and
  runs their tests on every change, and pushes signed bundles to the PDPs of
  each deployment (including Synapse's embedded PDP).
- `cerbos`, `cerbos-policy`, `cerbos-hub-setup`, `cerbos-pep-integration`,
  `cerbos-embedded-pdp`, `cerbos-synapse-extension`, `cerbos-audit-insights`
  and `cerbos-authz-migration` are Cerbos agent skills (implementation guides
  for coding agents); citing them for next steps is legitimate.
- Further real features of the listed components, which are not fabrication:
  `CheckResources` and `PlanResources` (the API's names; SDKs spell them
  `checkResources`/`check_resources` and so on); policy test suites run by
  `cerbos compile`, with an optional strict-evaluation mode; Hub deployment
  freeze and rollback, build history, and per-environment deployments; scoped
  policies selected by `resource.scope`/`principal.scope`; derived roles;
  schemas; outputs; audit logs to local backends as well as Hub; Synapse data
  sources (including `system://sqldb`), proxy, route and Envoy extensions.
- Fabrication means naming a Cerbos product, package, API, feature or
  configuration that does not exist (an invented library, manager, plugin,
  storage driver that serves user data, or CEL function), or stating something
  that contradicts these facts. A real feature described above, a casing or
  naming variant of a listed API, or ordinary implementation detail about a
  listed component is not fabrication.

Read `DESIGN.md` and judge each criterion strictly against what it says. A
criterion passes only when every part of it holds. Content that is vague,
optional-sounding, or contradicted elsewhere in the document does not count. If
`DESIGN.md` does not exist, every criterion fails. Do not modify any files.

{criteria}
