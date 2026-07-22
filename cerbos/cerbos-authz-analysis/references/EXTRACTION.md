# Extraction reference

How to discover entry points, recognize authorization logic, and record findings. The
patterns below cover common stacks; for anything not listed, apply the same method: find
where the framework registers externally reachable operations, then find what stands
between that registration and the business logic.

## 1. Entry-point discovery by stack

Prefer a runtime route dump where the framework offers one, and reconcile it against
static discovery — the diff is usually dynamic registration you missed.

| Stack | Discovery pattern |
|---|---|
| Express / Fastify / Koa | `app.<verb>(`, `router.<verb>(`, `app.use('/prefix', router)` — resolve mounted router prefixes to full paths. Fastify: `fastify.route(`, plugin `register` trees. |
| NestJS | `@Controller('prefix')` + `@Get/@Post/@Put/@Patch/@Delete` methods; global prefix in `main.ts`; `@MessagePattern`/`@EventPattern` for microservice handlers. |
| Next.js | `app/**/route.ts` (App Router), `pages/api/**` (Pages Router), `"use server"` server actions — server actions are entry points even without a route. Middleware in `middleware.ts`. |
| Go net/http / chi / gin / echo | `mux.HandleFunc(`, `r.Get/Post(`, `router.GET(`, `e.GET(`; middleware via `Use(`/wrappers. gRPC: `Register<Service>Server` + the `service` blocks in `.proto` files (the proto is the authoritative operation list). |
| Python FastAPI / Flask / Django | `@app.get/post(`, `@router.*`, `APIRouter(dependencies=[...])`; `@app.route(`, blueprints; Django `urls.py` trees, DRF `ViewSet`/`router.register` (expands to list/retrieve/create/update/destroy — inventory each expanded action separately). |
| Java Spring | `@RestController` + `@RequestMapping/@GetMapping/...`; also `@MessageMapping`, `@KafkaListener`, `@Scheduled`. |
| Ruby on Rails | `config/routes.rb` (`resources :x` expands to 7 actions — inventory each); `rails routes` runtime dump. |
| PHP Laravel | `routes/*.php`, `Route::resource` expansion, controller middleware; `php artisan route:list` runtime dump. |
| GraphQL (any host) | Every field on `Query`/`Mutation`/`Subscription` in the schema is an entry point; resolver maps (`resolvers.ts`, `@Resolver` classes, graphql-ruby types). Field-level guards count as per-entry-point rules. |
| Async / background | Queue consumers (Kafka/SQS/RabbitMQ/BullMQ/Sidekiq/Celery handlers), webhook receivers, cron/scheduled jobs. These often run with elevated implicit privilege — inventory them; their "principal" (system identity, original requester) is an A2 finding. |

## 2. Guard-signal catalog

What authorization looks like in code, roughly ordered from explicit to buried:

- **Route middleware / decorators**: `requireAuth`, `requireRole('admin')`, `@UseGuards(...)`,
  `@PreAuthorize("hasRole('X')")`, Rails `before_action`, Laravel `->middleware('can:...')`,
  FastAPI `Depends(get_current_admin)`. Distinguish *authentication only* from
  *authorization* — `requireAuth` alone classifies the endpoint as `role-gate` only if it
  also checks a role; otherwise the endpoint's authorization is whatever lies deeper.
- **Inherited and layered guards**: the effective guard set for a handler is resolved
  per-action *after* inheritance and opt-outs, not read off the handler's own file. Walk
  base classes and mixins (Rails `ApplicationController` + concerns, Django CBV mixins,
  NestJS/Spring class-level and global guards, router-group middleware) — and equally
  their opt-outs (`skip_before_action`, guard overrides, routes mounted outside a
  middleware group). A handler that *looks* unguarded may inherit a guard; a handler
  inside a guarded base may skip it. Record the resolved chain as the evidence.
- **Authorization libraries**: CASL (`ability.can`), Pundit/CanCanCan (`authorize`,
  policy classes), casbin (`enforcer.Enforce`), Spring Security expressions, existing
  OPA/other PDP calls, Django/DRF permission classes, homegrown `permissions.ts`-style
  modules. Library policy definitions are rule gold — extract them wholesale.
- **Inline conditionals**: role string comparisons (`user.role === 'admin'`,
  `'admin' in user.roles`), ownership checks (`x.ownerId === user.id`), tenant checks
  (`x.orgId !== user.orgId → 403`), status/state guards (`if invoice.status == 'draft'`).
  Search for the 403/Forbidden throw sites and work backwards to the condition.
