# AUTHORIZATION_MODEL.md template

This is the canonical structure of the model document the analysis produces. It is the
contract consumed by the `cerbos-policy-migration` skill — keep every section heading and
table column exactly as shown. Guidance for filling each section appears as `> notes`;
remove the notes from the generated document.

Two invariants:

- **Part A records what the code does today** — observations only, each with evidence.
  Never "improve" the model here; discrepancies and bad patterns are recorded, not fixed.
- **Part B proposes the Cerbos translation** of Part A — a design, marked as proposal
  until the review session approves it.

---

```markdown
# Authorization Model — <service name>

| | |
|---|---|
| **Status** | DRAFT \| REVIEWED — do not generate policies from a DRAFT document |
| **Service** | <repo-relative path of the analyzed service> |
| **Analyzed at** | <ISO date> · commit `<short sha>` |
| **Entry points analyzed** | <n> of <total discovered> |

## Part A — Observed model

### A1. Scope

> One paragraph: the deployable unit analyzed, its stack (language, framework, ORM,
> auth library/IdP), and anything deliberately excluded (other services, admin CLIs).

### A2. Identity and principal sources

> How a request becomes an authenticated identity: auth mechanism (JWT/session/mTLS/…),
> which middleware establishes it, and — critically — where **roles** come from
> (token claim, DB table, IdP group mapping, hardcoded list). Cite file:line for each.

### A3. Entry-point inventory

> Every externally reachable operation: HTTP routes, GraphQL resolvers, gRPC methods,
> queue/event consumers, scheduled jobs, WebSocket handlers. This table defines
> completeness — every row must be classified, even if the classification is `none`.
> Enforcement: `single` (per-object check), `list` (result-set filtering), `role-gate`
> (coarse role/permission gate only), `none` (no authz found), `public` (intentionally
> unauthenticated — cite the evidence for "intentional").

| EP | Operation | Handler (file:line) | Guard mechanism | Rules | Enforcement | Confidence |
|----|-----------|---------------------|-----------------|-------|-------------|------------|
| EP-01 | `GET /invoices/:id` | `src/routes/invoices.ts:42` | `requireAuth` + inline owner check | R-03 | single | High |

### A4. Resources

> The nouns users act on, with their backing model/table and which entry points touch them.

| Resource | Backing model (file:line) | Entry points |
|----------|---------------------------|--------------|

### A5. Authorization rules

> Every distinct rule observed, per resource. `Condition (verbatim)` quotes the actual
> code expression; `Condition (plain)` translates it. Confidence: **High** = explicit
> code evidence; **Medium** = inferred from a pattern (e.g. framework convention);
> **Low** = ambiguous — every Low row MUST have a matching open question in A9.

| Rule | Resource | Subject | Action | Condition (verbatim) | Condition (plain) | Effect | Evidence (file:line) | Confidence |
|------|----------|---------|--------|----------------------|-------------------|--------|----------------------|------------|
| R-03 | invoice | any authenticated | view | `inv.ownerId === user.id \|\| user.role === 'admin'` | owner or admin | allow | `src/routes/invoices.ts:47` | High |

### A6. Attribute provenance

> Every identity/resource attribute the rules depend on, and where its value lives at
> request time. This drives enforcement placement later: request-time attributes allow
> middleware checks; DB-loaded attributes force service-layer checks.

| Attribute | Of | Source | Available | Evidence (file:line) |
|-----------|----|--------|-----------|----------------------|
| `role` | principal | JWT claim `role` | request time | `src/auth/middleware.ts:18` |
| `ownerId` | resource: invoice | DB column `invoices.owner_id` | after load | `src/models/invoice.ts:12` |

### A7. Observed scenarios

> Concrete allow/deny examples per rule — these become the policy test suite, so include
> both the allow and the deny side of every rule, plus observed edge cases.

| Scenario | Principal | Resource | Action | Expected | From rule |
|----------|-----------|----------|--------|----------|-----------|
| S-01 | role=member, id=u1 | invoice ownerId=u1 | view | ALLOW | R-03 |
| S-02 | role=member, id=u2 | invoice ownerId=u1 | view | DENY | R-03 |

### A8. Coverage gaps

> Entry points classified `none` that do not appear intentionally public, and mutations
> guarded only by authentication. This is a security finding list — neutral tone, evidence
> only.

### A9. Open questions

> Numbered. Each states the ambiguity, the evidence conflict, and which rules/rows are
> blocked on the answer. Every Low-confidence row must appear here.

### A10. Dead and unreachable checks

> Authorization code that appears unused (unreferenced guards, checks behind disabled
> flags). Flag for confirmation — do not migrate without it.

## Part B — Proposed Cerbos mapping

### B1. Modeling approach

> Chosen approach (action-led / role-led / hybrid / attribute-led) with a two-sentence
> rationale grounded in Part A's shape. See MAPPING.md for how to choose.

### B2. Principals and derived roles

> Static roles carried on the principal, and derived-role candidates (owner, same-team,
> …) with their CEL-shaped membership conditions and the A5/A6 rows they come from.

### B3. Resource kinds

| Kind | From resource (A4) | Attributes required | Provenance (A6) |
|------|--------------------|---------------------|-----------------|

### B4. Policy rules (Structured Intent)

> One row per proposed rule, answering all six Structured Intent questions used by the
> `cerbos-policy` skill. `Source` ties back to A5 — every row must trace to observed
> behavior. Behavior-parity is the rule: the mapping may reorganize, never redefine.

| Subject | Action | Resource | Condition | Decision | Purpose | Source |
|---------|--------|----------|-----------|----------|---------|--------|
| derived: owner OR role: admin | view | invoice | — | ALLOW | Owners and admins can view invoices (parity with legacy owner check) | R-03 |

### B5. Endpoint enforcement plan

> How each entry point will call Cerbos: `CheckResources` (single) or `PlanResources`
> (list), and where the call belongs given attribute provenance.

| EP | API | Placement | Notes |
|----|-----|-----------|-------|
| EP-01 | CheckResources | service layer (resource loaded) | |

### B6. Scopes and multi-tenancy

> Only if Part A shows tenant isolation: proposed scope hierarchy or tenant attributes.

### B7. Improvement opportunities (NOT applied)

> Everything noticed that would make the model better — inconsistencies, over-broad
> grants, missing denies. Explicitly excluded from the migration; parity first. Each item
> notes what would change and why it is deferred.

## Review log

> Appended by the review session: date, each open question with its resolution, rows
> changed, and the final approval line:
> `Approved for policy generation by <name> on <date>` — the `cerbos-policy-migration`
> skill refuses to run without this line and Status: REVIEWED.
```
