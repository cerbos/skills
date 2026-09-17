# Finding authorization in an unfamiliar codebase

Phase 1 of the migration. The goal is a list of **guards** with a `file:line` for each, and a list of entry points that reach no guard at all.

Examples below use `rg`; `grep -rEn` takes the same patterns.

## Sweep order

Work outside in. Each pass narrows the next.

1. **Entry points.** Enumerate every route, handler, resolver, RPC method, queue consumer and scheduled job in the slice. This is the denominator: the completion criterion is that every one of them is accounted for.
2. **Declared guards.** Middleware, decorators, annotations and guard registrations — the places a framework lets you attach a check without writing one. Cheapest to find and usually the coarse layer.
3. **Inline guards.** Role and permission comparisons inside handlers and services. The long tail, and where the conditional rules live.
4. **Silent guards.** Query filters and ORM scopes that narrow results rather than refusing. They enforce without ever returning 403, so they never appear in a search for `403`.
5. **Stored guards.** Permission rows in the database, and permission maps in config.
6. **Intent evidence.** Tests and UI conditionals. Not enforcement, but the clearest statement of what the rules were meant to be.

## Generic sweep

Start here regardless of language. High recall, plenty of noise — the point is to find the vocabulary this codebase uses, then search for that.

```bash
rg -n --stats -i '\b(authoriz|permission|forbidden|unauthori[sz]ed|access[_ ]?denied|not[_ ]?allowed)\b'
rg -n -i '\b(is_?admin|is_?owner|is_?staff|is_?superuser|has_?role|has_?permission|can_?[a-z]+)\b'
rg -n '\b(403|401|Forbidden|PermissionDenied|AccessDenied|NotAuthorized)\b'
rg -n -i "role\s*(==|===|!=|!==|\.eq|in|\bis\b)\s*['\"]"
```

The `--stats` line matters more than the hits. One helper name appearing 200 times means the codebase has a convention and you should read that helper first. A flat spread of ad-hoc comparisons means there is no convention and every hit is its own rule.

Once you know the vocabulary, re-run narrowly on it. A codebase that says `ensureCan(...)` everywhere is fully enumerated by one search.

## By language

| Language | Patterns worth a pass |
|---|---|
| JavaScript / TypeScript | `req.user.role`, `session.user`, `ctx.user`, `\.roles\.(includes|some|indexOf)`, `@UseGuards`, `@Roles\(`, `canActivate`, `abilities?\.can\(`, `authorize\(`, `requireRole` |
| Python | `request.user.(is_staff|is_superuser|has_perm)`, `@permission_required`, `@user_passes_test`, `@login_required`, `permission_classes`, `has_object_permission`, `Depends\(.*(auth|perm|role)` |
| Go | `ctx.Value\(.*[Uu]ser`, `middleware\.`, `if .*\.Role(s)? (==|!=)`, `Authorize|CanAccess|HasRole|checkPerm`, `casbin\.Enforce` |
| Java / Kotlin | `@PreAuthorize`, `@PostAuthorize`, `@Secured`, `@RolesAllowed`, `hasRole\(|hasAuthority\(`, `SecurityContextHolder`, `AccessDecisionVoter` |
| Ruby | `before_action :(authorize|require_|check_)`, `authorize `, `policy\(`, `can\? :`, `current_user\.(admin\?|has_role)`, `Pundit`, `CanCan` |
| PHP | `Gate::(allows|denies|authorize)`, `@can\(`, `->can\(`, `#\[IsGranted`, `is_granted\(`, `AuthorizationChecker`, `middleware\('can:` |
| C# / .NET | `\[Authorize`, `\[AllowAnonymous\]`, `User\.IsInRole`, `IAuthorizationHandler`, `RequireClaim`, `policy:` |

`@AllowAnonymous`, `@login_required`-without-more and `skip_before_action` are as informative as the positive matches: they mark entry points that deliberately reach no guard, which is exactly the list Phase 1 owes the user.

## By framework — where guards attach

| Framework | Attachment points |
|---|---|
| Express / Koa / Fastify | `app.use`, per-route middleware arrays, error handlers that map an auth error to 403 |
| NestJS | `@UseGuards`, `CanActivate` implementations, `@SetMetadata('roles', ...)` |
| Django / DRF | `permission_classes`, `has_permission` / `has_object_permission`, `Model.Meta.permissions`, admin `ModelAdmin` overrides, custom `QuerySet` managers |
| FastAPI | `Depends(...)` chains carrying the current user, router-level dependencies |
| Rails | `before_action`, Pundit policy classes, CanCanCan `Ability`, `default_scope` on models |
| Spring | `@PreAuthorize` / `@Secured` on controllers and services, `SecurityFilterChain` matchers, method security on repositories |
| Laravel | `Gate::define`, `*Policy` classes, `can:` route middleware, `@can` in Blade templates |
| ASP.NET Core | `[Authorize(Policy = ...)]`, `AddAuthorization` policy registrations, `IAuthorizationRequirement` handlers |
| GraphQL (any) | Field-level directives (`@auth`, `@hasRole`), resolver-level checks, schema stitching layers |
| gRPC | Interceptors, per-method metadata checks |

