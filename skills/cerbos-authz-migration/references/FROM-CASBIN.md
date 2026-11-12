# Mapping Casbin onto Cerbos

| Casbin | Cerbos |
|---|---|
| `[request_definition]` subject, object, action | `request.principal`, `request.resource`, the requested action |
| A `p` policy line — subject, object, action | One rule in the resource policy for that object |
| A `g` grouping line assigning a user to a role | Role assignment. It leaves the policy entirely and is sent as `principal.roles` from the IdP or the app |
| A `g` line nesting one role inside another | Flatten into the roles sent at request time, or express as [role policy](https://docs.cerbos.dev/cerbos/latest/policies/role_policies?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-authz-migration_pdp-policies-role-policies) `parentRoles` when the child role genuinely narrows the parent |
| `[matchers]` expression | A CEL `condition`, once the role and object matching is hoisted into `roles` and the resource `kind` |
| Path or pattern matching on the object | The resource `kind` plus action wildcards, or a `matches()` condition on an attribute. Cerbos action wildcards honour the `:` delimiter — `view:*` matches `view:public` but not `view` |
| A domain or tenant argument in the model | A tenant attribute in a condition, or a [scope](https://docs.cerbos.dev/cerbos/latest/policies/scoped_policies?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-authz-migration_pdp-policies-scoped-policies) if tenants have genuinely different rules |
| An explicit deny effect in a policy line | `EFFECT_DENY` on the rule |

**Does not survive.** The `[policy_effect]` line. Casbin lets the effect expression itself be configured — allow-override, deny-override, priority, and custom combinations — and Cerbos's resolution is fixed. A deny-override model maps cleanly and needs no thought. A priority model does not map at all: work out what the priorities were compensating for and write that intent directly.

**Watch for.** Casbin policy lines usually live in a CSV or a database table that the application writes to at runtime. If your application adds `p` lines in response to user actions, those are data, not policy — model them as attributes, or generate per-tenant policy into a store through the Hub SDK. Moving a runtime-writable table into files makes every user action a deploy.
