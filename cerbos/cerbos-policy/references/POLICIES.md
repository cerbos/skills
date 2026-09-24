# Cerbos Policy Types

Every Cerbos policy is YAML with an `apiVersion: api.cerbos.dev/v1` header and exactly one top-level policy object.

## Required YAML Language-Server Header

Every policy file MUST begin with the Cerbos policy schema comment so LSP-aware editors provide validation and autocomplete:

```yaml
# yaml-language-server: $schema=https://api.cerbos.dev/latest/cerbos/policy/v1/Policy.schema.json
```

This applies to ALL policy files: resource policies, derived roles, exported variables, role policies, and principal policies. Test suites and fixtures use different schemas — see [TEST-SUITES.md](TEST-SUITES.md).

## Resource Policy (most common)

```yaml
# yaml-language-server: $schema=https://api.cerbos.dev/latest/cerbos/policy/v1/Policy.schema.json
apiVersion: api.cerbos.dev/v1
resourcePolicy:
  version: "default"
  resource: "document"
  schemas:
    principalSchema:
      ref: "cerbos:///principal.json"
    resourceSchema:
      ref: "cerbos:///resources/document.json"
  importDerivedRoles:
    - document_roles
  rules:
    - actions: ["view"]
      effect: EFFECT_ALLOW
      derivedRoles: ["owner"]
```

Always include the `schemas` field:

- `principalSchema.ref`: `cerbos:///principal.json`
- `resourceSchema.ref`: `cerbos:///resources/{resource_name}.json` (must match the resource name)

