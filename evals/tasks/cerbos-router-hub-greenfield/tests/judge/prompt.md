You are grading a design document, `DESIGN.md`, in your working directory. A
team asked for it before implementing anything; the rest of the directory is
their project (`README.md`, `api/`, `infra/`, `docs/`) for context.

The request: Rosterly, a five-person startup with no platform or SRE engineer,
is adopting Cerbos for its first service, `schedules-api` (TypeScript/Fastify
on AWS ECS Fargate in staging and prod, Auth0 tokens carrying `sub`, `org_id`,
`location_ids` and `roles`). The roadmap adds a React manager dashboard that
must hide buttons people cannot use (Q1), a Python `payroll-export` service
(Q2), and a SOC 2 Type II audit that will want evidence of who accessed and
changed data and how access rules are changed and reviewed (Q3). Rules will
change as pilot customers ask. They do not want to over-build for one service
or redo everything in six months. The document had to recommend how to set up
Cerbos now (what runs where, how policies are written, tested and delivered),
explain why given the roadmap, say what can wait, and list ordered next steps.

Reference facts about Cerbos for this grading:
- Real components: policies (resource, derived roles, principal, role
  policies) with `*_test.yaml` test suites, compiled and tested by
  `cerbos compile`; the open-source Cerbos PDP, run as a sidecar, DaemonSet or
  central service; PEP SDKs (Go, JavaScript `@cerbos/grpc`/`@cerbos/http`,
  Python, Java, .NET, Rust, PHP, Ruby) calling `CheckResources`/`isAllowed`
  and `PlanResources`; `cerbosctl`; Cerbos Hub (policy stores, deployments,
  client credentials, embedded PDP rules, playground, audit log collection,
  Insights, usage dashboard, exports); embedded PDPs (WebAssembly,
  `@cerbos/embedded-client`); Cerbos Synapse.
- The open-source PDP runs standalone with no Hub account, loading policies
  through its storage drivers (`disk`, `git`, `blob`, database drivers) and
  writing audit logs to the `local`, `file` (a file or stdout) or `kafka`
  backends. That remains a valid way to run Cerbos; Hub is not required to run
  Cerbos. Without Hub each PDP fetches and compiles policies itself, and the
  team owns any pipeline that tests policies before they reach production.
- A Hub policy store holds policy files. Its source is either a GitHub
  repository that Hub mirrors (a branch, optionally a subdirectory; each push
  that changes a policy triggers a build) or uploads (`cerbosctl hub store
  replace-files` / `upload-git` / `add-files`, from a laptop or CI with a store
  credential, or a ZIP in the console).
- A Hub deployment references one or more stores. On every change it compiles
  the policies once and runs every test suite; a compile or test failure blocks
  the build and leaves the previous bundle serving. A passing build becomes a
  signed bundle pushed to every PDP connected to that deployment within
  seconds, with no PDP restart and no application redeploy. Teams typically
  create a deployment per environment (dev, staging, prod). The Builds tab
  shows build history and which version was active when; the deployment can
  roll back to an earlier version or promote a newer one (either pins and
  freezes it), and can be frozen so new builds queue instead of going live.
  The Decision points tab lists each connected PDP with the build it runs, its
  Cerbos version and when it was last seen; PDPs export
  `cerbos_dev_hub_connected` and bundle-update metrics.
- Connecting a service PDP to Hub is a PDP configuration change: the same
  Cerbos binary/image and the same policy files, with `storage.driver: hub`,
  the deployment ID (`storage.hub.remote.deploymentID` or
  `CERBOS_HUB_DEPLOYMENT_ID`) and a deployment client credential
  (`hub.credentials` or `CERBOS_HUB_CLIENT_ID`/`CERBOS_HUB_CLIENT_SECRET`),
  optionally a `pdpID` (`CERBOS_HUB_PDP_ID`) naming the instance in Hub and a
  `cacheDir`. The PDP needs outbound HTTPS to
  `api.cerbos.cloud` and `cdn.cerbos.cloud`, and keeps serving its last bundle
  if it loses the connection. Store credentials (for uploads) and deployment
  credentials (for PDPs) are different and not interchangeable. Stores,
  deployments and credentials are created in the Hub console.
