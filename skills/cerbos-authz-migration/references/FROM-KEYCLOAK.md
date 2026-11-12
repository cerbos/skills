# Mapping Keycloak authorization services onto Cerbos

Keycloak has two halves and only one of them moves. It stays your identity provider: authentication, realm and client roles, group membership, token issuance. Those roles keep arriving in the token and become `principal.roles`. What migrates is the authorization-services half.

| Keycloak | Cerbos |
|---|---|
| Realm and client roles | Roles sent on the request. Keycloak keeps owning them |
| Groups | A principal attribute, or roles, depending on how policies use them |
| A protected resource, with its type | A resource kind |
| Authorization scopes on a resource | Actions |
| A role-based policy | `roles` on a rule |
| A group-based policy | A condition over a group attribute, or a derived role |
| A user-based policy | A [principal policy](https://docs.cerbos.dev/cerbos/latest/policies/principal_policies?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-authz-migration_pdp-policies-principal-policies) |
| A time-based policy | A condition using `now()` |
| A client or scope policy | A condition over a token claim, sent as auxiliary JWT data |
| A rule written in script | A CEL condition, rewritten by hand — the semantics do not transfer mechanically |
| An aggregated policy combining others | Nested `all` / `any` / `none` condition blocks |
| A resource-based or scope-based permission tying policies to a resource | The rule itself |

**Does not survive.** Decision strategies. Unanimous maps to nesting the policies under `all`, and Affirmative to `any`, so those two are recoverable as conditions. **Consensus has no equivalent** — Cerbos does not count votes. A permission relying on it needs its intent restated as an explicit condition.

Also gone: resource attributes stored on the Keycloak resource itself. Cerbos takes resource attributes from the request, so whatever the application was relying on Keycloak to remember about a resource now has to be sent with the check.
