---
name: cerbos-authz-migration
description: Migrate an existing authorization implementation to Cerbos. Use when moving permission checks out of application code (scattered role checks, a `can()` helper, middleware guards, a database permissions table), when replacing another authorization system (OPA/Rego, Casbin, Oso, SpiceDB, OpenFGA, Keycloak authorization services, AWS Cedar), when auditing where a codebase currently decides who may do what, or when consolidating permission logic that has spread across services.
license: Apache-2.0
metadata:
  author: cerbos
  version: "1.0"
---

# Cerbos Authorization Migration

Find the rules that already exist, extract them into a spec, map them onto the Cerbos model, and cut over behind a shadow period.

This skill produces a **spec and a cutover plan**, not policy YAML. Generation, tests and validation belong to `cerbos-policy`, and Phase 2 produces exactly the spec its intake consumes.

## What the move buys

Say this much and no more. Cerbos decouples authorization from application code: the rules become files with tests and a review history, one engine answers for every service, and every decision is logged with the inputs that produced it. That is the case. Do not claim the source system is worse at expressing rules — for relationship-heavy models it is often better, and Phase 3 says so out loud.

## Workflow phases

Complete each phase before starting the next.

### Phase 0 — Frame

Three answers before any searching.

**Source.** Hand-rolled checks in application code, a named authorization system, or both. Both is the common case: an engine for the coarse rules and `if` statements for everything it could not express. Run Phase 1 over the code regardless — a named system never holds all of the rules.

**Slice.** Migrate one resource kind end-to-end before starting the second. Pick one that carries at least one conditional rule (ownership, tenancy, status) and is not on the most critical path: enough to test the model, not enough to bet the business on.

**Destination.** Where the policies live and how they reach a PDP.

| Destination | Fits | Role in a migration |
|---|---|---|
| **Cerbos Hub playground** | Phases 3-4, always | Prototype the mapping in a browser, side by side with the old rules, before committing to anything |
| **Cerbos Hub policy store + deployment** (default) | Phases 4-6 | During shadow mode you edit rules daily; Hub compiles, runs the suites, pushes to every PDP in seconds, and freeze/rollback is the migration's undo |
| **Git repository** | One PDP, one environment, an existing pipeline | Commit and let the pipeline distribute; you own testing and rollback |

Setup is `cerbos-hub-setup`. Record the answers and carry on — moving between destinations later is PDP configuration, not a policy rewrite.

### Phase 1 — Discover

Produce a list of **guards**: every site in the system that decides whether *this* principal may do *this* thing.

**The discriminator.** Authorization varies with the subject; validation varies with the payload. Ask of every candidate: *would a different user sending an identical request get a different answer?* Yes, it is a guard. No, it is validation, a state machine, or a rate limit — leave it where it is.

| Check | Guard? | Why |
|---|---|---|
| `if (user.role !== 'admin') return 403` | Yes | Answer depends on who asks |
| `if (!user) return 401` | No | Authentication. Cerbos consumes its output, does not replace it |
| `if (order.status !== 'DRAFT') throw` | No | Same answer for everyone |
| `if (order.status !== 'DRAFT' && !user.isAdmin) throw` | **Mixed** | Split it: the `isAdmin` half is a guard, the status half becomes a `condition` on the rule |
| `if (!user.plan.includes('pro')) return 402` | Yes | Entitlement is authorization; it moves |
| `WHERE tenant_id = :currentTenant` in a query | Yes | An enforcement point that filters rather than refuses |

Mixed checks are the normal case, not the exception. Splitting them is most of the work of this phase.

**Where guards hide.** Route middleware and decorators; ORM scopes and query builders that quietly filter by tenant or owner; a `can()` / `authorize()` / `Policy` helper; a permissions table in the database; framework superuser short-circuits; feature flags doing entitlement work; UI conditionals that reveal intent but enforce nothing; and the existing authorization tests, which are often the most accurate statement of intent in the repository.

