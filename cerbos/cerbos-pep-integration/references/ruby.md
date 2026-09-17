# Ruby PEP

Source of truth: [`cerbos/cerbos-sdk-ruby`](https://github.com/cerbos/cerbos-sdk-ruby). Gem `cerbos`, gRPC. Requires Ruby 3.3+ and a Cerbos PDP 0.16+.

## Install

```console
$ bundle add cerbos
```

```ruby
require "cerbos"
```

## Connecting

```ruby
client = Cerbos::Client.new("localhost:3593", tls: false)
```

```ruby
Cerbos::Client.new(target, tls:, grpc_channel_args: {}, grpc_metadata: {},
                   on_validation_error: :return, playground_instance: nil, timeout: nil)
```

`tls:` is a required keyword with no default — the SDK makes you state it. Pass `false` for plaintext, `Cerbos::TLS.new(root_certificates_pem: nil)`, or `Cerbos::MutualTLS.new(client_certificate_pem:, client_key_pem:, **tls_settings)`. `target` accepts `"host"`, `"host:port"` or `"unix:/var/run/cerbos.grpc.sock"`.

`on_validation_error:` takes `:return` (default — read the errors off the response), `:raise`, or a callable.

**Forking servers** (Puma in cluster mode, Unicorn, Passenger) need care: the underlying `grpc` gem requires version 1.57.0+, `GRPC_ENABLE_FORK_SUPPORT=1`, and `GRPC.prefork` / `GRPC.postfork_parent` / `GRPC.postfork_child` hooks around the fork. Support is Linux-only and experimental. The simpler alternative is to create the client lazily after fork, in each worker.

## Checking

```ruby
decision = client.check_resource(
  principal: { id: "user@example.com", roles: ["USER"] },
  resource: { kind: "document", id: "1", attr: { owner: "author@example.com" } },
  actions: ["view", "edit"]
)

decision.allow?("view") # => true
```

```ruby
decision = client.check_resources(
  principal: { id: "user@example.com", roles: ["USER"] },
  resources: [
    { resource: { kind: "document", id: "1" }, actions: ["view", "edit"] },
    { resource: { kind: "image", id: "1" }, actions: ["delete"] }
  ]
)

decision.allow?(resource: { kind: "document", id: "1" }, action: "view")
```

```ruby
client.allow?(principal:, resource:, action: "view") # => Boolean
```

Three methods, all keyword-argument: `allow?` for one action, `check_resource` for several actions on one resource, `check_resources` for a batch. Note the selector asymmetry — `allow?` on a single-resource decision takes a bare action string, on a batch decision it takes a hash.

Principals and resources take plain Hashes, or the explicit `Cerbos::Input::Principal`, `Input::Resource`, `Input::ResourceCheck` and `Input::ResourceQuery` objects when you want the constructor to validate them for you.

Every call also accepts `aux_data:`, `include_metadata:`, `request_id:`, `request_context:` and `grpc_metadata:`.

Also on the client: `check_health(service: "cerbos.svc.v1.CerbosService")` and `server_info`.

## Query plan

```ruby
plan = client.plan_resources(
  principal: { id: "user@example.com", roles: ["USER"] },
  resource: { kind: "document" },
  actions: ["view"]
)

if plan.conditional?
  apply(plan.condition)
end
```

`actions:` needs a PDP running Cerbos v0.44+. The singular `action:` is deprecated. Branch on the kind — `conditional?` and its siblings — before reading `condition`; see [query-plan.md](query-plan.md).

There is no published Ruby query plan adapter. An ActiveRecord adapter exists in [`cerbos/query-plan-adapters`](https://github.com/cerbos/query-plan-adapters) as a work-in-progress prototype and is not on RubyGems, so treat it as a starting point to vendor and finish, not a dependency.

## JWT auxiliary data

```ruby
client.check_resource(
  principal:, resource:, actions: ["view"],
  aux_data: Cerbos::Input::AuxData.new(jwt: Cerbos::Input::JWT.new(token: raw, key_set_id: "ks1"))
)
```

`jwt` and `jwts` are mutually exclusive; `key_set_id` may be omitted only when the PDP has a single JWKS configured. Semantics in [api-shapes.md](api-shapes.md).

## Rails

There is no Rails engine or `before_action` helper in the SDK. Wire it yourself: one method that maps `current_user` onto a principal hash, an explicit `check_resource` in the controller action, and `plan_resources` for index actions. Keep the principal mapping in one place so a new attribute reaches every check at once.