- **Data-layer scoping**: ORM default scopes, repository methods that always filter by
  `user_id`/`org_id`, multi-tenant query wrappers, Postgres RLS policies (check
  migrations for `CREATE POLICY`). These are *list-enforcement* rules — record them even
  though no explicit "check" exists.
- **Permission tables**: `permissions`/`roles_permissions` DB tables, seed files, enum
  catalogs. Record the catalog in A2 and the lookup call sites as rules.
- **Infrastructure**: API-gateway/ingress config (nginx `auth_request`, Envoy ext_authz,
  API-gateway authorizers), reverse-proxy allowlists. Note in A1/A2 — enforcement outside
  the service still shapes the model.

Useful sweep starters (adapt to the codebase's vocabulary): grep for `403`, `Forbidden`,
`Unauthorized`, `permission`, `can(`, `authorize`, `isAdmin`, `role`, `owner`,
`accessDenied`, plus the auth library's API surface once identified.

## 3. Tracing and recording rules

- Follow the call chain from handler to the first business-logic statement; everything
  authorization-shaped on that path belongs to the entry point's rules. Shared helpers
  (`canEditProject(user, project)`) are rules in their own right — record once in A5,
  reference from every entry point that uses them.
- **The resource is what the handler acts on, not what it is named after.** Identify each
  entry point's resource by the object it loads and mutates, never by controller/module/
  route naming — controllers are often named by domain, not resource (an
  `AccountAdminController` action that edits surveys is a *survey* operation, not an
  account one). Name-matching produces both false positives (domain-named controllers
  touching other resources) and false negatives (handlers operating on a resource without
  mentioning it in any check). This matters twice: when grouping entry points, and later
  when Part B assigns resource kinds.
- Quote conditions **verbatim** — the exact expression, not a paraphrase — then translate
  to plain English beside it. The verbatim quote is what makes review and later parity
  checking possible.
- One rule row per distinct (subject, action, resource, condition, effect) tuple. The
  same code check reached from three endpoints is one rule with three EP references.
- **Effects**: most inline code expresses allow-or-403. Explicit deny paths (blocklists,
  `if suspended: reject`) are their own rows with effect `deny` — they matter because
  Cerbos deny rules override allows.
- Negations and early returns invert easily — when a guard reads `if (!can) throw`, the
  *rule* is the positive `can` condition. Double-check every inversion.

## 4. Confidence rubric

| Level | Meaning | Obligation |
|---|---|---|
| High | Explicit code evidence, unambiguous semantics | — |
| Medium | Inferred from framework convention or partial evidence (e.g. a guard whose implementation couldn't be fully traced) | Say what was inferred |
| Low | Conflicting or missing evidence; behavior genuinely unclear | MUST have an open question in A9 |

Confidence describes the *finding*, not the code quality. A clearly-hardcoded
`return true // TODO` is High confidence with an ugly finding.

## 5. Attribute provenance (A6)

For every attribute any rule reads, record where its value exists at request time:

- **JWT/token claim or session** — available before any DB access → checks using only
  these can run in middleware.
- **DB column on the resource** — available only after load → check belongs in the
  service/data layer, or the migration will force a redundant fetch.
- **Request parameter/body** — caller-controlled; flag any rule trusting it for an
  authorization decision (finding, not fix).
- **Derived/computed** — joins, membership lookups (`project.members.includes(user)`);
  record the computation site, these become derived-role conditions later.

## 6. Supporting evidence (non-backend)

- **Frontend gating** (`v-if="user.isAdmin"`, hidden menu items, route guards): intent
  signals only. A frontend-only restriction with no backend counterpart is a coverage-gap
  finding for that endpoint, not a rule.
- **Seed/migration files**: authoritative for the role/permission *catalog* (what roles
  exist), not for enforcement.
- **IdP configuration** (Auth0 rules/actions, Keycloak mappers, Okta groups): explains
  where token claims come from — cite in A2/A6.
- **OpenAPI/proto annotations** (`security:` schemes, custom authz extensions): treat as
  documentation of intent; verify against code before promoting to a rule.

## 7. Scenario capture (A7)

For every rule: at least one ALLOW scenario satisfying the condition and one DENY scenario
violating it, using realistic attribute values from the codebase (fixtures, tests, seeds
are good sources). Add edge cases the code visibly handles (boundary amounts, self-access,
suspended users). Existing application tests that assert 403s are pre-validated scenarios —
harvest them and cite the test file as evidence.
