# Mapping SpiceDB, OpenFGA and Auth0 FGA onto Cerbos

**Read this before promising a migration.** These systems and Cerbos solve overlapping problems with fundamentally different machinery, and the mismatch is structural rather than cosmetic.

A Zanzibar-style system stores relationship tuples — *this object, this relation, this subject* — and answers a check by walking that graph: is there a path from the user to the object through the relations the schema permits? The tuple store and the graph walk are the product. Cerbos has neither. It evaluates roles, attributes and conditions supplied in the request, and never looks anything up.

| Source concept | Cerbos |
|---|---|
| Object type definition | Resource kind |
| A named permission on a type | An action |
| A direct relation that behaves like a role on an object — viewer, editor, owner | A derived role conditioned on an attribute naming the actor's relation to this instance |
| A contextual tuple supplied per request | The closest analogue to a request attribute, and the right mental model for what the PEP now sends |
| Schema type constraints | JSON [schemas](https://docs.cerbos.dev/cerbos/latest/policies/schemas?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-authz-migration_pdp-policies-schemas) on the resource policy, enforced at `warn` or `reject` by PDP configuration |
| A list-objects query | `PlanResources`, but only over attributes — not over the graph |

**What does not map, plainly.** Computed and tuple-to-userset relations — *a viewer of a document is anyone who is a viewer of its parent folder*, group-within-group nesting, wildcard subjects, recursive containment. These are the core of the model, and Cerbos cannot evaluate them: there is no data to walk. A schema that is mostly `permission X = relation from parent` lines is mostly the part that does not port.

Three honest options, in the order they are usually right:

1. **Resolve the relationship before the call.** Your application owns the data and already knows how to answer "what is this user's effective relation to this object" — often it is a join it already runs to render the page. Send the answer as an attribute (`R.attr.user_relation`, or `P.attr.memberships`) and let Cerbos evaluate everything else: the role logic, the conditions, the tenancy, the deny rules. The graph walk moves to where the graph lives. This is the option that makes the migration worth doing, because the code being replaced is the *rule* logic, not the traversal.
2. **Fetch it inside the authorization path.** A Synapse data source performs the lookup during the check, so the PEP does not have to. Same computation, different place, no change to your application's call sites. See `cerbos-synapse-extension`.
3. **Keep the relationship service.** Cerbos handles roles, attributes and conditions; the existing system keeps answering reachability, and its answer is one more attribute. A partial migration, and a legitimate end state — say so rather than dressing it as a full one.

**The honest recommendation.** Count the schema. If most permissions are direct relations with conditions layered on top, the migration is straightforward and option 1 is enough. If most are transitive rewrites over a deep hierarchy, tell the user directly that Cerbos is not a drop-in replacement for that part, and that they are choosing between materialising the closure and keeping a graph service. Do not quietly convert a graph into a hand-maintained attribute and discover the maintenance cost in production.

Auth0 FGA is OpenFGA; everything here applies unchanged.
