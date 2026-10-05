# Test Suite Files (`*_test.yaml`)

Declarative test files that `cerbos compile` runs as part of validation. For interactive debugging of a single condition, see [TESTING.md](TESTING.md).

## File Structure

Test files MUST end in `_test.yaml`. The schema is strict — only documented fields are allowed (`additionalProperties: false`).

Every test file MUST begin with the test suite language-server header:

```yaml
# yaml-language-server: $schema=https://api.cerbos.dev/latest/cerbos/policy/v1/TestSuite.schema.json
```

```yaml
# yaml-language-server: $schema=https://api.cerbos.dev/latest/cerbos/policy/v1/TestSuite.schema.json
name: "DocumentPolicyTest"
description: "Tests for document resource policy"  # optional

principals:
  owner_user:
    id: "user1"
    roles:
      - "user"
    attr:
      department: "engineering"
  other_user:
    id: "user2"
    roles:
      - "user"
    attr:
      department: "sales"

resources:
  owned_doc:
    kind: "document"
    id: "doc1"
    attr:
      owner: "user1"
      public: false

# Optional: auxData fixtures — only needed if policies use request.auxData (e.g., JWT claims).
# Skip this section entirely if your policies don't reference auxiliary data.
# See "AuxData Fixtures" below for the jwt / jwts forms.

tests:
  - name: "Owner can edit their document"
    input:
      principals:
        - owner_user
      resources:
        - owned_doc
      actions:
        - edit
        - view
    expected:
      - principal: owner_user
        resource: owned_doc
        actions:
          edit: EFFECT_ALLOW
          view: EFFECT_ALLOW

  - name: "Non-owner cannot edit"
    input:
      principals:
        - other_user
      resources:
        - owned_doc
      actions:
        - edit
    expected:
      - principal: other_user
        resource: owned_doc
        actions:
          edit: EFFECT_DENY
```

## Strict Schema — Allowed Fields Only

Root-level fields (ONLY these):

- `name` (required), `description`, `options`, `skip`, `skipReason`
- `principals`, `principalGroups`, `resources`, `resourceGroups`, `auxData`
- `tests` (required)

Each test case in `tests` (ONLY these):

- `name` (required): string
- `input` (required): object
- `expected` (required): array
- `description`, `options`, `skip`, `skipReason`: optional

`input` object (ONLY these):

- `actions` (required): array of strings
- `principals`: array of fixture key strings
- `resources`: array of fixture key strings
- `principalGroups`, `resourceGroups`: arrays (optional)
- `auxData`: STRING reference to fixture key (NOT an object)

`expected` array items (ONLY these):

- `actions` (required): object mapping action name to `"EFFECT_ALLOW"` or `"EFFECT_DENY"`
- `principal`: string (fixture key)
- `resource`: string (fixture key)
- `principals`, `resources`, `principalGroups`, `resourceGroups`: arrays (alternative to singular)
- `outputs`: array (optional, for output assertions)

Every list above is exhaustive: the schema sets `additionalProperties: false`, so any field outside them fails validation. Assertions describe the expected *effect* of a request — the policy's own vocabulary (conditions, roles, rules) has no place in a test file.

## `options` Block

Valid at suite root and per test case; the test-case block overrides the suite block. Allowed keys (ONLY these):

| Key | Type | Purpose |
|---|---|---|
| `now` | RFC3339 timestamp string | Pins what `now()` returns. Use this for any time-dependent rule — never rely on the wall clock |
| `strictEvaluation` | boolean | Treat runtime CEL errors as terminal, denying the affected action (v0.55+) |
| `defaultPolicyVersion` | string | Policy version for fixtures that do not set one |
| `defaultScope` | string | Scope for fixtures that do not set one |
| `lenientScopeSearch` | boolean | Fall back to ancestor scopes when an exact scope has no policy |
| `globals` | object | Values bound to `globals.*` in expressions |

```yaml
options:
  now: "2026-01-15T10:00:00Z"
  strictEvaluation: true
  globals:
    tenant_tier: "enterprise"
```

Pinning `now` is the correct way to test time-based conditions — see [TESTING.md](TESTING.md).

