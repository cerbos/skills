---
name: cerbos-authz-analysis
description: Extract the authorization model from an existing codebase into an evidence-backed AUTHORIZATION_MODEL.md. Use when planning a migration to Cerbos, auditing access control for coverage gaps, or asked "who can do what" in an app.
license: Apache-2.0
metadata:
  author: cerbos
  version: "1.0"
allowed-tools: Read Write Edit Bash Glob Grep Task WebFetch
---

# Cerbos Authorization Model Analysis

Extract the complete, evidence-backed authorization model from an existing application and
produce `AUTHORIZATION_MODEL.md` — the reviewed input for the `cerbos-policy-migration`
skill. This skill only observes and documents; it never modifies application code.

Two principles govern everything:

- **Evidence or it didn't happen.** Every rule, attribute source, and classification cites
  `file:line`. Anything inferred gets a confidence marker; anything ambiguous becomes an
  open question. Never present a guess as a finding.
- **Record, don't improve.** The document captures what the code does today, including
  inconsistencies and gaps. Improvements are listed separately and never folded into the
  observed model — behavior parity is what makes the later migration verifiable.

## Workflow

### Phase 1 — Scope

Identify the deployable services in the repo (build files, compose/deploy manifests,
package roots). Confirm with the user which **one** service this run analyzes — one
service per run, one model document per service. Detect its stack: language, web
framework, ORM, auth library/IdP. In a monorepo, state explicitly what is excluded.

### Phase 2 — Entry-point inventory

Enumerate **every** externally reachable operation before analyzing any of them: HTTP
routes, GraphQL resolvers, gRPC methods, queue/event consumers, scheduled jobs, WebSocket
handlers. Use the per-framework discovery patterns in
[references/EXTRACTION.md](references/EXTRACTION.md). Where the framework can dump its
route table at runtime, prefer that as the completeness check against static discovery.

Record the total. This number is the completeness contract: the final document states
"N of N entry points analyzed", and every entry point gets a row even when the finding is
"no authorization present".

For large codebases, fan out parallel subagents (Task tool) — one per module or route
group — each returning inventory rows in the exact table format of
[references/MODEL-TEMPLATE.md](references/MODEL-TEMPLATE.md) §A3.

### Phase 3 — Rule extraction

For each entry point, classify its guard mechanism and trace the authorization logic
inward through the call chain (guard catalog and tracing rules in
[references/EXTRACTION.md](references/EXTRACTION.md)). Capture:

1. **Rules** (§A5) — subject, action, condition quoted **verbatim** plus a plain-English
   translation, effect, evidence, confidence. Every Low-confidence row must have a
   matching open question.
2. **Attribute provenance** (§A6) — for every attribute a rule reads: JWT claim, session,
   DB column, request param, or derived — with evidence. This later decides where checks
   can be placed.
3. **Scenarios** (§A7) — concrete allow *and* deny examples per rule; these become the
   generated policy test suite.
4. **Coverage gaps** (§A8) and **dead checks** (§A10).

Backend code is authoritative. Frontend permission gating, seed/migration files (role
tables, permission fixtures), IdP/auth config, and OpenAPI security schemes are
*supporting* evidence — use them to corroborate role catalogs and flag intent, never as
proof of enforcement.

Phase 3 is complete when every Phase 2 inventory row carries either extracted rules or an
explicit `none`/`public` classification — the entry-point count and the analyzed count
match.

### Phase 4 — Cerbos mapping proposal

Fetch the latest modeling guidance before proposing anything: get
`https://docs.cerbos.dev/llms.txt` and read the current best-practices and policy-type
pages it links. Then, following [references/MAPPING.md](references/MAPPING.md), draft
Part B: modeling approach, principal roles and derived-role candidates, resource kinds
with required attributes, the Structured Intent rule table (every row traced to a Part A
rule), and the per-endpoint `CheckResources` vs `PlanResources` enforcement plan.

Anything that would *change* behavior — tightening an over-broad grant, adding a missing
deny — goes in §B7 as an explicitly deferred improvement.

### Phase 5 — Emit document

Write `AUTHORIZATION_MODEL.md` at the analyzed service's root using the exact structure in
[references/MODEL-TEMPLATE.md](references/MODEL-TEMPLATE.md), Status: DRAFT. Do not
deviate from the section headings or table columns — the migration skill parses them.

### Phase 6 — Guided review

Walk the user through the document as a working session, in this order:

1. Each **open question** (§A9) — present the evidence conflict and concrete options.
2. Each **Low/Medium-confidence** rule — confirm or correct.
3. **Coverage gaps** (§A8) — intentional or a finding to fix?
4. **Part B decisions** — modeling approach, derived roles, kind boundaries, enforcement
   plan.

Update the document as answers land and append each resolution to the Review log.
Questions the user cannot answer stay open — flagged for `cerbos-policy-migration` to
re-raise. When the user approves, set Status: REVIEWED and add the approval line. Never
self-approve.

### Phase 7 — Handoff

Report: entry points analyzed, rules extracted, coverage gaps, unresolved questions. Then
point to the next step: run the **cerbos-policy-migration** skill against the approved
document to generate policies, then **cerbos-sdk-integration** to wire them in.

## References

- [references/MODEL-TEMPLATE.md](references/MODEL-TEMPLATE.md) — canonical AUTHORIZATION_MODEL.md structure (the output contract)
- [references/EXTRACTION.md](references/EXTRACTION.md) — per-framework entry-point discovery, guard-signal catalog, tracing and confidence rules
- [references/MAPPING.md](references/MAPPING.md) — translating the observed model into Cerbos constructs, with live documentation sources
