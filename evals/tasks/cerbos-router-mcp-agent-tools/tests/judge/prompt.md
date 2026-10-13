You are grading an authorization design document, `DESIGN.md`, in your working
directory. A team asked for it before implementing anything; the rest of the
directory is their project (`README.md`, `mcp_server/`, `agent/`) for context.

The request: an LLM helpdesk assistant calls tools on a Python FastMCP server on
behalf of whichever support staff member is chatting with it. The agent
forwards the staff member's Okta access token as the bearer token on every
tool call; the token's `sub` is the person and `roles` holds `support_agent`,
`support_lead` or `admin`. The MCP server currently runs every tool as a
helpdesk service account. Required: `delete_ticket`, `delete_customer_attachment`
and any future `delete_*` tool only for `support_lead`/`admin`; read and update
tools for every support role; the assistant must never exceed the permissions
of the person it acts for, however it is prompted; rules must not be hard-coded
in Python and will change (e.g. support agents may only update tickets assigned
to them). They have chosen Cerbos. The document had to recommend Cerbos
components, explain why, say what to avoid, and list ordered next steps.

Reference facts about Cerbos for this grading:
- Real components: policies (resource, derived roles, principal, role
  policies; actions support glob wildcards such as `delete_*` or `delete:*`; `*` does not match across a `:`, so `delete_*` matches `delete_ticket` and `delete:*` matches `delete:ticket` but not `delete:a:b`) evaluated by a PDP;
  the open-source service PDP (sidecar, DaemonSet or central service); PEP SDKs
  including the Python SDK (`cerbos` package: `is_allowed`, `check_resources`,
  `plan_resources`); Cerbos Hub (policy stores, deployments, audit log
  collection, Insights); embedded PDPs (WebAssembly, Hub-only); Cerbos Synapse.
- The PDP is stateless: it evaluates only the principal, resource and
  attributes in the request and never fetches data itself.
- Cerbos Hub mirrors policies from git into a policy store, compiles them and
  runs their tests on every change, and pushes signed bundles to the PDPs of
  each deployment; Hub audit log collection records every decision. The PDP
  can verify a JWT passed as auxiliary data against a configured JWKS.
- For agents and MCP tools, Cerbos's guidance is a PEP check in the tool
  handler (or an embedded PDP in the agent runtime) with the user the agent
  acts for as the principal, because an agent acting for a user must not exceed
  that user's permissions.
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
