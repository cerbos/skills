# Mapping Oso onto Cerbos

| Oso | Cerbos |
|---|---|
| `allow(actor, action, resource)` rules | Resource policy rules |
| A resource block's declared `permissions` | The rule's `actions` |
| A resource block's declared `roles` | Static `roles`, if assigned by the IdP; otherwise see below |
| A role held *on a specific resource* | A [derived role](https://docs.cerbos.dev/cerbos/latest/policies/derived_roles?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-authz-migration_pdp-policies-derived-roles) conditioned on an attribute that names the actor's relation to that instance |
| Rule bodies testing actor or resource fields | A CEL `condition` |
| Shorthand rules implying a role on a related resource | Relationship resolution — see the caveat below |
| Data filtering / list endpoints | `PlanResources` and a query plan adapter |

**Does not survive.** Polar is a logic language with unification and rule chaining; CEL is a single-expression evaluator. Rules that recurse through relations, or that rely on Oso resolving a relation to fetch the related object, need the relation supplied as an attribute instead. Oso deployments that register application classes so policy can call into them have no equivalent — a Cerbos condition cannot call your code.

Oso sits between the code-shaped and relationship-shaped families. Read the actual policy: one dominated by field comparisons maps easily; one dominated by `relations` and role inheritance across resources belongs in [FROM-ZANZIBAR.md](FROM-ZANZIBAR.md).
