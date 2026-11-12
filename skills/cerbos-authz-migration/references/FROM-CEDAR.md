# Mapping AWS Cedar and Amazon Verified Permissions onto Cerbos

The closest fit of the named systems — the evaluation model genuinely lines up.

| Cedar | Cerbos |
|---|---|
| `permit` | `effect: EFFECT_ALLOW` |
| `forbid` | `effect: EFFECT_DENY` |
| Forbid overrides permit | Deny overrides allow for the same role — the same posture |
| Default deny when nothing permits | Deny-by-default |
| The principal element of the scope | `roles`, or a principal policy for a specific principal |
| The action element of the scope | The rule's `actions` |
| The resource element of the scope | The resource `kind` |
| `when` | A `condition` |
| `unless` | A `condition` with a `none` block |
| Context | Request attributes, or auxiliary JWT data |
| A schema | JSON schemas on the resource policy |
| A policy template with linked policies | Static policies with dynamic context, or scoped policies where tenants differ |

**Does not survive.** The entity store. Cedar resolves `in` against a supplied entity hierarchy — group membership, resource containment, parent chains — and Cerbos has no entity graph. Two replacements, and which one fits depends on the shape:

- **A containment path** — org, then department, then team — maps well to a dotted string plus the [hierarchy functions](https://docs.cerbos.dev/cerbos/latest/recipes/hierarchies-and-multi-tenancy?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-authz-migration_pdp-recipes-hierarchies-and-multi-tenancy) (`ancestorOf`, `descendentOf`, `immediateParentOf`, `siblingOf` and the rest), which is the same idea expressed as a prefix comparison rather than a graph walk.
- **Arbitrary membership** — a user in several unrelated groups — becomes a principal attribute listing them, with the condition testing membership.

Cedar's action groups flatten into action wildcards where the naming supports it; where it does not, list the actions explicitly.
