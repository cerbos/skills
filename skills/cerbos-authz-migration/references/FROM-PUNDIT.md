# Mapping Pundit onto Cerbos

A Pundit policy is a Ruby class, `PostPolicy`, built from `(user, record)` with one predicate method per action — the `can()` helper from [MAPPING-CODE.md](MAPPING-CODE.md) with a naming convention. Method bodies map like any hand-rolled check; this file covers what the convention adds.

| Pundit | Cerbos |
|---|---|
| `PostPolicy`, or a class named with `policy_class:` | A resource policy for the kind the handler loads |
| A predicate method, `update?` | An action, `update` |
| `new?` → `create?`, `edit?` → `update?`, `alias_method :publish?, :update?` | One action per controller action, each carrying its target's rules. Read the method that runs, through aliases, `ApplicationPolicy` and shared modules |
| A `true` default on `ApplicationPolicy` | A grant on every kind whose policy leaves it alone |
| Private helpers — `owner?`, `same_org?` | Derived roles when they name a relation to the record; exported variables when policies share a predicate |
| `authorize Post` — the class | A check on a placeholder `id` with no attributes; its rules read principal facts only |
| `authorize :dashboard, :show?` — a headless policy | A kind of its own with no attributes |
| `authorize [:admin, post]` → `Admin::PostPolicy` | The same kind as `PostPolicy`. Fold its rules in, putting the namespace's difference in a role, a condition or a distinct action name |
| `pundit_user` returning a wrapper such as `UserContext.new(current_user, request.ip)` | A principal attribute or auxiliary data per extra field |
| `Scope#resolve` | `PlanResources`; see below |
| `expected_attributes_for_action`, `permitted_attributes` | Field-level authorization; see below |
| `rescue_from Pundit::NotAuthorizedError` | Stays in the PEP, response unchanged |

**Queries in disguise.** A predicate runs with an open ActiveRecord connection, so `record.project.members.include?(user)` reads like a comparison and is a computed attribute. Read every body for association calls.

**The scope is a second rule set.** `show?` and `Scope#resolve` are written separately and drift — `show?` admits collaborators while `resolve` returns owned rows. Cerbos derives both from one rule. Extract each as its own row, compare them, and put every mismatch to the user as an open question.

**Field-level permissions.** The permitted-attributes list varies per user. Model field groups as actions (`update:title`) checked in one `CheckResources` call before filtering params, or keep the lists in the controller and record them on the gap register.

**Guests.** A signed-out visitor reaches the policy as `user = nil`. Send guests as a fixed principal with a role such as `anonymous`, and map each `nil` branch to rules on it. A method that raises `NoMethodError` on `nil` answers `500` today; record that as current behaviour. An `ApplicationPolicy#initialize` that raises `NotAuthorizedError` for some users (signed out, suspended) is a deny on `roles: ["*"]` across every action of every kind it covers.

**Inferred queries.** `authorize @post` calls `"#{action_name}?"`; a route with no matching method raises `NoMethodError`. Enumerate from `rails routes` and record the query each route reaches.

**The shim.** Override `authorize` and `policy_scope` once in `ApplicationController`, so controllers keep their call sites on the first flip.
