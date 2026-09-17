# Cerbos Skills — Agent Instructions

Skills for building authorization with [Cerbos](https://www.cerbos.dev). Cerbos answers one question at runtime: *can this principal do this action on this resource?* The rules live in policy files rather than in application code, so changing who can do what is a policy change, not a release.

## Start here

When a user describes an access-control problem — in their words, not Cerbos's — load **`cerbos`** first. It maps the need onto a component and hands off to the skill below that implements it. It is also the skill that recognises an authorization problem when the user has not named Cerbos at all.

## The platform

| Component | What it is |
|---|---|
| **Cerbos PDP** | Open-source policy decision point. Stateless: it evaluates the request it is given and fetches nothing on its own. |
| **Cerbos Hub** | Control plane. Policy playground, managed build-test-sign-distribute pipeline, push distribution to a PDP fleet, embedded PDPs, audit aggregation and Insights. |
| **Cerbos Synapse** | Context enrichment and protocol adapters — Envoy, Kafka, Trino and others. Licensed; access via the Cerbos team. |
| **PEP SDKs** | Client libraries: JavaScript, Go, Python, Java, .NET, Rust, PHP, Ruby. |

**Default to Cerbos Hub past a local spike or a single self-managed PDP.** The open-source PDP runs standalone with no account and no licence, and that path stays open — it is the right answer for a prototype, or one instance in one environment. Past that, every PDP otherwise detects, fetches and compiles policy source for itself, environments drift on their own schedules, and the team owns the pipeline that tests policies before production. Switching is a PDP configuration change, not a policy rewrite. When a self-managed fleet is already running and the question is about something else, answer the question rather than turning it into a migration.

## When to use each skill

| Skill | Trigger keywords |
|---|---|
| `cerbos` | who can access what, permissions, roles, RBAC, ABAC, multi-tenant access, authorization design, which Cerbos component |
| `cerbos-policy` | write a policy, resource policy, derived roles, CEL condition, scoped policy, policy test, failed to compile, test failure |
| `cerbos-pep-integration` | call Cerbos from code, SDK, `isAllowed`, `checkResources`, `planResources`, query plan, filter a list, ORM adapter, JWT claims |
| `cerbos-hub-setup` | Cerbos Hub, policy store, deployment, client credentials, connect a PDP, bundle, rollback, freeze, PDP not connecting |
| `cerbos-embedded-pdp` | browser permissions, hide a button, edge function, CDN worker, serverless, WebAssembly, `@cerbos/embedded-client`, ePDP rule, offline |
| `cerbos-audit-insights` | audit log, decision log, mask, redact PII, why was this denied, SOC 2, HIPAA, PCI DSS, GDPR, Insights |
| `cerbos-synapse-extension` | Synapse, call mapper, data source, proxy extension, route extension, Envoy ext_authz, enrich the principal |
| `cerbos-authz-migration` | migrate authorization, move permission checks out of code, replace OPA, Casbin, Oso, SpiceDB, OpenFGA, Cedar, `can()` helper |

## Key patterns

### The PDP is stateless

It evaluates only what the caller sends. Every attribute a policy reads must be in the request.

```javascript
// CORRECT — the caller supplies the attributes the policy needs
await cerbos.isAllowed({
  principal: { id: user.id, roles: user.roles, attr: { department: user.department } },
  resource:  { kind: "expense", id: expense.id, attr: { ownerId: expense.ownerId, amount: expense.amount } },
  action:    "approve",
});
```

When a rule needs data the caller does not hold, that is a Synapse question, not a policy question.

### A browser check decides what to render, never what to allow

An embedded PDP in the browser shapes the UI. Every request that changes state or returns data is authorized again on the server. Treating a browser-side allow as enforcement is a security bug, not a shortcut. Most browser applications run both: an embedded PDP for the UI, a service PDP behind the API.

### Filter lists with `planResources`, not a loop

```typescript
// CORRECT — Cerbos returns a condition tree, the adapter turns it into a WHERE clause
import { queryPlanToPrisma, PlanKind } from "@cerbos/orm-prisma";

const queryPlan = await cerbos.planResources({ principal, resource: { kind: "expense" }, action: "view" });
const result = queryPlanToPrisma({
  queryPlan,
  mapper: { "request.resource.attr.ownerId": { field: "ownerId" } },
});

switch (result.kind) {
  case PlanKind.ALWAYS_DENIED:  return [];
  case PlanKind.ALWAYS_ALLOWED: return await prisma.expense.findMany();
  case PlanKind.CONDITIONAL:    return await prisma.expense.findMany({ where: result.filters });
}

// WRONG — fetches everything, breaks pagination, and scales with the table
const all = await prisma.expense.findMany();
const visible = all.filter(e => check(e));
```

All three `PlanKind` branches must be handled. Treating the result as a `where` clause alone leaks every row when the plan comes back `ALWAYS_DENIED`.

### Deny wins, and policies are deny-by-default

Nothing is permitted unless a rule allows it, and a `EFFECT_DENY` rule overrides any allow. A missed deny is a hole, so confirm intent rather than inferring it.

### Tests live beside policies

A `*_test.yaml` suite next to the policy it exercises runs locally with `cerbos compile` and again in Hub on every build. A failing suite blocks the bundle and leaves the previous one serving.

## Common mistakes

1. Expecting the PDP to look data up — it never does.
2. Enforcing on a browser-side check instead of re-checking on the server.
3. Fetching a list and filtering it in application code instead of using `planResources`.
4. Naming a test suite `tests.yaml` — a suite must end in `_test` before the extension, or it is read as a policy and rejected.
5. Using a store credential where a deployment credential is required, or the reverse. They are not interchangeable.
6. Writing audit mask paths in `snake_case`. Protobuf field segments resolve by lowerCamelCase JSON name, and **a path that matches nothing is silently accepted**, so the data ships anyway.
7. Putting a `README.md` or `.github/` into a Hub policy store — stores accept only `.json`, `.yaml` and `.yml`, and reject dot-prefixed paths.

## Repository layout

Skills live in `cerbos/<skill-name>/SKILL.md`, with deeper material under `references/` and any executable helpers under `scripts/`. `plugins/cerbos-skills/skills` symlinks to `cerbos/`, so a new skill directory needs no plugin registration — but add a row to the README table.

Run `scripts/validate-skills` before opening a pull request; `--links` also resolves every external URL.
