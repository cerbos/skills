---
name: cerbos-policy
description: Generate, modify, and explain Cerbos authorization policies — resource and role policies, derived roles, exported variables, CEL conditions, and `*_test.yaml` suites. Use when writing access control rules from requirements or a spec document (including PDFs), changing what an existing policy allows, or when a Cerbos policy fails to compile or a policy test fails.
license: Apache-2.0
compatibility: Requires Docker for policy validation
metadata:
  author: cerbos
  version: "1.4"
  targetsCerbosVersion: "0.55.0"
allowed-tools: Read Write Edit Bash Glob Grep Task WebFetch
---

# Cerbos Policy Generator

## Prerequisites

Validation runs in Docker, so confirm it is available before writing any files:

```bash
docker --version
```

If it is missing, stop and point the user at [Docker Desktop](https://www.docker.com/products/docker-desktop/) (macOS/Windows) or [docs.docker.com/engine/install](https://docs.docker.com/engine/install/) (Linux). Generation starts once Docker answers.

## Workflow Phases

Complete each phase before starting the next.

### Phase 1 — Spec Intake

Before writing any files, converge on a compact spec by asking clarifying questions in plain business language ("Who can delete a project?"), never schema jargon. Offer concrete options per question where possible — avoid open-ended prompts. Ask as many rounds and as many questions as the requirements genuinely need.

Capture every rule against the **Structured Intent** checklist. Each rule must answer all six questions before it is generatable:

| Intent | Question | Cerbos construct |
|---|---|---|
| **Subject** | Who is acting? | `principal` roles / derived roles |
| **Action** | What are they doing? | rule `actions` |
| **Resource** | On what object? | resource `kind` |
| **Condition** | Under what context? | CEL `condition` (omit for pure RBAC) |
| **Decision** | Allow or Deny? | rule `effect` (`EFFECT_ALLOW` / `EFFECT_DENY`) |
| **Purpose** | Why is this needed? | rule `name` + comment above the rule |

**Completeness gate** — if any of the six is missing for a rule, ask before generating. Confirm **Decision** and **Purpose** with the user rather than inferring them:

- **Decision** is security-critical. Cerbos is deny-by-default and deny rules take precedence over allow rules, so a missed deny is a hole. Always confirm whether a rule grants or revokes.
- **Purpose** is the audit trail. Every rule needs a one-line rationale that survives into the generated YAML, so policies stay self-documenting and reviewable.

Produce a short spec artifact — one row per rule capturing all six elements:

```
Subject (role) → Action on Resource [Condition] | Effect | Purpose
e.g. manager → approve on expense [R.attr.amount < 1000] | ALLOW | Managers sign off small expenses without finance
```

List resources, principals/roles, and shared derived roles/variables alongside. Confirm the spec with the user before generating.

For schema-driven code generation, distinguish database structure from authorization requirements. A table, foreign key, or folder name does not establish who may access it. Keep unresolved business rules as questions in the spec; generate only confirmed rules. Keep a generated baseline independent of business-layer helpers unless a confirmed rule requires that dependency. For relationship-based authorization, establish the access rule, applicable resources, and required input attributes before implementing it.

### Phase 2 — Write

Read [POLICIES.md](references/POLICIES.md) before writing attribute schemas or policy definitions, and [TEST-SUITES.md](references/TEST-SUITES.md#coverage-plan) before writing fixtures and tests.

Save a **coverage plan** outside the policy directory before writing tests. Give each resource/action its allowed request, independent denial prerequisites, and applicable boundaries, defaults and role combinations. Map every row to concrete fixture keys and an expected effect; for isolated denials, also name the ALLOW control and the request field that changes. Shared definitions need coverage in every consuming resource policy.

Before writing variables or imports, read [Variable dependency design](references/POLICIES.md#variable-dependency-design). Generate each policy's dependencies from its actual expressions, including transitive variable references; a shared template must not attach every available variable set to every resource.

Batch-write all files in a single pass, in this order:

1. `_schemas/` (principal + resources)
2. `derived_roles/` (shared roles and exported-variable files, only where required by the spec)
3. `resource_policies/` / `role_policies/`
4. `testdata/` fixtures
5. `*_test.yaml`

Into this layout:

```
_schemas/                    # Attribute schemas (at root)
  principal.json
  resources/
    <resource>.json
derived_roles/
  common_roles.yaml          # Shared derived roles
  common_vars.yaml           # Optional shared exported variables
  <concern>_vars.yaml         # Additional focused sets where needed
principal_policies/
  <name>.yaml
resource_policies/
  <domain>/                  # Group by domain (hr, finance, etc.)
    <resource>.yaml
    <resource>_test.yaml     # Test files must end in _test
    testdata/                # Fixtures, shared across the domain
      principals.yaml
      resources.yaml
role_policies/               # Role-centric ABAC
  <role>.yaml                # Base role policies
  <tenant>/                  # Scoped policies per tenant
    <role>.yaml              # Narrowed role with parentRoles + scope
```

Every YAML file MUST begin with a `# yaml-language-server: $schema=...` header so LSP-aware editors validate the file. Policies use the `Policy.schema.json` URL, test suites use `TestSuite.schema.json`, and fixtures use the matching `TestFixture/*.schema.json`. See [POLICIES.md](references/POLICIES.md) and [TEST-SUITES.md](references/TEST-SUITES.md) for the exact URLs.

Carry the **Purpose** captured in Phase 1 into every rule: set a descriptive rule `name` and record the rationale as a comment above the rule. Rules must not ship without their "why" — the audit trail is part of the deliverable, not optional.

Write every file before validating anything.

### Phase 3 — Validate

First audit dependencies using [Variable dependency design](references/POLICIES.md#variable-dependency-design). Every retained import must supply a variable or derived role reachable from the policy's conditions or outputs, with its attribute requirements satisfied by that policy's inputs. Preserve transitive dependencies and dependencies used by other policies when pruning shared definitions.

Launch one fresh coverage-review subagent using [COVERAGE-REVIEW.md](references/COVERAGE-REVIEW.md). Give it the original confirmed requirements and bundle path, not your coverage plan as its checklist. Keep its work read-only while you run compilation and the fixture audit below. This independent derivation catches requirements omitted from both a plan and its checker. If subagents are unavailable, perform the same requirements-first review as a separate pass and report that it was not independent.

Run two passes. The first compiles the policies and runs the tests:

```bash
docker run --rm -v "$(pwd):/policies" ghcr.io/cerbos/cerbos:latest compile /policies
```

The second re-runs the tests with strict evaluation, which turns runtime CEL errors into denials instead of silently treating them as false:

```bash
docker run --rm -v "$(pwd):/policies" ghcr.io/cerbos/cerbos:latest compile --strict-evaluation /policies
```

Both must exit 0. Then run the [coverage audit](references/TEST-SUITES.md#coverage-audit): a one-off executable check that loads the emitted fixtures and the compiler's JSON report (`--output=json`), verifies the planned request pairs, and confirms each planned assertion executed. Save the check and its per-row results outside the policy directory. A compiler pass count alone cannot establish that a denial exercised the intended boundary.

Wait for the coverage reviewer. Reconcile every row it derives with the written tests, extend the plan and tests for supported gaps, and rerun both compilation modes and the audit after repairs. Retain its findings and their resolution outside the policy directory.

A test that passes the first pass but fails the second has a condition erroring at runtime — most dangerously on a DENY rule, where the error makes the deny silently no-op and the action gets allowed. Treat it as a real defect and fix it in Phase 4; keep the strict pass in place while doing so.

Otherwise capture the error list and move to Phase 4.

### Phase 4 — Fix

Apply one targeted fix per iteration, re-validating after each. Work in this priority order — a lower-priority error often disappears once a higher one is fixed:

1. YAML parse errors
2. CEL syntax errors
3. Schema validation errors (`additionalProperties: false`)
4. Compile errors (unresolved imports, missing derived roles, unknown variables)
5. Test failures

Rules:
- Fix shared files (`derived_roles/`, `common_vars.yaml`) before resource policies
- Fix the policy or the fixture — never delete a test to make validation pass
- Give up and report if the same error persists after **3** different fix attempts
- When a condition fails in a non-obvious way, use the REPL (see [references/TESTING.md](references/TESTING.md)) rather than patching blindly

### Phase 5 — Finalize

Finish when the requirements-first review has no unresolved coverage gaps, both validation passes and the executable coverage audit exit 0, and every planned row has a passing audit result. Report what was created, the coverage verified, and any assumptions made during spec intake.

## Modifying existing policies

Read the current policy files before editing, change only the files the request touches, and update the tests covering any rule whose behaviour changed. Preserve existing regression scenarios as well as their names; extend the coverage plan for new behavior and affected consumers of shared definitions. Then run Phase 3 in full — both passes and the coverage audit, over the whole tree.

## References

- [references/POLICIES.md](references/POLICIES.md) — Policy types and design patterns
- [references/CEL.md](references/CEL.md) — CEL objects, function catalogue, condition nesting, strict evaluation, pitfalls, error fix table
- [references/TEST-SUITES.md](references/TEST-SUITES.md) — `*_test.yaml` schema and fixture files
- [references/TESTING.md](references/TESTING.md) — `cerbosctl repl` usage and debugging recipes
