# Mapping OPA/Rego onto Cerbos

| Rego | Cerbos |
|---|---|
| A package per resource or service | A [resource policy](https://docs.cerbos.dev/cerbos/latest/policies/resource_policies?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-authz-migration_pdp-policies-resource-policies) per resource kind |
| `default allow = false` | Deny-by-default, already the engine's behaviour — nothing to write |
| Multiple definitions of `allow`, implicitly OR'd | Multiple rules for the same action; any matching allow grants |
| A rule body's conjunction of expressions | A `condition` with an `all` block |
| `input.user`, `input.action`, `input.resource` | `request.principal`, the rule's `actions`, `request.resource` |
| A role test inside a body | `roles` on the rule, hoisted out of the condition |
| Helper rules used as named predicates | [Exported variables](https://docs.cerbos.dev/cerbos/latest/policies/variables?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-authz-migration_pdp-policies-variables), imported where needed |
| Constants in `data` | Exported constants |
| Entity data loaded into `data` | Request attributes. There is no store to load them into |
| Partial evaluation for filtering | [`PlanResources`](https://docs.cerbos.dev/cerbos/latest/recipes/filtering-resources?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-authz-migration_pdp-recipes-filtering-resources); both return a residual condition for a query layer |
| `deny[msg]` sets, as used for admission control | `EFFECT_DENY` rules; the message becomes an `output`, not part of the effect |
| An ordered `else` chain — the first branch whose body holds decides | Separate rules whose conditions exclude every earlier branch; see below |
| A body that fails because an input field is undefined | A `has()` guard reproducing the absence: `has(R.attr.x) && …` for a positive test, `!has(R.attr.x) \|\| …` under `not`. Without it the condition errors instead of failing |
| `allow if { not deny }`, with `deny` true of the whole user | `EFFECT_DENY` with `roles: ["*"]`; see below |

**`else` chains.** Earlier branches win, and Cerbos has no order, so each branch's precedence moves into its condition. In

```rego
allow := true if { "admin" in input.user.roles }
else := false if { input.user.suspended }
else := true if { input.resource.owner == input.user.id }
```

the suspended branch becomes an `EFFECT_DENY` rule on `roles: ["*"]` whose condition excludes the admin branch above it — `P.attr.suspended && !("admin" in P.roles)` — and the owner branch an ordinary allow, which that deny beats.

Pick the deny's `roles` deliberately. A deny on `roles: ["user"]` beats only the allows granted to `user`; an allow reaching the same principal through another role (`editor`) still wins. Rego's deny-style branch, or a `not deny` in `allow`, applies to the user as a whole, so reproduce it with `roles: ["*"]` and put any role test in the condition: `"user" in P.roles && P.attr.suspended`.

**Does not survive.** Comprehensions and aggregation over a data document — `count`, `sum`, set operations across entities — have no equivalent, because the entities are not there to iterate. Rules producing non-boolean values. Recursive or mutually-dependent rule graphs. Anything relying on the bundle being a queryable document rather than a request payload.

**The reframe that usually works.** Rego policies are typically written against a rich `input` and a rich `data`. In Cerbos the split is different: identity facts go on `request.principal`, object facts on `request.resource`, and there is no third place. Re-partitioning the Rego `input` into those two buckets, and deciding who supplies the facts that used to come from `data`, is most of the design work.
