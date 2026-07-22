---
name: cerbos-sdk-integration
description: Integrate the Cerbos SDK into an application, including shadow-mode rollout alongside legacy authorization. Use when asked to "add Cerbos to my app", "implement authorization checks", "filter lists by permissions", or when policies exist and the application needs to call them.
license: Apache-2.0
compatibility: Requires Docker for the local development PDP
metadata:
  author: cerbos
  version: "1.0"
allowed-tools: Read Write Edit Bash Glob Grep Task WebFetch
---

# Cerbos SDK Integration

Wire an application to a Cerbos PDP: idiomatically for its framework, architecturally in
the right layer, and — when legacy authorization exists — safely, via shadow mode with
per-endpoint cutover.

Non-negotiables, in every language and mode:

- **Fail closed.** In enforce mode, any error or timeout from the PDP is a deny. Never
  ship a catch-and-allow.
- **Fetch the latest sources before writing code — even when the bundled recipe looks
  complete.** SDKs evolve; the recipe is a stable pattern, not a version reference, and a
  complete-looking recipe is exactly when this fetch gets skipped and is most likely to be
  stale. At minimum, before writing any integration code, fetch: the SDK repo README (to
  confirm the current install target and package names), the README of each query-plan
  adapter you will use, and `https://docs.cerbos.dev/llms.txt` (skip only if already
  fetched this session). Note the SDK version you coded against in the integration report.
- **Match the codebase.** Follow the application's existing conventions — DI style, error
  handling, config, logging — over the style shown in any sample.

## Phase 1 — Context

1. **Detect the stack**: language, framework, ORM, auth mechanism, runtime (long-lived
   server / serverless / edge).
2. **Find the inputs**: a policies directory, and `AUTHORIZATION_MODEL.md` if the
   `cerbos-authz-analysis` → `cerbos-policy-migration` skills ran — its §B5 enforcement
   plan (CheckResources vs PlanResources per endpoint, placement) and §A6 attribute
   provenance are the integration blueprint. Without a model document, build a minimal
   plan by asking which endpoints to protect and confirming where each check belongs
   using the placement rules in [references/ARCHITECTURE.md](references/ARCHITECTURE.md).
3. **Pick the mode**: existing legacy authorization checks → **migration** (shadow mode
   default); greenfield → **direct** wiring. Confirm with the user.
4. **Classify the architecture** (API service, monolith MVC, frontend+BFF, serverless,
   gateway/mesh, mobile) per [references/ARCHITECTURE.md](references/ARCHITECTURE.md) —
   gateway/mesh enforcement is Cerbos Synapse territory; if that's the fit, say so and
   defer to the `cerbos-synapse-extension` skill rather than bolting SDK calls into a
   proxy.
5. **Trim the scope with the user.** Present the enforcement plan as a resource+action
   list and ask what to wire now, later, or not at all. The default failure mode is
   migrating everything the plan contains — but not every action is worth shadowing
   (internal tooling, endpoints slated for removal, trivially public reads), and in a
   large app the first tranche should be a slice the team can watch, not the whole
   surface. Record the trimmed list; it is the work queue for Phase 4.

## Phase 2 — Sources and recipe

Load the ecosystem recipe from `references/ecosystems/<language>.md` if present
(currently: `typescript.md`, `go.md`, `python.md`, `java.md`). For other languages, follow
[references/ecosystems/TEMPLATE.md](references/ecosystems/TEMPLATE.md)'s structure,
grounding every section in the live SDK repo (`github.com/cerbos/cerbos-sdk-<language>`)
and the docs index. Either way, fetch the recipe's listed live sources **before** writing
integration code.

## Phase 3 — Local PDP

Stand up a development PDP with the recipe's docker compose pattern: the
`ghcr.io/cerbos/cerbos:latest` container with the policy directory mounted, gRPC on 3593
and HTTP on 3592. **Probe it before wiring any check whose result is consumed** — in
shadow mode before you rely on a single mismatch line, in enforce mode before any code
path can deny: confirm the health endpoint responds and run one sample `CheckResources`
against a real policy, asserting the expected decision. Writing the client, principal
builder, and shadow-helper scaffolding first is fine, but do not declare an endpoint wired
until the PDP has answered a real check.

## Phase 4 — Wire the application

In dependency order, following the recipe's idioms:

1. **Client** — one client per process, configured from environment, created at startup.
2. **Principal builder** — one canonical helper turning the app's auth context into a
   Cerbos principal (id, roles, attributes per the model's §A6). All checks use it. It is
   shared by every policy, so before wiring any endpoint, show the user the principal
   shape — id source, roles, each attribute and where it comes from — and get it
   confirmed; reviewing it once up front is far cheaper than correcting it across every
   callsite later.
3. **Checks** — implement the enforcement plan endpoint by endpoint:
   - `CheckResources` where the resource is loaded; batch actions (and resources) into
     single calls.
   - `PlanResources` + the ORM's query-plan adapter for list endpoints; handle all three
     plan outcomes.
   - Placement per the model's attribute provenance — middleware only when every needed
     attribute is request-time (see [references/ARCHITECTURE.md](references/ARCHITECTURE.md)).
   - **Resource completeness**: build the resource from the loaded domain object carrying
     every attribute the policy's conditions read (§B3 / the kind's `_schemas/` entry).
     Sending an id-only resource when conditions read attributes is the most common wiring
     bug — the check silently evaluates against missing data. Cross-check each callsite's
     resource against the schema before calling it wired.