- Service PDPs always run in the customer's own infrastructure, including when
  managed by Hub: authorization requests and their attributes are evaluated
  there and are not sent to Hub for evaluation. Hub builds and distributes
  policy bundles and collects audit logs; it does not host, run or scale the
  customer's service PDPs, and it does not evaluate their production checks.
- The Hub playground prototypes and tests policies in the browser with nothing
  installed, with execution traces, and can export the policies.
- Embedded PDPs exist only with Hub: an ePDP rule on a deployment serves a
  filtered bundle to `@cerbos/embedded-client`, which evaluates in WebAssembly
  in a browser, edge worker or serverless function. A browser check only
  decides what to render; the server still enforces with a service PDP. Hub
  client credentials never go in browser code.
- Hub audit log collection: the PDP's `audit.backend: hub` with `hub.credentials`
  (a Read & write deployment credential; a read-only one cannot upload logs)
  and `audit.hub.storagePath`, a local buffer that should be a persistent
  volume: entries are written there first and removed only once Hub has
  acknowledged them. It works whatever storage driver
  the PDP loads policies from. Masks under `audit.hub.mask` (sections
  `metadata`, `peer`, `checkResources`, `planResources`, JSONPath-like paths
  such as `inputs[*].principal.attr.email` or `inputs[*].auxData.jwt`) delete
  fields at the PDP before the entry is buffered or sent, so masked values
  never leave the network; masks are only available on the `hub` backend.
  `includeMetadataKeys`/`excludeMetadataKeys` control which request headers are
  captured at all (none by default; `authorization` is never captured), and the
  raw JWT is never recorded, only decoded claims under `auxData.jwt`.
  `pipeOutput` sends the same masked entries to a second backend such as
  stdout. `decisionLogFilters` can drop entries at the PDP.
- In Hub, the Audit logs tab holds decision logs and access logs, searchable
  and filterable by time range, PDP, principal, resource kind, action and
  decision; each decision entry shows the principal and resource attributes as
  evaluated, the effect per action and the policy that produced it.
  `requestContext.annotations` set by the caller (e.g. a ticket or reason)
  are recorded on each entry, and every response carries a `cerbosCallId` the
  application can log. Insights charts allow/deny trends and the most active
  principals, resource kinds and actions, with drill-through to the matching
  decisions. Exports are age-encrypted JSON Lines (Owner role); audit logs and
  Insights are visible to the Owner and Analyst roles. Hub keeps audit logs
  for a set retention period; encrypted exports or `pipeOutput` into storage
  the team controls keep a longer copy. An on-premises Hub option keeps audit
  logs in the customer's own infrastructure.
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
- Fabrication means naming a Cerbos product, package, API, feature or
  configuration that does not exist, or stating something that contradicts
  these facts. In particular each of these is fabrication: saying Cerbos Hub
  hosts, runs, operates or scales the team's service PDPs (a "managed" or
  "hosted" PDP endpoint that their services call); saying production
  authorization checks are sent to or evaluated by Hub in the cloud; saying
  Hub is required to run Cerbos or that the open-source PDP stops working
  without it; saying adopting Hub requires rewriting or converting the
  policies; and inventing Hub features (for example an approval or
  change-request workflow, automatic PII detection, a built-in SIEM, canary
  percentages, Hub-run CI runners, or a Hub log shipper agent). A real feature
  described above, a casing or naming variant of a listed API or setting, or
  ordinary implementation detail about a listed component (Kubernetes
  manifests, secrets, volumes, CI jobs, team process) is not fabrication; a
  statement is not fabrication merely because these facts do not mention it,
  only when it names something that does not exist or contradicts them.

Read `DESIGN.md` and judge each criterion strictly against what it says. A
criterion passes only when every part of it holds. Content that is vague,
optional-sounding, or contradicted elsewhere in the document does not count. If
`DESIGN.md` does not exist, every criterion fails. Do not modify any files.

{criteria}
