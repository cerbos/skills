# Mapping reference — observed model → Cerbos constructs

How to turn Part A observations into the Part B proposal. The mapping is a translation,
not a redesign: every Part B row traces to a Part A rule, and anything that would change
behavior goes to §B7 (deferred improvements).

## 0. Fetch the live documentation first

Cerbos policy features and best practices evolve. Before drafting Part B, fetch
`https://docs.cerbos.dev/llms.txt` and read the current versions of at least:

- the **best practices** page (modeling approaches: action-led, role-led, hybrid,
  attribute-led; policy repository layout)
- the **derived roles**, **resource policies**, **role policies**, and **scoped
  policies** pages
- the **schemas** page (principal/resource attribute schemas)

Base the mapping on what those pages say today, not on this file alone.

## 1. Vocabulary translation

| Observed in code (Part A) | Cerbos construct |
|---|---|
| Role strings on the user (`user.role`, `roles[]` claim) | Principal `roles` |
| Ownership / relationship checks (`x.ownerId === user.id`, membership lookups) | **Derived roles** (`owner`, `member`, …) with the relation as the membership condition |
| Permission/action catalog (permission tables, ability lists) | Rule `actions` — prefer the domain's verbs (`approve`, `publish`) over generic CRUD when the code distinguishes them |
| The nouns being guarded (models behind endpoints) | Resource `kind` |
| Contextual conditions (status, amounts, time, plan tier) | CEL `condition` on the rule |
| Tenant isolation (`orgId` equality everywhere) | Scoped policies (hierarchical tenants) or a tenant-equality condition — see §5 |
| Admin bypass (`if admin: allow all`) | A rule granting `actions: ['*']` to the admin role — keep it visible, don't bury it per-action |
| Explicit rejections (blocklists, suspended users) | `EFFECT_DENY` rules — deny overrides allow in Cerbos, mirroring the early-return in code |
| Data-layer scoping (default scopes, RLS) | The policy condition that `PlanResources` will reproduce as a query filter |

## 2. Choosing the modeling approach (B1)

Read Part A's shape:

- Few roles, many context conditions → **action-led** resource policies (rules per
  action, conditions inline).
- Many roles with clear per-role permission sets (permission-table-driven apps) →
  **role-led** (role policies / role-centric rules).
- Both → **hybrid**: resource policies for the common shape, role policies for the
  exceptional roles.
- Almost no roles, everything attribute-driven → attribute-led resource policies leaning
  on derived roles.

State the choice and rationale in two sentences in B1. When genuinely borderline, present
both options in the review session rather than deciding silently.

## 3. Resource kinds and actions

- Kind per domain noun (A4), lower_snake or kebab per the team's naming taste —
  consistent across the document.
- The kind for an entry point is the noun the handler **acts on**, never the controller/
  module/route name — domain-named controllers routinely operate on other resources (an
  account-admin route editing surveys checks the `survey` kind). If one handler mutates
  two nouns, that is two check calls against two kinds, not a merged kind.
- Don't invent granularity the code doesn't have: if the code only ever distinguishes
  read vs write, two actions beat seven CRUD verbs. Conversely, if the code guards
  `approve` differently from `update`, they are distinct actions.
- Required attributes (B3) come strictly from the conditions in A5 + provenance in A6 —
  an attribute no rule reads does not belong on the kind. These become the JSON schemas
  (`_schemas/`) at generation time.

## 4. Structured Intent rows (B4)

Each row must answer the six questions the `cerbos-policy` skill's intake demands —
Subject, Action, Resource, Condition, Decision, Purpose — plus `Source` (the A5 rule).

- **Subject**: a principal role or a derived role from B2 — never a raw user id
  (per-user grants observed in code are a review-session discussion: usually a data
  attribute, occasionally a principal policy).
- **Condition**: CEL-shaped, using `P.attr.*` / `R.attr.*` names defined in B2/B3. Keep
  the A5 verbatim expression reachable through `Source`.
- **Decision**: explicit ALLOW or DENY. Parity rule: if code was allow-by-default-behind-
  auth for some action, that's a finding (A8), not a silent wildcard allow here.
- **Purpose**: one line, written for the audit trail ("parity with legacy X check" is a
  valid purpose during migration).

## 5. Multi-tenancy (B6)

- Flat tenancy (every resource carries `orgId`, checked for equality) → a shared
  tenant-equality condition (commonly via a derived role or common variable) — simple and
  sufficient for most.
- Hierarchical tenancy or per-tenant rule *differences* observed in code/config →
  propose **scoped policies**; sketch the scope tree.
- Per-tenant custom roles defined in data → note it; the live best-practices page covers
  static vs dynamic custom-role patterns — follow its current recommendation.

## 6. Enforcement plan (B5)

Classify every entry point:

- Single object fetched then acted on → `CheckResources` — placed where the resource is
  loaded (service layer) when rules need DB-loaded attributes (check A6), middleware only
  when every referenced attribute is request-time.
- List/search/index endpoints whose rows depend on per-row conditions (ownership, tenant,
  status) → `PlanResources`, applied as a query filter at the data layer.
- List endpoints gated purely by role (no per-row condition) → a single `CheckResources`
  on the kind.
- Batch operations → one `CheckResources` call with multiple resource instances, not N
  calls.

The `cerbos-sdk-integration` skill consumes this column verbatim — mistakes here surface
as N+1 checks or double-fetches there.

## 7. What NOT to map

- **Improvements** — over-broad grants, missing denies, inconsistencies between endpoints
  guarding the same resource: §B7, deferred, each with what would change and why it waits.
- **Dead checks** (A10) — excluded until the user confirms deletion intent.
- **Authentication** — establishing *who* the principal is stays in the app/IdP; Cerbos
  consumes the result. If A2 shows authn and authz tangled, note the untangling as a B7
  item.
