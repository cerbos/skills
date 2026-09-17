# Rust PEP

Source of truth: [`cerbos/cerbos-sdk-rust`](https://github.com/cerbos/cerbos-sdk-rust). Crate `cerbos`, gRPC over tonic.

## Install

```bash
cargo add cerbos
```

Optional features: `admin`, `hub`, `testcontainers`, `serde`.

## Connecting

```rust
use cerbos::sdk::{CerbosAsyncClient, CerbosClientOptions, CerbosEndpoint, Result};

let opt = CerbosClientOptions::new(CerbosEndpoint::HostPort("localhost", 3593));
let mut client = CerbosAsyncClient::new(opt).await?;
```

`CerbosSyncClient::new(opt)` is the blocking equivalent. `CerbosEndpoint` is `HostPort(host, port)` or, on Unix, `UnixDomainSocket(path)`.

**TLS is on by default** — `CerbosClientOptions::new` installs a `ClientTlsConfig` and the channel scheme becomes `https`. The README example omits `.with_plaintext()`, so copying it against a local plaintext PDP fails to connect. For local development:

```rust
let opt = CerbosClientOptions::new(CerbosEndpoint::HostPort("localhost", 3593)).with_plaintext();
```

Other options: `with_tls_domain_name`, `with_tls_ca_cert_pem`, `with_timeout(Duration)` (default 2 s), `with_request_id_gen(fn)` (default UUID v4 — swap in your trace ID), `with_user_agent`, `with_playground_instance`, and with the `admin` feature `with_admin_credentials`.

The client methods take `&mut self`, so share it behind a `Mutex`, or clone the underlying channel per task.

## Checking

```rust
use cerbos::sdk::attr::attr;
use cerbos::sdk::model::{Principal, Resource};

let principal = Principal::new("alice", ["employee"])
    .with_attributes([attr("department", "marketing"), attr("geography", "GB")]);

let resource = Resource::new("XX125", "leave_request")
    .with_attributes([attr("owner", "alice"), attr("approved", true)]);

let allowed = client.is_allowed("view:public", principal, resource, None).await?;
```

**`Resource::new(id, kind)` takes the id first** — the reverse of the Go, PHP and .NET SDKs. Getting it backwards produces a resource of kind `"XX125"`, which fails to match any policy and denies everything. `Principal::new(id, roles)` is id-first as expected.

Methods, identical on both clients unless noted:

```rust
is_allowed<S>(&mut self, action: S, principal: Principal, resource: Resource, aux_data: Option<AuxData>) -> Result<bool>
check_resources(&mut self, principal: Principal, resources: ResourceList, aux_data: Option<AuxData>) -> Result<CheckResourcesResponse>
plan_resources<S>(&mut self, action: S, principal: Principal, resource: ResourceKind, aux_data: Option<AuxData>) -> Result<PlanResourcesResponse>
plan_resources_for_actions<A, S>(&mut self, actions: A, principal: Principal, resource: ResourceKind, aux_data: Option<AuxData>)  // async client only
```

There is no single-resource multi-action method: build a `ResourceList`.

```rust
use cerbos::sdk::model::ResourceList;

let resources = ResourceList::new()
    .add(Resource::new("XX125", "leave_request"), ["view:public", "defer"])
    .add(Resource::new("XX225", "leave_request"), ["approve"]);

let resp = client.check_resources(principal, resources, None).await?;
let allowed = resp.find("XX125").map(|r| r.is_allowed("view:public")).unwrap_or(false);
```

`CheckResourcesResponse` also has `find_with_predicates(...)` and `iter()`; `ResourceResult` has `is_allowed(action)`, `output(key)` and `output_entry(key)`.

Builders: `Principal` takes `add_role`, `with_policy_version`, `with_scope`, `with_attributes`, `add_attr`. `ResourceKind::new(kind)` is the plan-side resource. Attribute values come from `cerbos::sdk::attr::attr(key, value)`.

## Query plan

```rust
use cerbos::sdk::model::ResourceKind;

let plan = client
    .plan_resources("view", principal, ResourceKind::new("leave_request"), None)
    .await?;

let filter = plan.filter();
```

`plan_resources_for_actions` (multiple actions, PDP 0.44.0+) exists on `CerbosAsyncClient` only — the sync client has just `plan_resources`.

There is no Rust query plan adapter. Walk the filter AST yourself — node shapes in [api-shapes.md](api-shapes.md), and the rules in [query-plan.md](query-plan.md). Branch on the filter kind before reading the condition.

## JWT auxiliary data

The final positional parameter of every call is `aux_data: Option<AuxData>` — pass `None` when there is no token.

```rust
use cerbos::sdk::model::AuxData;

let aux = AuxData::new().with_jwt(token, Some("ks1"));
client.is_allowed("view", principal, resource, Some(aux)).await?;
```

`with_jwt` and `with_jwts` clear each other; the two forms are mutually exclusive on the wire. Semantics in [api-shapes.md](api-shapes.md).

## Errors

Every method returns `Result<_>`. A transport error is not a denial: propagate it with `?` and map it to a 5xx at the boundary, rather than `unwrap_or(false)` at the call site, which hides a PDP outage as a flood of denials.
