# Ruby integration recipe

**SDK packages**: [cerbos](https://rubygems.org/gems/cerbos) (gRPC client; requires Ruby >= 3.2 and a Cerbos PDP >= 0.16)
**Live sources — fetch these before writing any integration code:**
- SDK repo README: https://raw.githubusercontent.com/cerbos/cerbos-sdk-ruby/main/README.md
- SDK API docs (authoritative for signatures): https://cerbos.github.io/cerbos-sdk-ruby — start at `Cerbos::Client`
- Docs index: https://docs.cerbos.dev/llms.txt

This is a pointer-tier recipe: it names the verified entry points and where checks belong.
Fetch the live sources above for the full API surface before writing code.

## 1. Client setup

`bundle add cerbos`. The client speaks gRPC to the PDP (port 3593); `tls:` is a required
keyword (`false` for local dev, or a `Cerbos::TLS`/`Cerbos::MutualTLS` config — see the
README).

```ruby
# config/initializers/cerbos.rb (Rails) — or your app's boot file
CERBOS = Cerbos::Client.new(
  ENV.fetch("CERBOS_ADDRESS", "localhost:3593"),
  tls: false,
  timeout: 2, # seconds; keep short — an authz call sits on every request path
  on_validation_error: :raise, # surface schema violations instead of silently returning
)
```

One client per **process**, never per request. **Forking-server gotcha**: gRPC channels do
not survive `fork`. Under Puma in clustered mode, Unicorn, or Spring, construct the client
after fork (Puma `on_worker_boot`) or lazily memoize it per process (`@client ||=` keyed by
`Process.pid`) — a client created in the master process will hang or error in workers.

## 2. Principal construction

One canonical helper maps the app's auth context to a principal hash; every check and plan
call goes through it. `roles` must be non-empty; `attr` carries only attributes that policy
conditions read.

```ruby
# app/lib/authz/principal.rb
module Authz
  def self.principal(user)
    {
      id: user.id.to_s,
      roles: user.roles.presence || ["user"],
      attr: {
        department: user.department,
        tenant_id: user.tenant_id,
      },
    }
  end

  def self.resource(kind, record)
    { kind: kind, id: record.id.to_s, attr: resource_attrs(kind, record) }
  end
end
```

Write `resource_attrs` per kind from the model document's §B3 / the kind's `_schemas/`
entry — the resource must carry **every** attribute the policy's conditions read, built
from the loaded ActiveRecord object, not just an id.

## 3. Framework integration points

Placement follows [ARCHITECTURE.md](../ARCHITECTURE.md): `before_action` only for gates
decidable from the request alone (authentication, role-only gates, `create` on a kind);
any decision that reads resource attributes happens after the record is loaded — in the
controller action or the service layer.

### Rails controllers

```ruby
class DocumentsController < ApplicationController
  def show
    document = Document.find(params[:id]) # 404 if missing
    head :forbidden and return unless Authz.authorize(
      endpoint: "document.view",
      request_id: request.request_id,
      principal: Authz.principal(current_user),
      resource: Authz.resource("document", document),
      action: "view",
      legacy_decision: -> { current_user.can_view?(document) },
    )
    render json: document
  end
end
```

### Pundit / CanCanCan coexistence

If the app already uses Pundit, the policy class is the natural migration seam: keep every
caller on `authorize record` and swap the *inside* of each policy predicate to the
authorization helper (legacy expression becomes the `legacy_decision` thunk). Callers never
change; cutover happens per predicate. The same applies to CanCanCan ability blocks —
migrate the checks the abilities express, one action at a time, behind the same helper.

## 4. Single-resource checks

`allow?` for one action; `check_resource` to batch actions in one round trip;
`check_resources` for multiple resources.

```ruby
CERBOS.allow?(principal: p, resource: r, action: "view") # => true/false

decision = CERBOS.check_resource(principal: p, resource: r, actions: ["view", "edit", "delete"])
decision.allow?("edit") # => true/false

results = CERBOS.check_resources(
  principal: p,
  resources: [{ resource: r1, actions: ["view"] }, { resource: r2, actions: ["view"] }],
)
results.allow?(resource: r1, action: "view") # => true/false/nil (nil = not in results)
```

A `nil` result or a raised `Cerbos::Error` is a **deny** — rescue-and-deny or let it 5xx,
never rescue-and-allow.

## 5. List filtering

Never fetch-then-filter. `plan_resources` returns `Cerbos::Output::PlanResources` with
`kind` (`:KIND_ALWAYS_ALLOWED` / `:KIND_ALWAYS_DENIED` / `:KIND_CONDITIONAL`), predicate
helpers, and a `condition` AST. There is no official ActiveRecord adapter — hand-walk the
AST into scopes, keeping the attribute-to-column map next to the model:

```ruby
plan = CERBOS.plan_resources(principal: p, resource: { kind: "document" }, action: "view")

scope =
  if plan.always_denied?      then Document.none
  elsif plan.always_allowed?  then Document.all
  else                             Document.where(compile_plan(plan.condition))
  end
scope = scope.where(deleted_at: nil) # AND with existing app filters
```

`compile_plan` walks `condition` (nested `Expression` nodes: operator + operands that are
expressions, variables like `request.resource.attr.owner_id`, or literal values) and maps
each variable to a column (`"request.resource.attr.owner_id" => :owner_id`). Implement the
operators your policies actually produce (`and`, `or`, `not`, `eq`, `ne`, `in`, `lt`, …)
and **raise on anything unmapped** — an unhandled node must become a deny (`Document.none`)
plus an error log, never an unfiltered query. See the API docs for the AST classes.

## 6. The authorization helper (real check + enforcement flag)

One helper, used at every callsite, that **always runs the real Cerbos check**; a
per-callsite mode flag decides whether a Cerbos deny blocks (`enforce`) or is only logged
while the legacy decision stands (`shadow`). There is no separate shadow helper — shadow is
a value of the flag, so the callsite is identical in every mode and cutover is a config
change. Full contract in [ARCHITECTURE.md](../ARCHITECTURE.md) §4. Greenfield integrations
pin the mode to `enforce` and omit `legacy_decision`.

**Prefer Scientist if the app has it** (github/scientist is common in Rails codebases):
legacy is the control, the Cerbos check is the candidate, and the publish hook emits the
mismatch log and counter — that satisfies the §4 contract on machinery the team already
trusts. Otherwise:

```ruby
# app/lib/authz.rb
module Authz
  def self.mode(callsite)
    key = "AUTHZ_MODE_#{callsite.upcase.gsub(/[^A-Z0-9]+/, "_")}"
    (ENV[key] || ENV["AUTHZ_MODE"]) == "enforce" ? :enforce : :shadow
  end

  # Always issues the real Cerbos check; the mode flag decides what to do with the result.
  def self.authorize(endpoint:, request_id:, principal:, resource:, action:, legacy_decision: nil)
    if mode(endpoint) == :enforce
      begin
        return CERBOS.allow?(principal: principal, resource: resource, action: action)
      rescue Cerbos::Error, GRPC::BadStatus => e
        Rails.logger.error({ event: "cerbos_check_error", endpoint: endpoint,
                             request_id: request_id, error: e.message }.to_json)
        return false # fail closed
      end
    end

    legacy = legacy_decision ? !!legacy_decision.call : true
    begin # shadow: Cerbos still runs, but must never block or fail the response
      allowed = CERBOS.allow?(principal: principal, resource: resource, action: action)
      if allowed != legacy
        Rails.logger.warn({ event: "cerbos_shadow_mismatch", endpoint: endpoint,
                            principalId: principal[:id], resourceKind: resource[:kind],
                            resourceId: resource[:id], action: action,
                            legacy: legacy, cerbos: allowed, requestId: request_id }.to_json)
      end
    rescue StandardError => e
      Rails.logger.warn({ event: "cerbos_shadow_error", endpoint: endpoint,
                          request_id: request_id, error: e.message }.to_json)
    end
    legacy
  end
end
```

The synchronous shadow call above leans on the client's short `timeout:`; to take it off
the request path entirely, move the compare into the app's job/async machinery
(ActiveJob, `Concurrent::Promises`) — never let it change the response. Emit the
match/mismatch/error counter per §4 through the app's metrics stack (StatsD/Datadog etc.)
alongside the log line.

## 7. Testing

If the app already runs a PDP via docker-compose for local dev, reuse it in tests (point
`CERBOS_ADDRESS` at it) rather than adding a new dependency — same model as tests hitting
the compose Postgres. Otherwise use [testcontainers-ruby](https://rubygems.org/gems/testcontainers)
with `ghcr.io/cerbos/cerbos:latest`, mounting the policies directory and exposing 3593.

```ruby
# spec/authz/cerbos_integration_spec.rb — decisions against the real PDP, not mocks
RSpec.describe "Cerbos decisions" do
  it "allows the owner to edit" do
    expect(CERBOS.allow?(principal: owner_principal, resource: owned_doc, action: "edit")).to be true
  end
end
```

For pure policy logic prefer Cerbos's YAML test suites (`cerbos compile --tests`); keep
app-level specs on wiring — principal construction, resource attribute completeness, plan
compilation, deny paths returning 403/empty scopes.

## 8. Local dev PDP

```yaml
# docker-compose.yml
services:
  cerbos:
    image: ghcr.io/cerbos/cerbos:latest
    command: ["server"]
    ports:
      - "3592:3592" # HTTP
      - "3593:3593" # gRPC (the Ruby SDK uses this)
    volumes:
      - ./policies:/policies:ro
```

The disk driver watches `/policies`, so policy edits apply without a restart. Point the app
at it with `CERBOS_ADDRESS=localhost:3593`.