These JSON schemas validate `P.attr` and `R.attr`. Put attribute properties at the schema root. For example, `P.attr: {tenant: "acme"}` is validated by `{"type": "object", "properties": {"tenant": {"type": "string"}}, "required": ["tenant"]}`. The request envelope fields (`id`, `roles`, `kind`, `attr`) belong to the API request, outside the attribute schema. See [attribute schemas](https://docs.cerbos.dev/cerbos/latest/policies/schemas.html).

### Schema enforcement

Schemas use JSON Schema draft 2020-12. Enforcement is PDP configuration (`schema.enforcement: warn | reject`), not policy content. In `reject` mode an invalid principal or resource denies **every** action in the check and the response carries `validationErrors`. `cerbos compile` runs policy tests in reject mode, so a fixture with invalid attributes gets DENY even where a rule grants.

- Set `"additionalProperties": false` when the requirements forbid undeclared attributes; JSON Schema allows them by default.
- Use `"type": "integer"` for whole numbers; `number` accepts `2.5`.
- `resourceSchema.ignoreWhen.actions` skips resource validation, typically for `create`, where the new record's attributes are incomplete. It applies only when **every** action in the check is listed: a check for `create` alone on an incomplete resource can be allowed, but `create` plus `view` on the same resource is validated and denied. Principal attributes are always validated unless `principalSchema` has its own `ignoreWhen`.
- In a scope chain, every policy for the resource must declare the same schemas.

## Rule Outputs

A rule's `output` block returns values in CheckResources responses, such as audit events or denial reasons. It is supported on resource, principal and role policy rules. See [outputs](https://docs.cerbos.dev/cerbos/latest/policies/outputs.html).

```yaml
    - name: approve-within-limit
      actions: [approve]
      roles: [manager]
      effect: EFFECT_ALLOW
      condition:
        match:
          expr: R.attr.amount <= P.attr.approval_limit
      output:
        when:
          # The rule matched the role and action, and its condition was true.
          ruleActivated: '{"event": "payout_approved", "payout": R.id, "approver": P.id}'
          # The rule matched the role and action, but its condition was false.
          conditionNotMet: '{"reason": "over_limit", "amount": R.attr.amount, "limit": P.attr.approval_limit}'
```

- Each output is reported per action as `{src, action, val}`, where `src` is `resource.<kind>.v<version>#<rule name>`. Give every rule with an output a stable `name`, because consumers and tests match on `src`.
- To explain why a rule did not grant, put the explanation in that rule's `conditionNotMet`. Do not add a separate DENY rule: it changes the policy's decision logic and emits a different `src`. A rule for another role or action emits nothing.
- Outputs work on DENY rules too; `ruleActivated` fires when the denial applies.
- Overlapping rules can each emit, so a response may contain an ALLOW rule's `ruleActivated` output alongside the DENY that decided the action. Consumers must read the effect, not infer a decision from an output. Whether rules listed after the deciding DENY rule still emit depends on rule order, so do not rely on it.
- An output expression that fails at runtime yields an `error` entry instead of `val`; guard optional attributes with `has()`.
- Output expressions accept any CEL value: strings, numbers, maps, lists, and conditionals such as `R.attr.amount > 10000 ? "high" : "normal"`.

Test-suite `outputs` assertions (see [TEST-SUITES.md](TEST-SUITES.md#output-assertions)) are subset checks: listed outputs must match, and unlisted outputs are ignored. Assert every output a requirement specifies. Cover each branch: activation, the unmet condition, and both sides of any boundary inside the expression.

## Derived Roles

```yaml
# yaml-language-server: $schema=https://api.cerbos.dev/latest/cerbos/policy/v1/Policy.schema.json
apiVersion: api.cerbos.dev/v1
derivedRoles:
  name: "document_roles"
  definitions:
    - name: owner
      parentRoles: ["user"]
      condition:
        match:
          expr: R.attr.owner == P.id
```

Import the definition set with `resourcePolicy.importDerivedRoles`, then select a definition with the rule's `derivedRoles` field, as in the resource policy above. The rule's `roles` field matches caller-supplied base roles. Keep those base roles in principal fixtures; Cerbos computes derived roles from `parentRoles` and the condition. See [derived roles](https://docs.cerbos.dev/cerbos/latest/policies/derived_roles.html).

## Exported Variables

```yaml
# yaml-language-server: $schema=https://api.cerbos.dev/latest/cerbos/policy/v1/Policy.schema.json
apiVersion: api.cerbos.dev/v1
exportVariables:
  name: "common_vars"
  definitions:
    is_owner: R.attr.owner == P.id
```

### Variable dependency design

Keep a single-use condition inline. Use `variables.local` for expressions reused within one policy. Export a condition only when it is actually reused across policies, and group exports by a focused business concern and compatible attribute requirements rather than collecting every helper in `common_vars.yaml`.

`variables.import` names an exported **set**, not an individual variable; seeing any `V.*` reference does not justify every import. For each policy:

1. Start from its conditions and outputs, including those of derived roles it uses. Resolve variable references (`V.*` or `variables.*`) to local or exported definitions in the appropriate policy context.
2. Follow references inside those definitions transitively. Retain each required definition and import; remove imports with no reachable consumer and unused local definitions.
3. Inspect the complete contents of every retained exported set. If a policy needs one helper from a broad set, split the set by concern and update affected consumers. Keep shared definitions needed by other policies.
4. Check that the resource and principal attributes needed by those expressions exist in the consuming policy's input contract. Import relationship-specific helpers only for resources to which the confirmed relationship rule applies.

Imported sets are not free abstractions: concise source files do not guarantee a small compiled bundle. Keep dependencies minimal even if compilation succeeds. See the [Cerbos variable documentation](https://docs.cerbos.dev/cerbos/latest/policies/variables.html) for import and local-variable syntax.

## Role Policy (IdP role-centric ABAC)

Role policies define permissions from the perspective of an IdP role. Unlike resource/principal policies, they use an allowlist model — any resource-action pair not explicitly listed is denied.

```yaml
# yaml-language-server: $schema=https://api.cerbos.dev/latest/cerbos/policy/v1/Policy.schema.json
apiVersion: api.cerbos.dev/v1
rolePolicy:
  role: "acme_admin"
  scope: "acme"           # optional: matched against the resource's scope
  parentRoles:            # optional: inherit and narrow permissions
    - "admin"
  rules:
    - resource: "document"
      allowActions:
        - "view"
        - "edit"
        - "delete"
    - resource: "report"
      allowActions:
        - "view"
        - "view:*"        # wildcard
      condition:
        match:
          expr: R.attr.department == P.attr.department
```

Key characteristics:

- **Allowlist model**: no `EFFECT_ALLOW`/`EFFECT_DENY` — `allowActions` is the exhaustive permitted list
- **Implicit deny**: any action not in `allowActions` is denied
- **Parent inheritance**: child roles can only NARROW parent permissions (strict subset)
- **Wildcards**: both `resource` and `allowActions` support wildcards (`view:*`)
- **Conditions**: optional CEL expressions per rule entry
- **`allowActions` must be non-empty**: `allowActions: []` is a validation error
- **Never grants beyond resource policies**: an allowed action also needs a grant from the resource-policy chain for the role, or for its `parentRoles`. A custom role with no `parentRoles` that map to resource-policy roles gets nothing. A resource policy is always required, but no scoped resource policy is needed; the chain falls through to the base policy.
- **Parents resolve recursively**: a parent role with its own role policy in the same scope applies that policy's restrictions too. If Acme narrows `editor`, a custom role based on `editor` inherits the narrowing.
- **Narrowing an IdP role**: a role policy named after an existing role (`role: editor`, no `parentRoles`) restricts that role within its scope only; outside the scope the role keeps its resource-policy permissions.
- **Failed conditions deny**: a matching rule whose condition is false denies that action, even if another rule in the policy lists it unconditionally. Put each action in one rule.
- **Strict subset is checked at evaluation, not compile time**: listing an action the parent lacks compiles but is denied.
- **Scope**: a scoped role policy applies to requests for resources with that scope; the principal's scope does not select it. An unscoped role policy applies only to unscoped requests.

## Scoped Resource Policies (policy hierarchy)

A resource policy with `scope: "acme.eu"` applies to requests whose resource (or principal, for principal policies) has that scope. Cerbos evaluates the chain from most to least specific: `acme.eu`, `acme`, then the unscoped base policy. Every ancestor in the chain must exist, including the base policy, or compilation fails. Without `lenientScopeSearch` (engine config), a request for a scope with no policy of its own is denied. Imports (derived roles, variables) are not inherited: each scoped policy imports what its own rules use. See [scoped policies](https://docs.cerbos.dev/cerbos/latest/policies/scoped_policies.html).

`scopePermissions` decides what a scoped policy may do relative to its parents, and must match for all policies in the same scope:

| Setting | Rule matches, condition true | Rule matches, condition false | No rule matches | Use when |
|---|---|---|---|---|
| `SCOPE_PERMISSIONS_OVERRIDE_PARENT` (default) | Its effect is final | Continue to parent | Continue to parent | The scope may grant or revoke independently of its parents |
| `SCOPE_PERMISSIONS_REQUIRE_PARENTAL_CONSENT_FOR_ALLOWS` | ALLOW still needs a parent ALLOW; DENY is final | Implicit DENY | Continue to parent | The scope may only narrow what its parents allow |

Map requirements to the setting, not only to today's decisions. "May only restrict", "cannot grant beyond the parent", or "narrowing only" requires `REQUIRE_PARENTAL_CONSENT_FOR_ALLOWS` on that scope and on each descendant that must keep the guarantee. An override-mode policy that restates parent grants and adds DENY rules can produce the same decisions today, but any future ALLOW rule in it can exceed the parent.

In consent mode, express a restriction as a conditional ALLOW for the affected roles and actions. When the condition fails, the result is an implicit DENY. Leave unaffected permissions out of the policy so they fall through to the parent; do not restate the parent's grants. Roles are evaluated separately and the results combined, so a principal with an unrestricted second role keeps that role's access. An ALLOW rule for `roles: ["*"]` and `actions: ["*"]` gated by a condition adds a requirement across the whole scope, such as data residency, without granting anything the parent denies.

```yaml
resourcePolicy:
  resource: report
  version: default
  scope: acme
  scopePermissions: SCOPE_PERMISSIONS_REQUIRE_PARENTAL_CONSENT_FOR_ALLOWS
  rules:
    # Acme editors may change drafts only; other base permissions pass through.
    - name: editors-edit-drafts
      actions: [edit]
      roles: [editor]
      effect: EFFECT_ALLOW
      condition:
        match:
          expr: R.attr.status == "draft"
```

Place scoped policies in folders that mirror the scope (`resource_policies/acme/eu/report.yaml`). Resource fixtures carry `scope`; see [TEST-SUITES.md](TEST-SUITES.md#scoped-fixtures).

## Scoped Role Policies (`parentRoles` + `scope`)

Scoped role policies let tenants create custom roles that narrow base role permissions.

**Inheritance behavior:**

- Resources LISTED in the child policy are narrowed to the child's `allowActions` (must be a strict subset of the parent)
- Resources NOT LISTED in the child policy are DENIED entirely — the allowlist is exhaustive
- To grant any access to a resource, it must be explicitly listed in the child policy's rules

**Derived roles do NOT need custom role names:**

- If base derived roles list `parentRoles: ["admin", "operator", "developer", "viewer"]`, custom roles with `parentRoles: ["operator"]` automatically resolve through the parent chain
- Never add custom role names to derived role `parentRoles` lists

**Scope goes on the RESOURCE fixture, not the principal:**

- Role policy declares `scope: "acme"`
- Test resource fixtures must have `scope: "acme"` for the scoped role policy to evaluate
- Test principal fixtures should NOT have a `scope` field — just the custom role name in `roles`

```yaml
# role_policies/acme/release_manager.yaml
apiVersion: api.cerbos.dev/v1
rolePolicy:
  role: "release_manager"
  scope: "acme"
  parentRoles:
    - "operator"
  rules:
    - resource: "flow"
      allowActions:
        - "read"
        - "deploy"
    - resource: "secret"
      allowActions:
        - "read"
    # connector NOT listed → denied (allowlist is exhaustive)
```

```yaml
# testdata/principals.yaml — no scope on principal
acme_release_manager:
  id: "user_acme_rm"
  roles:
    - "release_manager"
  attr:
    org_id: "org1"
```

```yaml
# testdata/resources.yaml — scope on resource
acme_staging_flow:
  kind: "flow"
  id: "flow1"
  scope: "acme"
  attr:
    org_id: "org1"
    project_id: "proj1"
    environment: "staging"
```

**Conditions on scoped role rules:**

Individual rules within a scoped role policy can have CEL conditions. Use separate rule entries for the same resource to apply conditions to specific actions only.

```yaml
rules:
  - resource: "flow"
    allowActions:
      - "read"
  - resource: "flow"
    allowActions:
      - "create"
      - "update"
    condition:
      match:
        expr: R.attr.environment == "staging"
```

**File organization:** group scoped role policies into subfolders per tenant: `role_policies/acme/`, `role_policies/globex/`.

## Policy Design Patterns

Choose the pattern that best fits the requirements.

### Action-Led (recommended default)

Focus on actions, list which roles can perform each. Best when:

- Roles have hierarchical permissions
- You need visibility into "high-risk" actions
- Many roles, fewer distinct actions

### Role-Led

Center on roles, specify their allowed actions. Best when:

- Roles are distinct with minimal overlap
- Fewer roles, many actions
- Clear role separation

### Attribute-Led (ABAC)

Use dynamic attributes instead of static roles. Best for:

- Multi-tenant systems
- Context-aware access (time, location, status)
- Flexible rules without policy changes

### Role Policy (IdP role-centric)

Use role policies when permissions should be defined from the IdP role's perspective. Best for:

- Integrating with IdP-managed roles
- Simple allowlist semantics (list what's allowed, everything else denied)
- Hierarchical roles with inheritance and narrowing
- When you want to avoid explicit DENY rules