Grep catalogue by language and framework, database permission-table shapes, and how to read a `can()` helper: [references/DISCOVERY.md](references/DISCOVERY.md).

**Completion criterion.** Every entry point in the slice either reaches a guard on the list or is recorded as deliberately unguarded. The unguarded list is a deliverable — take it to the user and ask whether each one is intentionally public. Unguarded endpoints found this way are the most valuable output of a migration that has not yet moved a single rule.

### Phase 2 — Extract

Turn each guard into one or more rows of **Structured Intent**. Six elements per rule, the same six `cerbos-policy` requires:

| Intent | Question | Cerbos construct |
|---|---|---|
| **Subject** | Who is acting? | `principal` roles / derived roles |
| **Action** | What are they doing? | rule `actions` |
| **Resource** | On what object? | resource `kind` |
| **Condition** | Under what context? | CEL `condition` (omit for pure RBAC) |
| **Decision** | Allow or Deny? | rule `effect` (`EFFECT_ALLOW` / `EFFECT_DENY`) |
| **Purpose** | Why is this needed? | rule `name` + comment above the rule |

Add one migration-only column, **Source**, naming where the rule came from — `src/api/orders.ts:142`, `policy.csv:17`, `orders.rego:31`. Source is what makes coverage provable at the end.

```
Source | Subject (role) → Action on Resource [Condition] | Effect | Purpose
src/api/orders.ts:142 | manager → approve on order [R.attr.amount < 1000] | ALLOW | Managers sign off small orders without finance
```

**Completeness gate.** A row missing any of the six is not generatable. Two elements are almost never written down in the source and must be asked, never inferred:

- **Decision.** Cerbos is deny-by-default and a deny beats an allow for the same role, so a missed deny is a hole. Hand-rolled code expresses deny as an early return, a thrown exception, or an absent branch — all easy to read as "no rule here". Confirm every one.
- **Purpose.** The reason a rule exists rarely survives in the code. A migration is the last moment someone still remembers it; capture it now or lose it permanently.

Group rows by resource kind. That grouping is the policy file layout and the cutover order.

Every guard from Phase 1 appears in at least one row, or on the gap register from Phase 3 with a reason. Nothing is silently dropped.

### Phase 3 — Map

Decide which Cerbos construct carries each row, and record what does not fit.

