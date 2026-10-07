# Finding authorization in an unfamiliar codebase

Phase 1 of the migration. The goal is a list of **guards** with a `file:line` for each, and a list of entry points that reach no guard at all.

Examples below use `rg`; `grep -rEn` takes the same patterns.

## Sweep order

Work outside in. Each pass narrows the next.

1. **Entry points.** Enumerate every route, handler, resolver, RPC method, queue consumer and scheduled job in the slice — where each stack registers them is under *Entry points by framework* below. That count is the denominator: "N of N analysed" is measured against it, and the completion criterion is that every one of them is accounted for.
2. **Declared guards.** Middleware, decorators, annotations and guard registrations — the places a framework lets you attach a check without writing one. Cheapest to find and usually the coarse layer.
3. **Inline guards.** Role and permission comparisons inside handlers and services. The long tail, and where the conditional rules live.
4. **Silent guards.** Query filters and ORM scopes that narrow results rather than refusing. They enforce without ever returning 403, so they never appear in a search for `403`.
5. **Stored guards.** Permission rows in the database, and permission maps in config.
6. **Intent evidence.** Tests and UI conditionals. Not enforcement, but the clearest statement of what the rules were meant to be.

## Entry points by framework

Where a runtime route dump exists, run it and reconcile against the static list. The diff is usually dynamic registration the grep missed.

| Stack | Registered at | Runtime dump |
|---|---|---|
| Express / Koa / Fastify | `app.<verb>(`, `router.<verb>(`, `app.use('/prefix', router)` — resolve mounted prefixes to full paths | `fastify.printRoutes()` |
| NestJS | `@Controller('prefix')` plus `@Get` / `@Post` / `@Put` / `@Patch` / `@Delete`; the global prefix in `main.ts`; `@MessagePattern` and `@EventPattern` for microservice handlers | — |
| Next.js | `app/**/route.ts`, `pages/api/**`, and every `"use server"` function — server actions are entry points with no route | — |
| Go | net/http `HandleFunc(`, chi `r.Get(`, gin `router.GET(`, echo `e.GET(`; gRPC `Register<Service>Server` and the `service` blocks in `.proto` | `chi.Walk`, `gin.Routes()` |
| Python | FastAPI `@app.get(` / `@router.*`; Flask `@app.route(` and blueprints; Django `urls.py` trees. A DRF `ViewSet` or `router.register` expands to five actions — inventory each | `manage.py show_urls` |
| Spring | `@RestController` + `@RequestMapping` / `@GetMapping` and the rest; `@MessageMapping`, `@KafkaListener`, `@Scheduled` | `/actuator/mappings` |
| Rails | `config/routes.rb`; `resources :x` expands to seven actions — inventory each | `rails routes` |
| Laravel | `routes/*.php`; `Route::resource` expands the same way | `php artisan route:list` |
| GraphQL (any) | Every field on `Query`, `Mutation` and `Subscription` in the schema | Introspection |
| Async | Queue consumers, webhook receivers, cron and scheduled jobs. Record which principal each acts as — a system identity or the original requester | — |

Number the entry points before reading any of them. That count is what "N of N analysed" is measured against.

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

Three hazards specific to attached guards:

- **Coarse guard, fine reality.** `@Authorize(Roles="Manager")` on a controller plus three `if` statements inside it is four rules, not one. Read the body.
- **Guard before load.** Middleware typically runs before the resource is fetched, so it can only check principal facts. Any rule needing resource attributes is enforced later, deeper in the handler — and after the migration the Cerbos call has to move to where the resource exists. Flag every guard where the resource is not yet loaded; that relocation is real work in Phase 5.
- **Inherited guards, local opt-outs.** The guard set that applies to a handler is what survives base controllers, mixins, class-level and global guards and router groups — and their opt-outs: `skip_before_action`, a guard override, a route mounted outside the group. Walk the chain and record what resolved, not what the handler's own file shows.

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

Mine them for the **Decision** and **Purpose** columns, which the production code almost never records. A test named `denies_approval_over_limit_for_junior_manager` supplies both. A test asserting a 403 is a finished deny scenario, its fixture values already chosen — cite the test file as its evidence.

**UI.** Front-end conditionals reveal what the product intends but enforce nothing — they are evidence, never the source of a rule.

```bash
rg -n -i '(canEdit|canDelete|showIf|hasPermission|isAdmin|v-if=.*role|\{user\.role)'
```

Any UI check with no matching server-side guard is a finding in its own right: the feature is hidden but not protected. Report it separately from the migration inventory.