## AuxData Fixtures

Two mutually exclusive forms. Single token uses `jwt` with claims inline; multiple named tokens use `jwts` with a mandatory `claims` level (v0.55+).

```yaml
auxData:
  # Single JWT → request.auxData.jwt.dept
  valid_jwt:
    jwt:
      iss: my.domain
      aud: ["x", "y"]
      dept: engineering

  # Named JWTs → request.auxData.jwts.primary.claims.dept
  multi_token:
    jwts:
      primary:
        claims:
          iss: my.domain
          dept: engineering
      delegated:
        claims:
          act: service-account
```

Reference a fixture from a test with `input.auxData: valid_jwt` — a STRING key, never an inline object.

## Output Assertions

When a rule has an `output` block, assert on it under `expected[].outputs`:

```yaml
expected:
  - principal: owner_user
    resource: owned_doc
    actions:
      view: EFFECT_ALLOW
    outputs:
      - action: view
        expected:
          - src: resource.document.vdefault#view-rule
            val:
              key1: value1
```

Each entry under `expected` accepts `src`, `val`, `error`, and `action`. Since v0.54, an output expression that fails at runtime reports its `error` in the response and the test failure shows the actual evaluation error — so a mismatch tells you whether the expression errored or merely produced the wrong value. An `output` block with an empty expression is a compile error.

## Shared Fixtures

Fixtures come from two places, and a suite can use either or both:

- **Inline**: the suite's own `principals`, `resources` and `auxData` maps. A self-contained suite defines everything inline and needs no `testdata/` folder.
- **Shared files**: `testdata/principals.yaml`, `testdata/resources.yaml` and `testdata/auxdata.yaml` (`.yml` or `.json` also work) in the directory that contains the test file. They are shared by every `*_test.yaml` in that directory. A suite that uses only shared fixtures omits the inline `principals` and `resources` keys entirely.

There is only one file of each kind per `testdata/` folder, so combine everything the directory's suites need into it. When a key exists in both places, the suite's inline definition wins for that suite. When the requirements ask for one style, follow it exactly: do not create a `testdata/` folder beside a suite meant to be self-contained.

A principal/resource pair listed in `input` but absent from `expected` is expected to be DENY for every action, and the omitted actions of a listed pair default to DENY too. Write DENY expectations explicitly anyway, so the intent is readable.

### Scoped fixtures

Put `scope` on the resource fixture (`scope: emea.de`), or set `options.defaultScope` for the suite or test. A test's `options` replace the suite's `options` instead of merging, so repeat any other suite option you still need.

## Standalone Fixture File Format

Standalone fixture files MUST have a top-level key AND the matching language-server header:

- Principal fixtures: `$schema=https://api.cerbos.dev/latest/cerbos/policy/v1/TestFixture/Principals.schema.json`
- Resource fixtures: `$schema=https://api.cerbos.dev/latest/cerbos/policy/v1/TestFixture/Resources.schema.json`
- AuxData fixtures: `$schema=https://api.cerbos.dev/latest/cerbos/policy/v1/TestFixture/AuxData.schema.json`

```yaml
# testdata/principals.yaml
# yaml-language-server: $schema=https://api.cerbos.dev/latest/cerbos/policy/v1/TestFixture/Principals.schema.json
principals:
  owner_user:
    id: "user1"
    roles:
      - "user"
    attr:
      department: "engineering"
```

```yaml
# testdata/resources.yaml
# yaml-language-server: $schema=https://api.cerbos.dev/latest/cerbos/policy/v1/TestFixture/Resources.schema.json
resources:
  owned_doc:
    kind: "document"
    id: "doc1"
    attr:
      owner: "user1"
      public: false
```

## Coverage Plan

