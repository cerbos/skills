# Mapping hand-rolled checks onto Cerbos

Phase 3, for authorization written directly in application code. Each pattern below gives the shape you found, the construct that carries it, and the thing that usually goes wrong.

Policy syntax and CEL belong to `cerbos-policy` ([Policies](https://docs.cerbos.dev/cerbos/latest/policies/index.md?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=skill&utm_content=cerbos-authz-migration)); the snippets here are only enough to show the shape of the target.

## The inline role check

```js
if (user.role !== 'admin') throw new Forbidden()
```

The simplest case: a rule with `roles`.

```yaml
- actions: ["delete"]
  effect: EFFECT_ALLOW
  roles: ["admin"]
```

Two things to check before writing it down.

**Singular or plural.** `user.role` (one string) and `user.roles` (a list) migrate identically — Cerbos always takes a list — but they behave differently under [conflict resolution](https://docs.cerbos.dev/cerbos/latest/policies/evaluation.md?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=skill&utm_content=cerbos-authz-migration). If a principal holds several roles and any one of them produces an allow for the action, the result is allow. Code written as `if (user.role === 'viewer') return readOnlyView()` assumed exactly one role and will grant more than it used to once a user carries both `viewer` and `editor`. Flag every rule whose source read a singular role field.

**Negative or positive.** `!== 'admin'` throwing is a deny written as the absence of an allow. Cerbos is deny-by-default, so the positive rule above reproduces it — unless the code path also *grants* something to non-admins further down, in which case you have two rules and the order they appeared in matters for the Purpose column, not for the policy.

## The ownership check

```py
if doc.owner_id != current_user.id:
    raise PermissionDenied
```

A [derived role](https://docs.cerbos.dev/cerbos/latest/policies/derived_roles.md?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=skill&utm_content=cerbos-authz-migration), not a condition repeated on every rule.

```yaml
definitions:
  - name: owner
    parentRoles: ["*"]
    condition:
      match:
        expr: R.attr.owner == P.id
```

`parentRoles: ["*"]` matches any static role, which is what an ownership check written with no role test means. Use a narrower parent list only where the source code also required a role.

Derived roles must be imported into the resource policy with `importDerivedRoles` and named in a rule's `derivedRoles` list; defining one grants nothing on its own. Local variables defined in the derived roles policy are not visible to the resource policies that import it.

**Watch for:** `roles` and `derivedRoles` on the same rule are an OR, not an AND. A rule listing `roles: ["user"]` and `derivedRoles: ["owner"]` matches any user *or* any owner.

## The tenant check

```ts
if (resource.tenantId !== user.tenantId) return res.status(404).end()
```

Two constructs fit, and they answer different questions.

| Use | When |
|---|---|
| A condition or derived role over a tenant attribute | Every tenant obeys the same rules; only the data is partitioned. This is the common case |
| [Scoped policies](https://docs.cerbos.dev/cerbos/latest/policies/scoped_policies.md?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=skill&utm_content=cerbos-authz-migration) | Tenants genuinely have *different rules* — one requires a second approver, another disables sharing |

Reach for scopes only when the second is true. Scopes are a policy hierarchy with real constraints: a request carrying scope `a.b.c` needs policies at `a.b.c`, `a.b`, `a` and the base to exist unless lenient scope search is enabled, `scopePermissions` must agree within a scope, and derived roles and variables are not inherited down the chain — each policy imports them again. A per-tenant condition costs none of that.

If tenants define their own roles at runtime, neither applies: use static policies with dynamic context, passing the assignments as a principal attribute keyed by tenant, and condition on `P.attr.workspaces[R.id].role`.

## The `can()` helper

```rb
def can?(user, action, resource)
  return true if user.admin?
  case [action, resource.class.name]
  when [:edit, 'Post'] then resource.author_id == user.id
  ...
end
```

The best thing that can be found in a migration. It is already a PDP in miniature: a single function taking a subject, an action and a resource, returning a decision.

- Its **body** is the rule set. Read every branch; each is one or more Structured Intent rows.
- Its **signature** is the PEP boundary. Keep the function, replace the body with a Cerbos call, and nothing else in the codebase has to change on the first flip. This makes the shim in Phase 5 a one-file change.
- Its **callers** are the guard sites, and they are already enumerated.

Two branches to treat carefully. An early `return true if user.admin?` is a wildcard grant — write it as an explicit rule, not as an assumption. And a default branch returning `true` inverts Cerbos's posture: the helper is allow-by-default and Cerbos is deny-by-default, so every case the `case` statement never handled was permitted and will now be refused. Enumerate those cases before the flip; they are the single most common source of a broken cutover.

## The middleware or decorator guard

```ts
router.delete('/orders/:id', requireRole('manager'), deleteOrder)
```

The rule is a rule like any other. The problem is *where the check runs*.

Middleware fires before the handler loads the order, so it can only test principal facts. Any rule needing resource attributes — amount, status, owner — is enforced later, inside the handler, or not at all. After the migration the Cerbos call has to sit where the resource exists.

| Source shape | Where the Cerbos call goes |
|---|---|
| Guard tests principal facts only | Stays in middleware; send `principal` and a resource with `kind` and `id` |
| Guard tests resource facts | Moves into the handler, after the load |
| Guard is coarse, handler has extra `if`s | One Cerbos call in the handler covering all of it — that consolidation is the point of the migration |

Record the move in the inventory. Relocating a check from middleware to handler is the largest mechanical change most migrations contain, and it is easy to underestimate.

## The ORM scope or list filter

```py
Document.objects.filter(team_id__in=user.team_ids)
```

Not a `CheckResources` call. Use [`PlanResources`](https://docs.cerbos.dev/cerbos/latest/recipes/filtering-resources.md?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=skill&utm_content=cerbos-authz-migration): it returns `ALWAYS_ALLOWED`, `ALWAYS_DENIED`, or a `CONDITIONAL` filter as an AST that a [query plan adapter](https://docs.cerbos.dev/cerbos/latest/recipes/query-plan-adapters/index.md?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=skill&utm_content=cerbos-authz-migration) turns into a native query.

The rule must be written once and serve both paths — the same resource policy produces the per-instance decision for `CheckResources` and the residual filter for `PlanResources`. Conditions over resource attributes appear in the filter; conditions over principal attributes only are resolved before the plan is returned and do not.

**The real constraint.** A condition can only reach the filter if the attribute it names is a column, or something the adapter can map to one. A scope that joins across tables — *documents in projects whose owner is in my department* — has no attribute to condition on. Either denormalise the fact onto the row, or leave that part of the filter in the query and let Cerbos narrow the rest. Put it on the gap register either way, since it is the scope case that most often stalls a migration.

`cerbos-pep-integration` ([query plan adapters](https://docs.cerbos.dev/cerbos/latest/recipes/query-plan-adapters/index.md?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=skill&utm_content=cerbos-authz-migration)) owns the adapter wiring.

## The database permission table

Covered in [DISCOVERY.md](DISCOVERY.md) under stored guards, including the classification table. The rule of thumb again, because it decides the mapping: **rows that change with a deploy become policy; rows that change with a user action become attributes.**

Two conversions worth spelling out.

**`role_permissions(role, permission)`** with permission strings like `orders:approve`. Split each string into a resource kind and an action, group by kind into resource policies, and by action within them. A permission string with three segments (`orders:line_item:edit`) usually means the resource kind is coarser than the string — decide whether `line_item` is its own kind or an action suffix, because action wildcards honour the `:` delimiter and `edit:*` will match `edit:amount` but not `edit`.

**`resource_acl(resource_id, user_id, level)`** becomes an attribute on the resource, never a policy per instance. Send the relevant slice — the calling user's level, or a small map — and condition on it:

```yaml
condition:
  match:
    expr: R.attr.acl[P.id] in ["editor", "owner"]
```

Sending the whole ACL for a resource with thousands of grantees is a request-size problem, not a policy problem. Send only the calling principal's entry.

## The superuser short-circuit

```py
if request.user.is_superuser:
    return True
```

Framework-level bypasses (`is_superuser`, `admin?`, a root API key) are invisible to a grep for permissions and are real rules. Make each one explicit:

```yaml
- actions: ["*"]
  effect: EFFECT_ALLOW
  roles: ["superuser"]
```

Then confirm with the user that the bypass should survive. A migration is the moment to find out that four services each have their own root escape hatch, and one of them is a shared static token.

## The entitlement check

```js
if (!account.plan.features.includes('sso')) return res.status(402).end()
```

Subject-dependent, so it migrates. Either a condition over a plan attribute, or a derived role per tier when several rules key off the same tier:

```yaml
definitions:
  - name: pro_account
    parentRoles: ["*"]
    condition:
      match:
        expr: P.attr.plan in ["pro", "enterprise"]
```

Keep it separate from rollout flags, which do not vary by subject and stay where they are.

## Errors that carry meaning

Hand-rolled guards often say *why*:

```js
throw new Forbidden('Approval limit exceeded for your role')
```

Cerbos returns `EFFECT_ALLOW` or `EFFECT_DENY` and nothing else. To keep the message, attach an [output](https://docs.cerbos.dev/cerbos/latest/policies/outputs.md?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=skill&utm_content=cerbos-authz-migration) to the rule and have the PEP render it. The output does not change the effect, and outputs on every rule cost evaluation time — use them where the user-facing message matters, not as a debugging habit.

The `404`-instead-of-`403` pattern (hiding existence from unauthorised users) is a PEP behaviour, not a policy one. Record it in Purpose so the PEP keeps doing it after the flip.