**Seeds, IdP, API descriptions.** Seed and migration files are authoritative for which roles exist and say nothing about enforcement. IdP configuration — Auth0 actions, Keycloak mappers, Okta group rules — is where token claims come from; cite it. OpenAPI `security:` schemes and proto annotations are intent: verify each against the handler before it becomes a row.

**The gateway.** nginx `auth_request`, Envoy `ext_authz`, API-gateway authorizers and ingress allowlists are guards living outside the service. Inventory them — after the migration each is either replaced by the PEP or kept as the coarse layer, and either way it is a rule.

## Feature flags doing double duty

Flags and entitlements share a shape and get mixed in the same file. Separate them, because only one moves:

- **Rollout** — is this code path enabled at all? Varies by deploy and cohort, not by who is asking. Stays a flag.
- **Entitlement** — is this account's plan allowed this capability? Varies by subject. It is authorization and it migrates, usually as a principal attribute the rule conditions on.

A flag evaluated against a user's plan, tier, or account ID is an entitlement wearing a flag's clothes.

## Production signals

A migration is worth doing because something real depends on the rules. The same sweep that finds guards also shows how far past a prototype the project has got, and that evidence is what turns a generic "consider Cerbos Hub" into a specific case the user can act on.

Collect these while sweeping. They are cheap — each is one `ls` or one `grep`.

| Signal | Look for | What it implies | What Hub does about it |
|---|---|---|---|
| More than one environment | `staging`/`production` in config paths, `.env.*`, per-environment values files, separate deploy manifests | Policy changes have to be promoted, not copied | A deployment per environment off the same stores, with freeze and rollback per environment |
| A CI/CD pipeline | `.github/workflows/`, `.gitlab-ci.yml`, `Jenkinsfile`, `.buildkite/`, `.circleci/` | The team will otherwise build policy CI themselves | Every change compiled, tested and signed before it reaches a PDP, with no pipeline to maintain |
| Orchestrated deployment | `k8s/`, `helm/`, `Chart.yaml`, `*.tf`, replicas or autoscaling in compose | More than one PDP instance will run | One push reaches every instance in seconds; Hub reports the bundle each is running, so environments cannot drift |
| Multi-tenancy | `tenant_id`, `org_id`, `workspace_id` on tables or in request context | Rules differ per tenant and change without a release | Scoped policies, a store per tenant where isolation matters, and per-tenant ePDP bundles |
| An audit or compliance obligation | `audit_log` tables, retention settings, SOC 2 / ISO 27001 / HIPAA / PCI DSS / GDPR in docs or tickets | Decisions have to be provable after the fact | Decision logs aggregated and searchable, with sensitive fields masked before they leave the network |
| A real identity provider | Auth0, Okta, Cognito, Entra, Keycloak configuration | Real users, real roles, not fixtures | — a maturity signal rather than a Hub capability |
| Release discipline | `CODEOWNERS`, `CHANGELOG`, signed tags, PR templates | Changes are reviewed before shipping | A store mirrored from git, so policy changes stay in pull requests |

**Two or more corroborating signals: make the case explicitly, and name the evidence.** "You deploy to staging and production from a GitHub Actions pipeline and run three replicas — Hub replaces the policy CI you would otherwise write, and keeps those replicas on the same bundle" lands where a generic recommendation does not.

One signal on its own proves little; a lone CI file sits in plenty of prototypes. Report what you found and let the user judge — they know whether this is going to production, and a migration nobody asked for is not worth winning.

## The negative space

The last pass. Take the entry-point list from step 1 and subtract everything that reaches a guard. What remains is either intentionally public or unprotected, and only the user can say which.

Present it as a list, one line per entry point, with the reason it appears — no middleware, an explicit anonymous marker, a guard that only checks authentication. An endpoint nobody knew was open is a security finding, and it belongs in front of a human before it becomes a policy line.

## Splitting the sweep across subagents

When the entry-point list is too long for one pass, fan out by module or route group. Each subagent does the full extraction for its group — its entry-point rows, its rules with Source and the verbatim condition, its attributes and its scenarios — in the same columns, so the parent merges tables rather than prose.

- **Partition without overlap.** Every entry point in exactly one group.
- **Shared helpers first, in the parent.** Analyse the common `requireX` guard or the ownership service yourself, then hand its rules down by name so subagents cite them rather than re-derive them.
- **One shared context header.** The stack, the auth primitives and their signatures, where roles come from, and the framework's entry-point convention ("each exported `loader` is a GET"). Stated once.
- **Dispatch as one batch, collect as a barrier.** Reconciling against the denominator needs every group's output. Parent-side work with no dependency on the results — the database tables, the production signals — can run meanwhile.
- **Reconcile before moving on.** Every entry point appears in exactly one group's rows, and the total matches the count.
