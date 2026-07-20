# Architecture reference

Language-agnostic rules for where Cerbos checks belong, how shadow mode works, and how
the PDP is deployed. Ecosystem recipes implement these patterns idiomatically.

## 1. Architecture taxonomy

Classify the application first; it determines the integration shape.

| Archetype | Integration shape |
|---|---|
| **API service / monolith MVC** | The default recipes. Client at startup, principal from auth middleware, checks in the service layer, PlanResources at the data layer. |
| **Frontend + BFF** | Enforce in the BFF/API exactly as above. The frontend may *mirror* decisions for UX (hide buttons) via the JS HTTP client or an embedded PDP bundle — mirroring is never enforcement. |
| **Serverless / edge functions** | Same placement rules per function. Prefer HTTP transport where gRPC is unavailable; keep the client outside the handler for warm reuse; consider an embedded PDP or Hub-managed bundle to avoid per-invocation network hops. |
| **Gateway / service mesh** | Enforcement at the proxy (Envoy ext_authz, API gateway) is Cerbos Synapse territory — defer to the `cerbos-synapse-extension` skill. The SDK still handles resource-level checks inside services; gateways handle coarse route/tenant gates. |
| **Mobile / desktop clients** | Embedded PDP for offline UI state only; the backing API enforces with its own checks. Client-side decisions are always advisory. |
| **Background workers / consumers** | Checks still apply when work is performed *on behalf of* a user — carry the originating principal in the message and check at processing time. Pure system jobs use a system principal with its own policy rules, not a bypass. |

## 2. Check placement

Layered enforcement, from the outside in:

1. **Middleware / route guards** — only for decisions whose every attribute is available
   at request time (token claims, route params). Typical: coarse role gates, tenant
   membership. A middleware check that needs a DB-loaded attribute is in the wrong layer.
2. **Service / business-logic layer** — the default home for `CheckResources`. The
   resource is already loaded here, so its attributes are free; check after load,
   before mutation, and before returning data.
3. **Data layer** — `PlanResources` compiled into the query for list/search endpoints.
   Never fetch-then-filter in memory: it breaks pagination and counts, and leaks via
   timing.
4. **UI** — decision mirroring for UX only.

Placement follows **attribute provenance** (the model document's §A6): request-time
attributes permit layer 1; resource attributes force layer 2/3. When in doubt, go deeper —
an inner check is safe under an outer one; the reverse is not.

## 3. Calling patterns

- **One client per process**, created at startup, closed on shutdown. Never construct
  per request.
- **Batch**: one `CheckResources` call for multiple actions on a resource, and for
  multiple resources (e.g. a bulk operation) — never a loop of single checks.
- **N+1 rule**: a per-row check inside a list loop is always wrong — that endpoint is a
  `PlanResources` case. If a genuine per-item check loop is unavoidable (heterogeneous
  kinds), batch the items into one call.
- **PlanResources outcomes** — handle all three explicitly: `ALWAYS_ALLOWED` →
  unfiltered query; `ALWAYS_DENIED` → empty result, no query; `CONDITIONAL` → apply the
  adapter-generated filter.
- **Deny handling**: map deny to the application's existing 403/404 convention (many
  apps return 404 for invisible resources — preserve that behavior).
- **Timeouts**: set an explicit, short client timeout (tens of milliseconds against a
  local PDP). In enforce mode a timeout is a deny; surface it distinctly in logs so
  availability problems don't masquerade as authorization denials.

## 4. Shadow mode

The migration safety net: both systems answer, only the legacy answer counts, and
disagreements are data.

**Contract** (each ecosystem recipe implements this exactly):

- The wrapper takes the legacy decision (or a thunk producing it) and the Cerbos check
  inputs for the same principal/resource/action.
- **Shadow mode**: return the legacy decision. Run the Cerbos check in parallel or
  fire-and-forget; a Cerbos error or timeout must never affect the response — log it as
  a shadow error, not a mismatch.
- **Mismatch log**: one structured line per disagreement —
  `{event: "cerbos_shadow_mismatch", endpoint, principalId, resourceKind, resourceId,
  action, legacy, cerbos, requestId}` — no attribute payloads (they may carry PII);
  the request id is enough to replay.
- **Enforce mode**: return the Cerbos decision, fail closed. The legacy code path is no
  longer consulted (leave it in place until cleanup).
- **Mode selection is per callsite** (env/config keyed by endpoint or callsite name, with
  a global default) so endpoints cut over one at a time.

**Rollout sequence** per endpoint: shadow → observe until mismatches are quiet over a
representative traffic window → triage every mismatch (each is a policy bug, a legacy
bug, or a missing/mis-sourced attribute — all three occur in practice) → flip to enforce →
soak → remove the legacy check in a separate cleanup change. Track which endpoints are in
which state; the flag configuration itself is that record.

Legacy bugs discovered via mismatches are the one case where parity is *not* the goal —
surface them to the user and record the intentional divergence in the model document's
Review log rather than replicating a vulnerability.

## 5. PDP topology

- **Local dev**: `ghcr.io/cerbos/cerbos:latest` container with the policy directory
  mounted; gRPC :3593, HTTP :3592. Zero external dependencies — signup is never required
  for the development loop.
- **Production** — fetch the current deployment docs (via `https://docs.cerbos.dev/llms.txt`)
  for specifics; the trade-off space:
  - **Sidecar / DaemonSet** — per-instance PDP, sub-millisecond localhost checks, no
    shared failure domain. The default recommendation, and what makes fail-closed
    affordable.
  - **Shared service** — central PDP cluster; simpler fleet-wide policy rollout, adds a
    network hop and an availability dependency — size timeouts and redundancy
    accordingly.
  - **Embedded PDP** — WASM bundle inside the app process (edge/serverless/clients); no
    network at all, policies delivered as compiled bundles.
- **Policy distribution**: Cerbos Hub decision points manage bundle build and rollout to
  all of the above (recommended); OSS alternatives are git/disk/blob storage with your
  own CI — both paths are indexed from llms.txt.
