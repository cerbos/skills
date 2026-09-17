# Mapping another authorization system onto Cerbos

Phase 3, for a named source system. Each section maps concepts, then states plainly what does not survive.

These are conceptual mappings. Confirm the exact syntax of the source rules by reading them, not by trusting a shape described here — and when a source construct does not appear below, describe it in the inventory in plain language rather than forcing it into a row.

## What is true of every one of them

Three constraints apply no matter which system you are leaving, and they account for most of the gap register.

**No data.** The Cerbos PDP is stateless and holds none of your entities. Every system below can, in some form, resolve a fact about the world during evaluation — a bundled data document, a grouping table, a tuple store, an entity store. In Cerbos that fact arrives as a request attribute. The lookup does not disappear; it moves to the PEP, to a Synapse data source, or to a service that keeps answering it.

**No ordering.** Cerbos [conflict resolution](https://docs.cerbos.dev/cerbos/latest/policies/evaluation) is fixed: for a single role, a matching deny beats a matching allow; across roles, an allow from any role wins; anything without an explicit allow is denied. There is no priority field and no first-match. A rule set whose meaning depends on evaluation order has to be restated, not translated.

**Boolean only.** A condition must evaluate to a boolean. Rules that compute documents, transform inputs, or aggregate over data stay in the application. An [output](https://docs.cerbos.dev/cerbos/latest/policies/outputs) can return a map alongside the decision, but it does not participate in it.

## OPA / Rego

| Rego | Cerbos |
|---|---|
| A package per resource or service | A [resource policy](https://docs.cerbos.dev/cerbos/latest/policies/resource_policies) per resource kind |
| `default allow = false` | Deny-by-default, already the engine's behaviour — nothing to write |
| Multiple definitions of `allow`, implicitly OR'd | Multiple rules for the same action; any matching allow grants |
| A rule body's conjunction of expressions | A `condition` with an `all` block |
| `input.user`, `input.action`, `input.resource` | `request.principal`, the rule's `actions`, `request.resource` |
| A role test inside a body | `roles` on the rule, hoisted out of the condition |
| Helper rules used as named predicates | [Exported variables](https://docs.cerbos.dev/cerbos/latest/policies/variables), imported where needed |
| Constants in `data` | Exported constants |
| Entity data loaded into `data` | Request attributes. There is no store to load them into |
| Partial evaluation for filtering | [`PlanResources`](https://docs.cerbos.dev/cerbos/latest/recipes/filtering-resources); both return a residual condition for a query layer |
| `deny[msg]` sets, as used for admission control | `EFFECT_DENY` rules; the message becomes an `output`, not part of the effect |

**Does not survive.** Comprehensions and aggregation over a data document — `count`, `sum`, set operations across entities — have no equivalent, because the entities are not there to iterate. Rules producing non-boolean values. Recursive or mutually-dependent rule graphs. Anything relying on the bundle being a queryable document rather than a request payload.

**The reframe that usually works.** Rego policies are typically written against a rich `input` and a rich `data`. In Cerbos the split is different: identity facts go on `request.principal`, object facts on `request.resource`, and there is no third place. Re-partitioning the Rego `input` into those two buckets, and deciding who supplies the facts that used to come from `data`, is most of the design work.

## Casbin

| Casbin | Cerbos |
|---|---|
| `[request_definition]` subject, object, action | `request.principal`, `request.resource`, the requested action |
| A `p` policy line — subject, object, action | One rule in the resource policy for that object |
| A `g` grouping line assigning a user to a role | Role assignment. It leaves the policy entirely and is sent as `principal.roles` from the IdP or the app |
| A `g` line nesting one role inside another | Flatten into the roles sent at request time, or express as [role policy](https://docs.cerbos.dev/cerbos/latest/policies/role_policies) `parentRoles` when the child role genuinely narrows the parent |
| `[matchers]` expression | A CEL `condition`, once the role and object matching is hoisted into `roles` and the resource `kind` |
| Path or pattern matching on the object | The resource `kind` plus action wildcards, or a `matches()` condition on an attribute. Cerbos action wildcards honour the `:` delimiter — `view:*` matches `view:public` but not `view` |
| A domain or tenant argument in the model | A tenant attribute in a condition, or a [scope](https://docs.cerbos.dev/cerbos/latest/policies/scoped_policies) if tenants have genuinely different rules |
| An explicit deny effect in a policy line | `EFFECT_DENY` on the rule |

**Does not survive.** The `[policy_effect]` line. Casbin lets the effect expression itself be configured — allow-override, deny-override, priority, and custom combinations — and Cerbos's resolution is fixed. A deny-override model maps cleanly and needs no thought. A priority model does not map at all: work out what the priorities were compensating for and write that intent directly.

**Watch for.** Casbin policy lines usually live in a CSV or a database table that the application writes to at runtime. If your application adds `p` lines in response to user actions, those are data, not policy — model them as attributes, or generate per-tenant policy into a store through the Hub SDK. Moving a runtime-writable table into files makes every user action a deploy.

## Oso

| Oso | Cerbos |
|---|---|
| `allow(actor, action, resource)` rules | Resource policy rules |
| A resource block's declared `permissions` | The rule's `actions` |
| A resource block's declared `roles` | Static `roles`, if assigned by the IdP; otherwise see below |
| A role held *on a specific resource* | A [derived role](https://docs.cerbos.dev/cerbos/latest/policies/derived_roles) conditioned on an attribute that names the actor's relation to that instance |
| Rule bodies testing actor or resource fields | A CEL `condition` |
| Shorthand rules implying a role on a related resource | Relationship resolution — see the caveat below |
| Data filtering / list endpoints | `PlanResources` and a query plan adapter |

**Does not survive.** Polar is a logic language with unification and rule chaining; CEL is a single-expression evaluator. Rules that recurse through relations, or that rely on Oso resolving a relation to fetch the related object, need the relation supplied as an attribute instead. Oso deployments that register application classes so policy can call into them have no equivalent — a Cerbos condition cannot call your code.

Oso sits between the code-shaped and relationship-shaped families. Read the actual policy: one dominated by field comparisons maps easily; one dominated by `relations` and role inheritance across resources belongs in the next section.

## SpiceDB, OpenFGA, Auth0 FGA — the Zanzibar family

**Read this section before promising a migration.** These systems and Cerbos solve overlapping problems with fundamentally different machinery, and the mismatch is structural rather than cosmetic.

A Zanzibar-style system stores relationship tuples — *this object, this relation, this subject* — and answers a check by walking that graph: is there a path from the user to the object through the relations the schema permits? The tuple store and the graph walk are the product. Cerbos has neither. It evaluates roles, attributes and conditions supplied in the request, and never looks anything up.

| Source concept | Cerbos |
|---|---|
| Object type definition | Resource kind |
| A named permission on a type | An action |
| A direct relation that behaves like a role on an object — viewer, editor, owner | A derived role conditioned on an attribute naming the actor's relation to this instance |
| A contextual tuple supplied per request | The closest analogue to a request attribute, and the right mental model for what the PEP now sends |
| Schema type constraints | JSON [schemas](https://docs.cerbos.dev/cerbos/latest/policies/schemas) on the resource policy, enforced at `warn` or `reject` by PDP configuration |
| A list-objects query | `PlanResources`, but only over attributes — not over the graph |

**What does not map, plainly.** Computed and tuple-to-userset relations — *a viewer of a document is anyone who is a viewer of its parent folder*, group-within-group nesting, wildcard subjects, recursive containment. These are the core of the model, and Cerbos cannot evaluate them: there is no data to walk. A schema that is mostly `permission X = relation from parent` lines is mostly the part that does not port.

Three honest options, in the order they are usually right:

1. **Resolve the relationship before the call.** Your application owns the data and already knows how to answer "what is this user's effective relation to this object" — often it is a join it already runs to render the page. Send the answer as an attribute (`R.attr.user_relation`, or `P.attr.memberships`) and let Cerbos evaluate everything else: the role logic, the conditions, the tenancy, the deny rules. The graph walk moves to where the graph lives. This is the option that makes the migration worth doing, because the code being replaced is the *rule* logic, not the traversal.
2. **Fetch it inside the authorization path.** A Synapse data source performs the lookup during the check, so the PEP does not have to. Same computation, different place, no change to your application's call sites. See `cerbos-synapse-extension`.
3. **Keep the relationship service.** Cerbos handles roles, attributes and conditions; the existing system keeps answering reachability, and its answer is one more attribute. A partial migration, and a legitimate end state — say so rather than dressing it as a full one.

**The honest recommendation.** Count the schema. If most permissions are direct relations with conditions layered on top, the migration is straightforward and option 1 is enough. If most are transitive rewrites over a deep hierarchy, tell the user directly that Cerbos is not a drop-in replacement for that part, and that they are choosing between materialising the closure and keeping a graph service. Do not quietly convert a graph into a hand-maintained attribute and discover the maintenance cost in production.

Auth0 FGA is OpenFGA; everything here applies unchanged.

## Keycloak authorization services

Keycloak has two halves and only one of them moves. It stays your identity provider: authentication, realm and client roles, group membership, token issuance. Those roles keep arriving in the token and become `principal.roles`. What migrates is the authorization-services half.

| Keycloak | Cerbos |
|---|---|
| Realm and client roles | Roles sent on the request. Keycloak keeps owning them |
| Groups | A principal attribute, or roles, depending on how policies use them |
| A protected resource, with its type | A resource kind |
| Authorization scopes on a resource | Actions |
| A role-based policy | `roles` on a rule |
| A group-based policy | A condition over a group attribute, or a derived role |
| A user-based policy | A [principal policy](https://docs.cerbos.dev/cerbos/latest/policies/principal_policies) |
| A time-based policy | A condition using `now()` |
| A client or scope policy | A condition over a token claim, sent as auxiliary JWT data |
| A rule written in script | A CEL condition, rewritten by hand — the semantics do not transfer mechanically |
| An aggregated policy combining others | Nested `all` / `any` / `none` condition blocks |
| A resource-based or scope-based permission tying policies to a resource | The rule itself |

**Does not survive.** Decision strategies. Unanimous maps to nesting the policies under `all`, and Affirmative to `any`, so those two are recoverable as conditions. **Consensus has no equivalent** — Cerbos does not count votes. A permission relying on it needs its intent restated as an explicit condition.

Also gone: resource attributes stored on the Keycloak resource itself. Cerbos takes resource attributes from the request, so whatever the application was relying on Keycloak to remember about a resource now has to be sent with the check.

## AWS Cedar / Amazon Verified Permissions

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

- **A containment path** — org, then department, then team — maps well to a dotted string plus the [hierarchy functions](https://docs.cerbos.dev/cerbos/latest/recipes/hierarchies-and-multi-tenancy) (`ancestorOf`, `descendentOf`, `immediateParentOf`, `siblingOf` and the rest), which is the same idea expressed as a prefix comparison rather than a graph walk.
- **Arbitrary membership** — a user in several unrelated groups — becomes a principal attribute listing them, with the condition testing membership.

Cedar's action groups flatten into action wildcards where the naming supports it; where it does not, list the actions explicitly.

## After mapping

Every source rule reaches one of three outcomes, and the migration is only auditable if all three are written down:

- **Mapped** — a Structured Intent row with its Source column pointing back at the original.
- **On the gap register** — with the option chosen and who chose it.
- **Deliberately dropped** — dead, unreachable, superseded, or protecting something that no longer exists. Record the reason. A stale rule deleted on purpose is a good outcome; one that vanished during translation is an incident waiting to happen.
