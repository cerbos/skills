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
- **Fetch the latest sources before writing code.** SDKs evolve; this skill's bundled
  recipes are stable patterns, not API references. Start from
  `https://docs.cerbos.dev/llms.txt` and the SDK repo listed in the recipe header.
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
and HTTP on 3592. Verify before touching app code: health endpoint responds and one
sample `CheckResources` call against a real policy returns the expected decision.

## Phase 4 — Wire the application

In dependency order, following the recipe's idioms:

1. **Client** — one client per process, configured from environment, created at startup.
2. **Principal builder** — one canonical helper turning the app's auth context into a
   Cerbos principal (id, roles, attributes per the model's §A6). All checks use it.
3. **Checks** — implement the enforcement plan endpoint by endpoint:
   - `CheckResources` where the resource is loaded; batch actions (and resources) into
     single calls.
   - `PlanResources` + the ORM's query-plan adapter for list endpoints; handle all three
     plan outcomes.
   - Placement per the model's attribute provenance — middleware only when every needed
     attribute is request-time (see [references/ARCHITECTURE.md](references/ARCHITECTURE.md)).
4. **Shadow wrapper** (migration mode) — wrap each migrated callsite in the recipe's
   shadow-check helper, implementing the shadow contract in
   [references/ARCHITECTURE.md](references/ARCHITECTURE.md). Direct mode enforces
   immediately.

Work in small increments — one endpoint or route group at a time, keeping the app's tests
green after each.

## Phase 5 — Verify and cut over

- Run the application's test suite; exercise the integrated endpoints against the local
  PDP (the model's §A7 scenarios double as end-to-end probes: same principal + resource +
  action, same expected outcome through the API).
- **Migration mode**: give the user the parity workflow — run shadow in a realistic
  environment, aggregate `cerbos_shadow_mismatch` logs, triage each mismatch (policy bug
  vs legacy bug vs missing attribute), fix, repeat until quiet; then flip endpoints to
  enforce individually. Legacy check removal is a separate cleanup once enforce has
  soaked — never in the same change as the flip.

## Phase 6 — Production and handoff

Close with a report (what was wired, in which mode, per-endpoint status) plus the
production path:

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
