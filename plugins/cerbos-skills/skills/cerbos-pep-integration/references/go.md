# Go PEP

Source of truth: [`cerbos/cerbos-sdk-go`](https://github.com/cerbos/cerbos-sdk-go), API reference on [pkg.go.dev](https://pkg.go.dev/github.com/cerbos/cerbos-sdk-go/cerbos). gRPC.

## Install

```bash
go get github.com/cerbos/cerbos-sdk-go
```

```go
import "github.com/cerbos/cerbos-sdk-go/cerbos"
```

Code written against the old in-tree `github.com/cerbos/cerbos/client` package moves to this import path.

## Connecting

```go
c, err := cerbos.New("dns:///cerbos.ns.svc.cluster.local:3593", cerbos.WithTLSCACert("/path/to/ca.crt"))
```

`New(address string, opts ...Opt) (*GRPCClient, error)`. The address carries its own port — nothing is defaulted. Any gRPC target works: `10.1.2.3:3593`, `dns:///...`, `unix:/var/sock/cerbos` for a sidecar.

**TLS is on by default.** `cerbos.WithPlaintext()` switches to h2c. Other transport options: `WithTLSAuthority`, `WithTLSInsecure`, `WithTLSCACert`, `WithTLSClientCert(cert, key)`, `WithConnectTimeout`, `WithMaxRetries`, `WithRetryTimeout`, `WithMaxRecvMsgSizeBytes`, `WithMaxSendMsgSizeBytes`, `WithUnaryInterceptors`, `WithStreamInterceptors`, `WithStatsHandler`, `WithUserAgent`, `WithPlaygroundInstance`.

Build the client once at startup and pass it down. Deadlines come from the `context.Context` you pass to each call.

## Checking

```go
allowed, err := c.IsAllowed(ctx,
    cerbos.NewPrincipal("john").
        WithRoles("employee", "manager").
        WithAttr("department", "marketing"),
    cerbos.NewResource("leave_request", "XX125").
        WithAttributes(map[string]any{"owner": "harry", "status": "DRAFT"}),
    "view",
)
```

`NewResource(kind, id)` — kind first. `NewPrincipal(id, roles ...string)` — id first. Builders also offer `WithPolicyVersion`, `WithScope`, `WithAttrValue`.

### Batch

```go
cc := c.WithPrincipal(principal)

resources := cerbos.NewResourceBatch().
    Add(cerbos.NewResource("leave_request", "XX125"), "view:public", "defer").
    Add(cerbos.NewResource("leave_request", "XX225"), "approve")

result, err := cc.CheckResources(ctx, resources)
allowed := result.
    GetResource("XX125", cerbos.MatchResourcePolicyVersion("20210210")).
    IsAllowed("view:public")
```

`WithPrincipal` returns a context object carrying the principal, so the per-resource calls stop repeating it — the right shape for a request handler that checks several things for one user.

`cerbos.NewBatchingAdapter(c)` coalesces concurrent `CheckResources` calls into batched requests; useful behind a GraphQL resolver or dataloader.

The `Client` interface is small enough to fake in tests:

```go
IsAllowed(ctx context.Context, principal *Principal, resource *Resource, action string) (bool, error)
CheckResources(ctx context.Context, principal *Principal, resources *ResourceBatch) (*CheckResourcesResponse, error)
PlanResources(ctx context.Context, principal *Principal, resource *Resource, actions ...string) (*PlanResourcesResponse, error)
ServerInfo(ctx context.Context) (*ServerInfo, error)
With(opts ...RequestOpt) C
WithPrincipal(principal *Principal) P
```

There is no single-resource multi-action method: build a one-entry `ResourceBatch`.

## Query plan

```go
plan, err := c.PlanResources(ctx, principal, cerbos.NewResource("leave_request", ""), "approve")
```

`actions ...string` is variadic; more than one action needs PDP 0.44.0 or later. Branch on the filter kind before touching the condition — see [query-plan.md](query-plan.md).

Reference adapters for [Ent](https://github.com/cerbos/query-plan-adapters/tree/main/ent) and [pgx](https://github.com/cerbos/query-plan-adapters/tree/main/pgx) live in `cerbos/query-plan-adapters`, importable at `github.com/cerbos/query-plan-adapters/{ent,pgx}`. Both expose `Translate(plan, table, mapper, opts...)`. Neither has a tagged release, so you will pin a pseudo-version; read their READMEs first.

## Per-request options

`c.With(opts ...RequestOpt)` returns a client wrapper, so it is safe per request:

```go
c.With(cerbos.AuxDataJWT(token, "ks1")).IsAllowed(ctx, principal, resource, "view")
c.With(cerbos.AuxDataJWTs(map[string]cerbos.JWT{"app": {Token: tokenA}})).CheckResources(ctx, principal, batch)
```

Also available: `IncludeMeta(bool)`, `Headers(keyValues ...string)`, `RequestIDGenerator(func(ctx) string)` (wire in your trace ID), `AddAnnotations` / `SetAnnotations` (recorded in the PDP audit log), `AllowPartialRequests()`.

JWT semantics and the keyset rules are in [api-shapes.md](api-shapes.md).

## Testing

`github.com/cerbos/cerbos-sdk-go/testutil` starts a real PDP in a container (`3593/tcp` gRPC, `3592/tcp` HTTP) so integration tests run against the actual engine rather than a fake. Prefer it over mocking the client where the policy behaviour is what you are testing.

## Errors

`IsAllowed` returns `(false, err)` on transport failure. **Check `err` before the boolean** — a naked `if allowed` treats an unreachable PDP as a denial, which is safe, while ignoring the error hides the outage. Never invert it into an allow.

## AuthZEN

The repo also ships `cerbos-sdk-go/authzen` with `NewClient` (gRPC) and `NewHTTPClient(baseURL)` for the OpenID AuthZEN API. That is for interoperating with AuthZEN consumers, not for ordinary enforcement — use the `cerbos` package.