Two hazards specific to attached guards:

- **Coarse guard, fine reality.** `@Authorize(Roles="Manager")` on a controller plus three `if` statements inside it is four rules, not one. Read the body.
- **Guard before load.** Middleware typically runs before the resource is fetched, so it can only check principal facts. Any rule needing resource attributes is enforced later, deeper in the handler — and after the migration the Cerbos call has to move to where the resource exists. Flag every guard where the resource is not yet loaded; that relocation is real work in Phase 5.

## Silent guards: filters that enforce

These never return 403 and never mention permissions, so the sweeps above miss them entirely. They are still rules, and they are the ones that become `PlanResources`.

```bash
rg -n -i '(where|filter|scope)\s*\(?.{0,40}(tenant|org|owner|user|account|workspace|customer)_?id'
rg -n 'default_scope|global_scope|addGlobalScope|@Filter|TenantFilter|RowLevelSecurity|CREATE POLICY'
```

Also worth a look: multi-tenant middleware that sets a connection-level or session-level variable (`SET app.current_tenant`), and Postgres row-level security policies, which are guards living in the database schema rather than the code.

A filter written as `WHERE owner_id = :me` is the same rule as `if (doc.owner !== me) throw` — one refuses, the other hides. Inventory both as the same Structured Intent row and note in Purpose which behaviour the endpoint has, because that difference survives the migration and users notice it.

## Stored guards: the database

Find the tables first:

```sql
SELECT table_name, column_name
FROM information_schema.columns
WHERE column_name ~* '(permission|role|grant|acl|scope|capabilit|entitle)'
ORDER BY table_name;
```

Then classify each table by what changes it. **Rows that change with a deploy become policy. Rows that change with a user action become attributes.** That single rule of thumb decides almost every case.

| Shape | Changes when | Becomes |
|---|---|---|
| `roles(id, name)` | A deploy | The role names used in `roles:` on rules. Not data Cerbos needs |
| `role_permissions(role, permission)` | A deploy | Resource policy rules — split `permission` into action and resource kind, one rule per group |
| `user_roles(user_id, role)` | A user action | Role assignment. Stays in the IdP or the app, sent as `principal.roles` |
| `user_permissions(user_id, permission)` | A user action | A per-user override — principal policy if there are a handful and they are stable, a principal attribute if end users grant them |
| `resource_acl(resource_id, user_id, level)` | Constantly | A resource attribute. `R.attr.acl[P.id] == "editor"`. Never a policy per resource instance |
| `group_members(group_id, user_id)` | A user action | A principal attribute carrying the user's groups |
| `tenant_roles(tenant_id, user_id, role)` | A user action | A principal attribute keyed by tenant: `P.attr.workspaces[R.attr.tenant].role` |
| `plans / entitlements(plan, feature)` | A deploy | Rules, or a derived role per plan tier |

The trap is the middle column. A permissions table that a support engineer edits in production looks like policy but behaves like data, and moving it into policy files means every support edit becomes a deploy. Ask who edits the table and how often before deciding.

The same question applies to config: a `permissions.yaml` checked into the repository is policy, the identical file fetched from a config service at boot is data.

## Intent evidence

**Tests.** Existing authorization tests are frequently the most accurate specification in the repository — they state the intended answer for a named user and a named case, which is precisely a Structured Intent row.

```bash
rg -n -i '(test|it|describe|def test_).{0,80}(403|forbidden|unauthori|permission|denied|as_(admin|user|owner))'
```

Mine them for the **Decision** and **Purpose** columns, which the production code almost never records. A test named `denies_approval_over_limit_for_junior_manager` supplies both.

**UI.** Front-end conditionals reveal what the product intends but enforce nothing — they are evidence, never the source of a rule.

```bash
rg -n -i '(canEdit|canDelete|showIf|hasPermission|isAdmin|v-if=.*role|\{user\.role)'
```

Any UI check with no matching server-side guard is a finding in its own right: the feature is hidden but not protected. Report it separately from the migration inventory.

## Feature flags doing double duty

Flags and entitlements share a shape and get mixed in the same file. Separate them, because only one moves:

- **Rollout** — is this code path enabled at all? Varies by deploy and cohort, not by who is asking. Stays a flag.
- **Entitlement** — is this account's plan allowed this capability? Varies by subject. It is authorization and it migrates, usually as a principal attribute the rule conditions on.

A flag evaluated against a user's plan, tier, or account ID is an entitlement wearing a flag's clothes.

## The negative space

The last pass. Take the entry-point list from step 1 and subtract everything that reaches a guard. What remains is either intentionally public or unprotected, and only the user can say which.

Present it as a list, one line per entry point, with the reason it appears — no middleware, an explicit anonymous marker, a guard that only checks authentication. An endpoint nobody knew was open is a security finding, and it belongs in front of a human before it becomes a policy line.
