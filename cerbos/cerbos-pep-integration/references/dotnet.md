# .NET PEP

Source of truth: [`cerbos/cerbos-sdk-net`](https://github.com/cerbos/cerbos-sdk-net). NuGet package `Cerbos.Sdk`, gRPC, targeting `netstandard2.0`, `netstandard2.1` and `net8.0`.

## Install

```bash
dotnet add package Cerbos.Sdk
```

## Connecting

```csharp
using Cerbos.Sdk.Builder;

var client = CerbosClientBuilder.ForTarget("http://localhost:3593").WithPlaintext().Build();
```

The target needs a **scheme** — `GrpcChannel.ForAddress` is underneath, so `http://host:3593` or `https://host:3593`, not a bare `host:3593`.

`WithPlaintext()` takes no argument. TLS is the default. `WithCaCertificate`, `WithTlsCertificate` and `WithTlsKey` all take a `StreamReader`, not a path or a string. Also `WithMetadata(Metadata)`, `WithPlaygroundInstance(string)` and `WithGrpcChannelOptions(GrpcChannelOptions)`. `Build()` throws when TLS certificates and plaintext are both configured, or playground and plaintext.

Register the client as a singleton in DI; it wraps a channel.

## Checking

```csharp
var request = CheckResourcesRequest.NewInstance()
    .WithRequestId(RequestId.Generate())
    .WithPrincipal(
        Principal.NewInstance("john", "employee")
            .WithAttribute("department", AttributeValue.StringValue("marketing"))
    )
    .WithResourceEntries(
        ResourceEntry.NewInstance("leave_request", "XX125")
            .WithAttribute("owner", AttributeValue.StringValue("john"))
            .WithActions("approve", "view:public")
    );

var result = (await client.CheckResourcesAsync(request)).Find("XX125");
if (result.IsAllowed("approve")) { … }
```

The client surface is sync/async pairs:

```csharp
CheckResourcesResponse CheckResources(CheckResourcesRequest request, Metadata headers = null);
Task<CheckResourcesResponse> CheckResourcesAsync(CheckResourcesRequest request, Metadata headers = null);
PlanResourcesResponse PlanResources(PlanResourcesRequest request, Metadata headers = null);
Task<PlanResourcesResponse> PlanResourcesAsync(PlanResourcesRequest request, Metadata headers = null);
HealthCheckResponse CheckHealth(HealthCheckRequest request, Metadata headers = null);
```

**There is no `IsAllowed` on the client and no single-resource method.** Everything goes through `CheckResources`, then `CheckResourcesResponse.Find(string id)` returns a `ResultEntry` whose `IsAllowed(string action)` gives the decision. `ResultEntry` also exposes `Actions`, `Resource`, `Meta`, `Outputs`, `ValidationErrors`, `Output(string src)` and `OutputByAction(string action)`.

Use the `Async` variants in ASP.NET Core request handlers — the synchronous ones block a thread-pool thread on a network call.

Builders: `Principal.NewInstance(string id, params string[] roles)` plus `WithRoles`, `WithAttribute`, `WithAttributes(Dictionary<string, AttributeValue>)`, `WithPolicyVersion`, `WithScope`. `ResourceEntry.NewInstance(string kind, string id)` or `ResourceEntry.NewInstance(Resource resource, params string[] actions)`. `CheckResourcesRequest` also has `WithIncludeMeta`, `WithAuxData`, `WithAllowPartialRequests`, `WithRequestContext`.

Attribute values are `AttributeValue.StringValue(...)` and siblings, never bare .NET values.

## Query plan

```csharp
var request = PlanResourcesRequest.NewInstance()
    .WithRequestId(RequestId.Generate())
    .WithPrincipal(principal)
    .WithResource(Resource.NewInstance("leave_request"))
    .WithActions("approve");

var result = await client.PlanResourcesAsync(request);

if (result.IsAlwaysAllowed())      { /* no filter */ }
else if (result.IsAlwaysDenied())  { /* empty result */ }
else                               { ApplyFilter(result); }
```

`WithActions(params string[])` needs Cerbos PDP v0.44.0 or later; `WithAction(string)` is the single-action form. `PlanResourcesRequest` also takes `WithAuxData`, `WithIncludeMeta` and `WithRequestContext`.

There is no .NET query plan adapter. Walk the filter AST yourself — node shapes in [api-shapes.md](api-shapes.md), rules for doing it safely in [query-plan.md](query-plan.md). An expression translator that emits a LINQ `Expression<Func<T, bool>>` is the idiomatic target, since EF Core can then push it into SQL.

## JWT auxiliary data

```csharp
request.WithAuxData(AuxData.WithJwt(token, "ks1"));
request.WithAuxData(AuxData.WithJwts(new Dictionary<string, AuxData.Types.JWT> { … }));
```

Available on both `CheckResourcesRequest` and `PlanResourcesRequest`. `AuxData.Types.JWT.NewInstance(token, keySetId)` and `FromToken(token)` build the entries. Semantics in [api-shapes.md](api-shapes.md).

## ASP.NET Core

There is no Cerbos authorization handler in the package. The idiomatic wiring is an `IAuthorizationHandler` over a resource-based requirement, resolving the singleton client and calling `CheckResourcesAsync`, so `AuthorizeAsync(user, resource, policy)` reaches Cerbos through the framework's own pipeline. Keep the `ClaimsPrincipal` → `Principal` mapping in one place.
