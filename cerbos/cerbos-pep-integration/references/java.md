# Java PEP

Source of truth: [`cerbos/cerbos-sdk-java`](https://github.com/cerbos/cerbos-sdk-java). gRPC only — there is no HTTP client and no async client; everything is blocking.

## Install

```kotlin
dependencies {
    implementation("dev.cerbos:cerbos-sdk-java:0.+") // pin an actual release to avoid surprise updates
    implementation("io.grpc:grpc-core:1.+")          // must match the version the SDK was built against
}
```

The effective protobuf and gRPC versions in your project must match the ones the SDK requires; check the `build.gradle.kts` of the release you pin. When that clash is unavoidable, use the shaded jar, which relocates `com.google.protobuf` and `io.grpc` under `dev.cerbos.shaded`.

`CerbosContainer` (Testcontainers) ships in the same artifact — no separate test dependency. It starts `ghcr.io/cerbos/cerbos`, waits for the gRPC server log line, and exposes `getTarget()` for the builder.

## Connecting

```java
CerbosBlockingClient client = new CerbosClientBuilder("localhost:3593")
    .withPlaintext()
    .buildBlockingClient();
```

Builder: `withPlaintext()`, `withInsecure()`, `withAuthority(String)`, `withCaCertificate(InputStream)`, `withTlsCertificate(InputStream)`, `withTlsKey(InputStream)`, `withTimeout(Duration)`, `withPlaygroundInstance(String)`, `withClientInterceptors(List<ClientInterceptor>)`. All terminal methods throw the checked `CerbosClientBuilder.InvalidClientConfigurationException`.

Two things to get right:

- **TLS is the default.** `withPlaintext()` turns it off. `withInsecure()` is a different thing: it keeps TLS but skips certificate verification.
- **The default timeout is 1000 ms**, applied as a gRPC deadline. Raise it with `withTimeout(Duration)` if your PDP is a network hop away under load; a `DEADLINE_EXCEEDED` here surfaces as a `CerbosException`, not a denial.

Unix domain sockets work on Linux only — a `grpc-java` limitation.

Build the client once and share it; it holds a channel.

## Checking

```java
import static dev.cerbos.sdk.builders.AttributeValue.stringValue;

CheckResult result = client.check(
    Principal.newInstance("john", "employee")
        .withAttribute("department", stringValue("marketing")),
    Resource.newInstance("leave_request", "xx125")
        .withAttribute("owner", stringValue("john")),
    "view:public", "approve");

if (result.isAllowed("approve")) { … }
```

There is no `isAllowed` on the client: check once, then read the action off the `CheckResult`. `isAllowed(String)` returns `false` for an action that was not in the request, matching the PDP's deny-by-default.

`CheckResult` also gives you `getAll()`, `hasValidationErrors()` / `getValidationErrors()`, `getMeta()` (`getEffectiveDerivedRoles()`, `getInfoForAction(...)`), `getOutputs()` (`asMap()`), `getCerbosCallId()` and `getRaw()`.

### Batch

```java
CheckResourcesResult result = client.batch(principal)
    .addResources(
        ResourceAction.newInstance("leave_request", "XX125")
            .withAttributes(Map.of("owner", stringValue("john")))
            .withActions("view:public", "approve"))
    .check();

boolean canView = result.find("XX125").map(r -> r.isAllowed("view:public")).orElse(false);
```

`CheckResourcesRequestBuilder` also has `addResourceAndActions(Resource, String...)`, `withRequestId(String)`, `withAuxData(AuxData)` and `withIncludeMeta()`. Read results with `find(String resourceID)`, `find(String, Predicate<…Resource>)` when one batch mixes policy versions or scopes, or `results()` for the stream.

## Principal and resource

```java
Principal.newInstance(String id, String... roles)
    .withPolicyVersion(String).withRoles(String...)
    .withAttribute(String, AttributeValue).withAttributes(Map<String, AttributeValue>)
    .withScope(String)

Resource.newInstance(String kind, String id)   // or newInstance(kind) — id defaults to "_NEW_"
    .withPolicyVersion(String)
    .withAttribute(String, AttributeValue).withAttributes(Map<String, AttributeValue>)
    .withScope(String)
```

Attribute values come from `AttributeValue` factories, normally statically imported: `stringValue`, `doubleValue`, `boolValue`, `listValue`, `mapValue`, `nullValue`.

`Resource.newInstance(kind)` with its `"_NEW_"` default id is for create-style checks, where no instance exists yet. Anywhere else, pass the real id.

## Query plan

```java
PlanResourcesResult result = client.plan(
    Principal.newInstance("maggie", "manager"),
    Resource.newInstance("leave_request"),
    List.of("approve"));

if (result.isAlwaysAllowed()) {
    return findAll();
} else if (result.isAlwaysDenied()) {
    return List.of();
} else {
    return executeQuery(result.getCondition().get());
}
```

`plan(Principal, Resource, Iterable<String>)` needs Cerbos PDP 0.44.0 or later. The single-`String` overload is deprecated but still works, and the README example still uses it.

**`getCondition()` is never `Optional.empty()`** — on an unconditional plan it hands back the protobuf default instance. Branch on `isAlwaysAllowed()` / `isAlwaysDenied()` / `isConditional()`, never on the `Optional`.

Walk the AST through `Engine.PlanResourcesFilter.Expression.Operand`: `getExpression()` gives `getOperator()` and `getOperands(i)`, and each operand is a `oneof` of `value`, `expression` or `variable`. See [query-plan.md](query-plan.md).

There is no published Java query plan adapter on Maven Central. A Spring Data JPA adapter that turns a plan into a `Specification`, and an Elasticsearch adapter, exist in [`cerbos/query-plan-adapters`](https://github.com/cerbos/query-plan-adapters) but are unreleased — vendor them in knowingly, or walk the AST yourself.

## JWT auxiliary data

```java
client.with(AuxData.withJWT(token))
      .check(principal, resource, "view");

client.with(AuxData.withJWTs(Map.of(
        "app_token", AuxData.JWT.from(tokenA),
        "gateway_token", AuxData.JWT.from(tokenB))))
      .check(principal, resource, "view");
```

`with(AuxData)` returns a new client wrapper rather than mutating the shared one, so it is safe to call per request. `AuxData.withJWT(token, keySetId)` names the keyset, which is mandatory once the PDP has more than one configured. The batch builder takes the same object through `batch(principal, auxData)` or `withAuxData(...)`. Semantics in [api-shapes.md](api-shapes.md).

## Per-request context

- `withHeaders(Map<String, String>)` / `withHeaders(Metadata)` — propagate trace or tenant headers.
- `withRequestAnnotations(Map<String, AttributeValue>)` — values captured in the PDP's audit log alongside the decision. Pass `null` to clear.

Both return a new client wrapper.

## Errors

Every RPC failure throws `dev.cerbos.sdk.CerbosException`, wrapping the underlying `StatusRuntimeException`. Catch it where you can map it to a 5xx; a PDP that is unreachable or past its deadline is an outage, not a denial, and must never fall through to "allowed".