Before writing tests, save the plan outside the policy directory as `coverage-plan.json`. It is the input to the [coverage audit](#coverage-audit), so write it in that script's JSON format.

Start with `paths`: one entry per **grant path**, meaning a rule, role or derived role that allows actions on one resource kind. List every prerequisite in that path's condition, including the parent role. A prerequisite shared by several paths, such as a tenant check in two derived roles, appears in each path, and each consuming resource kind gets its own paths.

Then write one row per planned assertion, keyed by the fixture keys the tests will use. Each denial that isolates a prerequisite names its `path` and `prerequisite`; the audit fails if any listed prerequisite of any path lacks such a row.

```json
{
  "paths": [
    {"id": "document-owner", "kind": "document", "requires": ["parent-role", "tenant", "ownership"]},
    {"id": "document-reviewer", "kind": "document", "requires": ["parent-role", "tenant", "department"]}
  ],
  "rows": [
    {"id": "document-owner-edit", "principal": "alice_employee", "resource": "document_owned_by_alice",
     "action": "edit", "effect": "EFFECT_ALLOW"},
    {"id": "document-missing-parent-role-edit", "principal": "alice_reviewer_only", "resource": "document_owned_by_alice",
     "action": "edit", "effect": "EFFECT_DENY", "control": "document-owner-edit", "change": "principal.roles",
     "path": "document-owner", "prerequisite": "parent-role"}
  ]
}
```

`principal` and `resource` are fixture keys. Here `alice_reviewer_only` keeps the ID `alice` with different roles. `control` names the row with the opposite effect, and `change` the one field that differs from it.

When a requirement names a qualifying condition, such as "even for archived projects" or "a quantity equal to the cap", record it in the row's `facts` (for example `{"resource.attr.archived": true}` or `{"resource.scope": "emea"}`; use `null` for an absent attribute). The audit then checks the resolved fixture instead of trusting its name.

Field paths for `change` and `facts` are `principal.id`, `principal.roles`, `principal.attr.<name>`, `principal.scope`, `principal.policyVersion`, `resource.kind`, `resource.attr.<name>`, `resource.scope` and `resource.policyVersion`; the audit rejects any other name. An optional `suite` (test file relative to the policy directory) or `test` (test case name) narrows the match.

Plan rows separately for each resource policy, including those that import the same derived roles or variables. Exercise these branches where the specification uses them:

- An allowed request for each grant and denial for unrelated roles/actions.
- Each independent authorization prerequisite: base role, tenant, ownership, department, status, or other attribute condition.
- Exact threshold values and values on either side; missing optional attributes and their explicit values; overrides that change a decision from the default.
- Overlapping roles and alternative grant paths, using the confirmed combination semantics.

**Isolate the denial.** Give each denial of an authorization prerequisite a `control`: an active ALLOW row for the same resource kind and action. Copy that allowed request and change only the prerequisite under test. One allowed case can serve as the control for several negatives. For example, if editing requires a base role, ownership and a matching tenant:

| Case | Base role | Owner equals principal ID | Tenant matches | Effect | `change` |
| --- | --- | --- | --- | --- | --- |
| Allowed (control) | Present | Yes | Yes | ALLOW | — |
| Missing parent role | Absent; only unrelated roles | Yes | Yes | DENY | `principal.roles` |
| Different owner | Present | No | Yes | DENY | `resource.attr.owner` |
| Different tenant | Present | Yes | No | DENY | `resource.attr.tenant` or `principal.attr.tenant` |

**Fixture keys are unique; principal IDs need not be.** The audit ignores a principal ID difference between a row and its control unless a policy reads `P.id` (or a principal policy exists), but keeping the ID is still the simplest way to leave only the tested field different. Several principal fixtures may share one `id`. A missing-parent-role variant of owner `alice` is a new key such as `alice_reviewer_only` with `id: alice` and different roles, so the resource's `owner` still matches. Giving the variant a new ID also breaks ownership, so the test no longer shows which prerequisite caused the denial. Likewise, a limit-override principal keeps the default principal's ID and differs only in the override attribute.

Keep other grant paths inactive when isolating a denial, then test role combinations separately. A tenant test that also changes the owner cannot establish which boundary caused the denial. The same principle applies to a blocked resource, suspended principal or amount limit: satisfy the other prerequisites so the intended condition determines the result.

**Defaults and overrides must flip a decision.** Pair an optional attribute or override with a control whose effect is opposite. For a principal limit that replaces a default of 250, test an amount between the two limits: 200 with limit 150 is DENY while the default principal gets ALLOW, or 400 with limit 500 is ALLOW while the default principal gets DENY. An amount within both limits proves nothing about the override. Do this for every resource with its own default.

For derived roles, test matching attributes with unrelated base roles, the required parent role with a failing relationship, and a derived-role name supplied as a principal role. Include a valid positive case for each role before relying on its negative cases.

**Schema rejections need a request the policy would allow.** If the request says principals or resources have no attributes, keep every fixture's `attr` empty and do not add schema-rejection fixtures for them. Tests run with schema enforcement in reject mode, so a schema denial proves something only when the same request with valid attributes is ALLOW. Use an ALLOW row as the control, and break one attribute in its fixture: remove a required attribute, give one an invalid value, add an undeclared attribute, or make one principal attribute invalid. Use one violation per fixture, and break an attribute that the granting rule does not read. Pair an invalid principal with a complete, valid resource, even for `create`, so the principal is the only violation. If the rule checks `owner` or `status`, a missing or invalid value there is denied by the policy anyway, so it cannot show the schema at work; break `amount` on a request that does not compare `amount` instead. When a fixture's name claims a property (such as "archived"), check that its attributes actually have it. For `ignoreWhen`, add a check for the ignored action alone on an incomplete resource, expecting ALLOW. See [POLICIES.md](POLICIES.md#schema-enforcement).

**Scope-specific rules need a request that qualifies.** To show that a grant from one scope does not apply elsewhere, reuse the request that is allowed in the granting scope and change only the resource's `scope`. To show that a restriction applies only in its scope, reuse the request it denies (for example, an analyst exporting a raw dataset) and change only the `scope`, expecting ALLOW. A request the restriction would allow anyway proves nothing. For example, an `apac` auditor reading a dataset marked shareable becomes the same request in the base scope or `emea`, expecting DENY. Test each restriction in the scope that adds it and in each descendant that inherits it. Test inherited base permissions in every scope, and test a principal with several roles where one role alone would be denied.

In the plan, a scope boundary is a pair of rows whose fixtures differ only in `scope`. If `emea` lets analysts export only anonymised datasets, pair the `emea` DENY for a raw dataset with the same request unscoped (in a hierarchy with only the `emea` branch; see below when there are others):

```json
{"id": "emea-analyst-raw-export", "principal": "analyst", "resource": "emea_raw_dataset", "action": "export",
 "effect": "EFFECT_DENY", "facts": {"resource.scope": "emea", "resource.attr.anonymised": false}},
{"id": "base-analyst-raw-export", "principal": "analyst", "resource": "base_raw_dataset", "action": "export",
 "effect": "EFFECT_ALLOW", "control": "emea-analyst-raw-export", "change": "resource.scope",
 "facts": {"resource.scope": null}}
```

The audit requires such a pair for every role named by a scoped resource-policy rule (any role for `*`) and every scoped role policy, in the scope that adds the rule and in each descendant scope with its own policy, because the rule governs those too. When the hierarchy has other top-level branches, the other side of the pair must be a scope in one of them rather than the unscoped base, so the same row shows the rule does not leak across branches: with `emea` and `apac` policies, pair the `emea` export DENY with the same request in `apac`. One row can meet several requirements, such as an `apac` row for a `*` rule. A scoped rule that only restates its parent cannot produce one; list it under the plan's top-level `scopeExemptions` as `{"scope": "emea", "role": "analyst", "reason": "..."}`, or remove the redundant rule.

For explicit DENY rules, start with a request another rule would allow and activate the denying condition. This proves the denial overrides a real grant. Run the strict pass to expose condition errors that could otherwise make the deny silently no-op ([CEL.md](CEL.md#strict-evaluation-v055)). Pin `options.now` for time-dependent cases.

## Coverage Audit

Run the bundled audit after writing or fixing the bundle. It needs only the Python 3 standard library, and reads fixtures with PyYAML when it is installed. Save both compile reports outside the policy directory first:

```bash
cerbos compile --output=json policies > normal.json
cerbos compile --output=json --strict-evaluation policies > strict.json
python3 <skill-dir>/scripts/coverage_audit.py --policies policies \
  --plan coverage-plan.json --report normal.json --report strict.json
```

With the native binary, `--run` in place of the `--report` arguments runs both compile passes, saves the two reports next to the plan, and prints compile errors, failing tests and audit failures before the passes. With Docker, mount the working directory and redirect the container's stdout the same way. Without `python3`, run the audit in Docker from the directory that holds `policies/`, the plan and both reports:

```bash
docker run --rm -v "$(pwd):/work" -v "<skill-dir>/scripts:/audit:ro" -w /work python:3.13-slim \
  python /audit/coverage_audit.py --policies policies \
  --plan coverage-plan.json --report normal.json --report strict.json
```

For each row the audit:

1. Finds an executed, passing assertion with the planned principal, resource, action and effect in every report. Missing or skipped cases fail; aggregate pass counts are insufficient.
2. Resolves the fixture keys through the suite's `testdata/` files and inline suite fixtures to actual IDs, roles and attributes. Fixture names are only labels.
3. For a row with a `control`, requires the control to have the opposite effect and the same action, and the resolved requests to differ at exactly the `change` field (ignoring `resource.id`). It prints that field's before/after values.
4. For every prerequisite of every declared path, requires a passing row with that `path`, `prerequisite` and a control on a resource of the path's kind.
5. When a bundle has role-specific scoped rules or scoped role policies, requires a passing ALLOW row for a principal with two or more roles whose control has a subset of those roles (`change: principal.roles`) and is DENY, showing the roles combine, unless the plan sets `roleUnionExemption: {"reason": "..."}`.
6. For every role named by a scoped resource-policy rule or scoped role policy, in that scope and each descendant scope with its own policy, requires a passing row with `change: resource.scope` for a principal with that role, with that scope on one side and a scope from another top-level branch (or the unscoped base when there is none) on the other, unless `scopeExemptions` lists it.

It exits 1 when coverage fails and 2 when it cannot read an input, such as fixture YAML with anchors, aliases or tags on a machine without PyYAML. When it exits 2, or neither `python3` nor Docker is available, perform these checks yourself from the plan, both reports and the fixture files, record each row's result and each control pair's before/after values next to the plan, and state in your final report that the executable audit did not run.

Every requirement needs rows in each consuming resource; a test of one consumer does not establish coverage of another consumer of a shared variable or derived role. Do not weaken the plan to make the audit pass: when a row fails, fix the fixture or test. Save the plan and audit output together. Rerun both validation modes and the audit until all three exit 0. Compilation shows the submitted assertions pass; the audit shows they cover the requested behavior.

## Common Test Failures

| Symptom | Cause | Fix |
|---|---|---|
| `additional property not allowed` | Extra field in test or fixture | Remove the field — schema is strict |
| Expected ALLOW, got DENY | Derived role not matching, or fixture missing an attribute | Reproduce in REPL ([TESTING.md](TESTING.md)) |
| Expected ALLOW, got DENY for every action on a fixture | Fixture attributes fail the policy's schema (tests enforce schemas in reject mode), or `create` shares a check with a validated action | Fix the fixture, or test `create` alone on incomplete resources |
| Compile error about a missing scope policy | A scoped policy lacks an ancestor (`emea` for `emea.de`, or the base policy) | Add every ancestor policy in the chain |
| Expected DENY, got ALLOW | Duplicate unconditional rule, wildcard action grant, or a DENY condition erroring at runtime | Search for conflicting rules; re-run with `--strict-evaluation` |
| Passes normally, fails under `--strict-evaluation` | Condition errors at runtime and silently evaluates false | Fix the expression or add the missing fixture attribute |
| Output assertion fails with an `error` value | Output expression itself errored rather than returning a wrong value | Fix the output expression, not the expected `val` |
| Test result ERRORED: time-based condition but `now` not provided | Rule reaches `now()` and the test has no `options.now` | Set `options.now` on every test that can reach the rule, including tests of other actions for that principal |
| "0 tests executed" | No `*_test.yaml` files present | Expected — not an error unless you expected tests |