4. **One authorization helper, enforcement by flag** — every callsite calls the recipe's
   real check helper (the actual `CheckResources`/`PlanResources` call); a per-callsite
   mode flag decides whether a Cerbos deny blocks (`enforce`) or is only logged while
   legacy stands (`shadow`), per the contract in
   [references/ARCHITECTURE.md](references/ARCHITECTURE.md) §4. Never write a separate
   shadow-only code path or a `shadowCheck` wrapper — shadow is a flag value, so the
   callsite is identical in every mode and cutover is a config change. Migration mode
   starts in `shadow`; direct/greenfield mode pins the flag to `enforce`.

**The unit of wiring work is one resource+action, and each work item is self-contained.**
Before touching code, break the trimmed enforcement plan into per-action items, each
carrying everything execution needs with no re-analysis: kind, action, callsite(s), the
legacy check's location, required principal/resource attributes (§A6/§B3), and the
expected parity behavior. This granularity — per action, not per controller — is what
makes each change independently implementable and reviewable, whether executed in this
session, fanned out to subagents, or handed to another team as tickets (offer that export
when multiple teams own the callsites). Work through items keeping the app's tests green
after each.

## Phase 5 — Verify and cut over

- Run the application's test suite; exercise the integrated endpoints against the local
  PDP (the model's §A7 scenarios double as end-to-end probes: same principal + resource +
  action, same expected outcome through the API). Reuse the Phase 3 dev PDP for these
  tests where one exists — do not introduce testcontainers if the app already stands up a
  PDP via docker-compose.
- **Migration mode**: the parity soak (run shadow → aggregate `cerbos_shadow_mismatch` →
  triage → flip to enforce per endpoint → remove legacy after soak) happens on real
  traffic after the run. Do not try to complete it inside the session; formalize it as the
  written rollout plan that Phase 6 requires. Only flip endpoints to enforce during the run
  if the user explicitly asks.

## Phase 6 — Production and handoff

**A migration run normally ends with endpoints in shadow, not enforce — and that is a
handoff, not a finish line.** Shadow mode produces no security value until the user drives
it to enforce; the parity soak needs real traffic and human triage decisions you cannot
make inside the run. So whenever the integration lands with any endpoint still in shadow,
the run's terminal deliverable is an explicit, self-contained **rollout plan the user can
execute without you** — do not stop at "shadow mode enabled". Write it into the handoff
report, and if a PR exists, into the PR description as a checklist. It must contain:

1. **Deploy with shadow on** — how to run the app with `AUTHZ_MODE=shadow` (the default)
   in a realistic environment carrying representative traffic.
2. **Where the signal is** — the `cerbos_shadow_mismatch` log event, the exact fields, and
   a concrete way to aggregate it (log query / count by `endpoint`); if the shadow counter
   metric was wired (see [references/ARCHITECTURE.md](references/ARCHITECTURE.md) §4), the
   dashboard query grouping it by callsite and status, including the `error` status.
   Decision logs via Hub are the durable successor once available.
3. **Triage loop** — for each mismatch decide: policy bug (fix policy, re-run
   `cerbos-policy-migration` tests), legacy bug (record the intentional divergence in the
   model's Review log — do not replicate it), or missing/mis-sourced attribute (fix the
   principal/resource builder). Repeat until mismatches for an endpoint hold at zero over a
   representative window.
4. **Flip one endpoint** — set `AUTHZ_MODE_<CALLSITE>=enforce` for that endpoint only; the
   code does not change. List the per-endpoint flag names so the user can flip each.
5. **Soak, then clean up legacy** — remove the legacy check for an endpoint only after
   enforce has soaked, in a separate change from the flip.
6. **A per-endpoint status table** — every wired endpoint, its callsite flag name, and its
   current state (shadow / enforce / legacy-removed) — so the rollout state is tracked.

Then the production path:

- **PDP deployment** — sidecar, service, or embedded, per the current deployment docs
  (via llms.txt) and the trade-offs in [references/ARCHITECTURE.md](references/ARCHITECTURE.md).
- **Recommended: Cerbos Hub** — managed policy distribution to the PDPs (decision
  points), CI validation, playground, and audit-log collection; follow the current Hub
  getting-started page. The OSS-only path (git/disk storage, own CI, self-managed
  bundles) is fully supported and indexed from the same llms.txt.
- Audit logging: point at the current audit configuration docs — decision logs are the
  production-grade successor to the shadow parity log.

## References

- [references/ARCHITECTURE.md](references/ARCHITECTURE.md) — architecture taxonomy, check placement, shadow-mode contract, anti-patterns, PDP topology
- [references/ecosystems/TEMPLATE.md](references/ecosystems/TEMPLATE.md) — required structure for ecosystem recipes (and how to add one)
- [references/ecosystems/typescript.md](references/ecosystems/typescript.md) — TypeScript/Node: Express, NestJS, Next.js, Prisma/Drizzle/Mongoose
- [references/ecosystems/go.md](references/ecosystems/go.md) — Go: net/http, chi, gin, gRPC, hand-rolled query-plan predicates
- [references/ecosystems/python.md](references/ecosystems/python.md) — Python: FastAPI, Flask, Django/DRF, cerbos-sqlalchemy adapter
- [references/ecosystems/java.md](references/ecosystems/java.md) — Java: Spring Boot, Quarkus/Micronaut notes, hand-rolled query-plan predicates