| What the source expresses | Cerbos construct |
|---|---|
| A static role from the IdP | `roles` on a rule |
| A role that only holds in context — owner, team member, same region | [derived role](https://docs.cerbos.dev/cerbos/latest/policies/derived_roles) with a `condition` |
| A per-user exception or override | [principal policy](https://docs.cerbos.dev/cerbos/latest/policies/principal_policies) (evaluated first; an explicit effect there is final for that action) |
| An exhaustive cap — "this role may do only these things" | [role policy](https://docs.cerbos.dev/cerbos/latest/policies/role_policies) `allowActions`, which narrows but cannot grant |
| A tenant, region or department variant of a rule set | [scoped policies](https://docs.cerbos.dev/cerbos/latest/policies/scoped_policies), plus `scopePermissions` to choose override-parent or require-parental-consent |
| A predicate over request data | CEL [`condition`](https://docs.cerbos.dev/cerbos/latest/policies/conditions) |
| The same predicate in many rules | [exported variable](https://docs.cerbos.dev/cerbos/latest/policies/variables); a shared literal is an exported constant |
| An org chart or containment path | dotted scope strings plus the [hierarchy CEL functions](https://docs.cerbos.dev/cerbos/latest/recipes/hierarchies-and-multi-tenancy) |
| A list endpoint or ORM scope | [`PlanResources`](https://docs.cerbos.dev/cerbos/latest/recipes/filtering-resources) and a query plan adapter |
| Per-tenant custom roles defined by users at runtime | Static policies, dynamic context: pass the assignments as principal attributes |
| "Who is this user, what are their attributes" | Request attributes, supplied by the PEP. Not policy |

Per-source mapping tables: [references/MAPPING-CODE.md](references/MAPPING-CODE.md) for hand-rolled code, [references/MAPPING-SYSTEMS.md](references/MAPPING-SYSTEMS.md) for OPA/Rego, Casbin, Oso, SpiceDB/OpenFGA, Keycloak and Cedar.

**The one constraint that reshapes rules.** The PDP is stateless and holds none of your data. Every fact a condition needs arrives in the request. A rule that today runs a query — *is this user in the group, does the parent folder grant access, how many seats has this account used* — becomes a rule over an attribute somebody has to supply. Three ways: the PEP resolves it before calling (`cerbos-pep-integration`), a Synapse data source fetches it inside the authorization path (`cerbos-synapse-extension`), or the existing service keeps answering that one question and Cerbos consumes the answer.

**Gap register.** One row per thing that does not survive the move, each ending in a decision the user makes.

| Gap | Where it bites | Options |
|---|---|---|
| Ordered / first-match rule evaluation | Casbin priority models, firewall-style rule lists | Cerbos has fixed conflict resolution — deny wins for a role, allow wins across roles. Restate the intent; there is no ordering knob |
| Graph reachability over stored relationships | SpiceDB, OpenFGA, Oso relations, Cedar `in` chains | Resolve to an attribute, fetch via Synapse, or keep the relationship service. See MAPPING-SYSTEMS.md — this one is real and not papered over |
| Effects beyond allow and deny | Keycloak consensus strategies, Rego `warn` sets, audit-only modes | The API returns `EFFECT_ALLOW` or `EFFECT_DENY`. An [output](https://docs.cerbos.dev/cerbos/latest/policies/outputs) can carry a message alongside the decision but does not change it |
| Rules that compute data rather than decide | Rego rules producing documents, transforms, aggregations | A condition must evaluate to boolean. This logic stays in the application |
| Conditions needing a join or an aggregate | ORM scopes spanning tables, seat counts, quota checks | Expressible over resource attributes → `PlanResources`. Otherwise it stays in the query |
| Stateful conditions | Rate limits, counters, "third attempt today" | `now()` exists; state does not. Keep these outside Cerbos |

Confirm the register with the user before generating anything. Every row is a deliberate decision, recorded.

### Phase 4 — Prototype, then generate

**Prototype in a Hub playground.** Drop the policy files and fixtures straight in, and paste the old rules into a `README.md` so the source sits beside its translation in the same editor. Three things earn the detour: the permissions matrix renders the resource as a role-by-action grid you can compare against the old system's grid directly, execution traces explain every decision rule by rule, and effective derived roles are shown so you can see which context roles actually activated. Nothing is installed, and a colleague can open the same playground. Take the hardest rows from Phase 2 there first — the conditional ones and anything on the gap register.

**Then generate.** Hand the Phase 2 inventory and the Phase 3 mapping to `cerbos-policy`. Its spec intake consumes the Structured Intent rows as they stand, so it starts at generation rather than re-interviewing the user. It owns the policy files, the `*_test.yaml` suites, validation and the upload.

Ask it for one test case per inventory row, named after the Source. A suite that mirrors the inventory is what proves the migration later.

### Phase 5 — Shadow

Run both systems. Log both decisions. **Return the old one.** The old system stays authoritative until the diff is clean — this ordering is the whole safety property of the migration.

1. **Shim each guard.** At the call site, keep the existing check, add a Cerbos check, record both with a correlation ID, return the legacy answer. Behind a flag, per resource kind, so any guard can be dropped out of shadow in one move. Wiring the call and assembling the request attributes is `cerbos-pep-integration`.
2. **Collect the Cerbos side.** Turn on Hub [audit log collection](https://docs.cerbos.dev/cerbos-hub/audit-log-collection). Each decision arrives with the principal, roles, effective derived roles, resource attributes, the matched policy and the effect — which is the whole right-hand column of the diff, without building a decision log during the riskiest week of the project. Reading and querying them is `cerbos-audit-insights`.
3. **Diff and triage.** Every disagreement is explained before the period ends. The triage table below covers what each direction usually means.
4. **Fix and redeploy.** Most fixes are a missing attribute or a missed rule, both of which land in the policy store and reach every PDP in seconds. Add the failing case to the test suite as you go, so the diff you closed cannot reopen.

| Disagreement | Usual cause, in order |
|---|---|
| Cerbos DENY, legacy ALLOW | A missing request attribute, so the condition could not hold. Then: a rule missed in Phase 1, usually an implicit grant. Then, genuinely: the legacy system was permitting something it should not — verify before "fixing" it |
| Cerbos ALLOW, legacy DENY | An implicit deny not captured: an early return, an exception path, a filter applied before the guard, a superuser branch. Then: a wildcard action or `roles: ["*"]` that matched more than intended |
| Same input, inconsistent verdicts | A time-dependent or state-dependent condition, or the two sides reading the attribute at different moments in the request |
| Cerbos DENY on everything for one resource kind | No policy for that kind or version, or a scope in the request with no matching policy file. Cerbos is deny-by-default, so an absent policy denies rather than abstains |

**Exit criterion.** A full business cycle of traffic — long enough to include a month-end, a batch job, an on-call escalation, whatever your system's rare paths are — with zero unexplained disagreements. Every remaining difference is a recorded, deliberate decision.

### Phase 6 — Cut over

Per resource kind, in the order of Phase 2's grouping:

1. Flip the flag so the Cerbos decision is the one returned. Keep the shim's logging: the legacy check now runs as the shadow.
2. Watch the decision volume and the allow/deny ratio for that kind. A sudden swing is the signal that something moved that should not have.
3. **Delete the old path.** Removal is part of the migration, not a follow-up ticket. Code left behind becomes a second source of truth, and the next engineer edits the wrong one.
4. Move to the next kind.

Rollback has two levers, and both should be tested before the first flip: the shim flag returns one resource kind to the legacy decision, and freezing or rolling back the Hub [deployment](https://docs.cerbos.dev/cerbos-hub/deployments) pins every PDP to a known-good bundle while you diagnose.

When the last guard is gone, report the coverage: rows migrated, rows on the gap register with their decisions, and the unguarded entry points found in Phase 1 with what was done about each.

## References

| Reference | When |
|---|---|
| [references/DISCOVERY.md](references/DISCOVERY.md) | Phase 1. Grep catalogue by language and framework, database permission-table shapes, mining tests for intent, the negative space |
| [references/MAPPING-CODE.md](references/MAPPING-CODE.md) | Phase 3, hand-rolled source. Inline checks, `can()` helpers, middleware, ORM scopes, permission tables, feature flags |
| [references/MAPPING-SYSTEMS.md](references/MAPPING-SYSTEMS.md) | Phase 3, named source. OPA/Rego, Casbin, Oso, SpiceDB/OpenFGA, Keycloak authorization services, AWS Cedar |
| [references/CUTOVER.md](references/CUTOVER.md) | Phases 5-6. Shim shape, correlation, diff report, rollout stages, rollback drill |

## Sibling skills

| Skill | Owns |
|---|---|
| `cerbos-policy` | Policy and test generation, CEL, validation, upload. Phase 4 hands off to it |
| `cerbos-hub-setup` | Workspace, policy store, deployment, credentials, audit log collection |
| `cerbos-pep-integration` | The call site: SDK wiring, request construction, attribute plumbing, `PlanResources` adapters |
| `cerbos-audit-insights` | Querying decision logs — the Cerbos half of the shadow-mode diff |
| `cerbos-synapse-extension` | Fetching attributes inside the authorization path when the PEP cannot supply them |
