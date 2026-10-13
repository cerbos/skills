You are grading an authorization design document, `DESIGN.md`, in your working
directory. A team asked for it before implementing anything; the rest of the
directory is their project (`README.md`, `web/`, `api/`) for context.

The request: Ledgerly is a multi-tenant B2B invoicing app with a React web app
and an Express API. Edit, Approve and Delete buttons show to users who cannot
use them; the invoice list shows up to 500 invoices and hiding buttons must not
slow it. Editing and deleting are only "protected" by the UI hiding buttons, so
the API must enforce every rule. Customers need different rules (Acme: approver
role above $10,000 and no deleting sent invoices; Globex: clerks approve up to
$5,000), and new variations must not need a release. They have chosen Cerbos
and run three environments. The document had to recommend Cerbos components,
explain why, say what to avoid, and list ordered next steps.

Reference facts about Cerbos for this grading:
- Real components: policies (resource, derived roles, principal, role
  policies) evaluated by a PDP; scoped policies (`scope`, `scopePermissions`);
  the open-source service PDP (sidecar, DaemonSet or central service); PEP SDKs
  such as `@cerbos/grpc` and `@cerbos/http` with `checkResource(s)`,
  `isAllowed` and `planResources`; Cerbos Hub (policy stores, deployments,
  playground, audit log collection, Insights); embedded PDP (ePDP) rules in Hub,
  `@cerbos/embedded-client`, `@cerbos/embedded-server`, `@cerbos/react`
  (`CerbosProvider`, `useIsAllowed`, `useCheckResource`, `useCheckResources`);
  Cerbos Synapse.
- The PDP is stateless: it reads only policies, never application data. The
  caller supplies every principal and resource attribute. Its storage drivers
  (disk, git, blob, database, hub) load policies, not user or record data.
- Cerbos Hub mirrors policies from git into a policy store, compiles them and
  runs their tests on every change (a failing test blocks the build), and
  pushes signed bundles to the PDPs of each deployment (e.g. one per
  environment); service PDPs connect with `storage.driver: hub`, a deployment ID
  and a client credential.
- An embedded PDP requires Cerbos Hub. Hub ePDP rules on a deployment filter
  the bundle by resource, action, role, version and scope; scopes can be fixed
  in the rule or "required at fetch time", where each client names its scopes
  (e.g. its tenant) and gets those plus their ancestors. The browser client is
  `new Embedded({ policies: { ruleId, scopes }, wasm })`, with Vite loading the
  engine via `@cerbos/embedded-server/server.wasm?init`. A browser check only
  decides what to render; the server must still enforce. Hub client
  credentials must never be shipped in browser code; the rule is public or the
  bundle is served by a backend-for-frontend.
- Scoped policies: the scope is set per check on the resource
  (`resource.scope`) and/or the principal (`principal.scope`), e.g. from the
  tenant ID; it selects the most specific matching policy and falls back through its ancestors to the
  unscoped base; `scopePermissions` is `SCOPE_PERMISSIONS_OVERRIDE_PARENT` or
  `SCOPE_PERMISSIONS_REQUIRE_PARENTAL_CONSENT_FOR_ALLOWS`.
- Service PDPs (and Synapse) always run in the customer's own
  infrastructure, including when managed by Cerbos Hub: Hub builds, tests and
  distributes policy bundles (and collects audit logs), but it does not host or
  run the PDPs and does not evaluate authorization checks in the cloud. Hub is
  not required to run Cerbos; the open-source PDP also runs standalone.
- Real audit settings and Hub audit features, which are not fabrication:
  `audit.enabled`, `audit.accessLogsEnabled` and `audit.decisionLogsEnabled`
  (both default to true once audit is enabled), decision-log filters such as
  `ignoreAllowAll`, access entries that record the policy source, and Hub
  audit-log filters by time range, PDP ID, policy source, principal, resource
  kind, action and decision.
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
