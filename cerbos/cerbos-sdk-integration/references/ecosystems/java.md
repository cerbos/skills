# Java integration recipe

**SDK packages**: `dev.cerbos:cerbos-sdk-java` ([Maven Central](https://central.sonatype.com/artifact/dev.cerbos/cerbos-sdk-java))
**Live sources — fetch these before writing any integration code:**
- SDK repo README: https://raw.githubusercontent.com/cerbos/cerbos-sdk-java/main/README.md (repo: https://github.com/cerbos/cerbos-sdk-java — Javadoc on classes, test classes as examples)
- Query-plan adapters: https://github.com/cerbos/query-plan-adapters (Java: `elasticsearch-java`, copy-in — see §5)
- Docs index: https://docs.cerbos.dev/llms.txt

Pointer-tier recipe: it names the verified API surface — fetch the live sources for the rest.

## 1. Client setup

Add `dev.cerbos:cerbos-sdk-java` from Maven Central. The SDK is **gRPC only** (grpc-java,
netty-shaded); `CerbosBlockingClient` is the only client — no HTTP transport, no async
variant (wrap calls in `CompletableFuture`). README gotcha: the effective protobuf/gRPC
versions in your dependency tree must match the SDK's — add exclusions or shading if an
older transitive version wins. One client per process, built at startup and injected —
never per request:

```java
CerbosBlockingClient client = new CerbosClientBuilder(System.getenv("CERBOS_ADDRESS")) // "localhost:3593"
        .withPlaintext()                          // local dev / same-host sidecar only
        .withTimeout(Duration.ofMillis(200))      // default is 1s; keep it short, fail closed
        .buildBlockingClient();                   // throws InvalidClientConfigurationException
```

For TLS, drop `withPlaintext()`; `withCaCertificate(InputStream)`, `withTlsCertificate` +
`withTlsKey` (mTLS), `withInsecure()` (never in production). Admin API: `buildBlockingAdminClient(...)`.

## 2. Principal construction

One canonical helper maps the app's auth context (Spring Security principal, verified JWT
claims, session) to a Cerbos principal. Builders live in `dev.cerbos.sdk.builders`;
attributes are wrapped with `AttributeValue` factories (`stringValue`, `boolValue`,
`doubleValue`, `listValue`, `mapValue`).

```java
// import static dev.cerbos.sdk.builders.AttributeValue.*;
public static Principal fromClaims(Jwt jwt) { // adapt claim names to your IdP
    return Principal.newInstance(jwt.getSubject(), rolesFrom(jwt).toArray(String[]::new))
            .withAttribute("email", stringValue(jwt.getClaimAsString("email")))
            .withAttribute("department", stringValue(jwt.getClaimAsString("department")));
}
```

Identity facts only (id, roles, org, department) — resource facts belong on the
`Resource`. If the app has a `User` type, adapt from that instead of raw claims.

## 3. Framework integration points

Placement per [ARCHITECTURE.md](../ARCHITECTURE.md): filters/interceptors only for coarse,
resource-independent gates; **resource-level checks live in the service layer** where the
entity is already loaded.

### Spring Boot

Expose the client as a bean; wrap checks in one `@Component` so callsites stay uniform:

```java
@Configuration
public class CerbosConfig {
    @Bean
    CerbosBlockingClient cerbos(@Value("${cerbos.address:localhost:3593}") String address)
            throws CerbosClientBuilder.InvalidClientConfigurationException {
        return new CerbosClientBuilder(address).withPlaintext()
                .withTimeout(Duration.ofMillis(200)).buildBlockingClient();
    }
}

@Component
public class Authorizer {
    private final CerbosBlockingClient cerbos; // constructor-injected

    public void require(Principal p, Resource r, String action) {
        try {
            if (!cerbos.check(p, r, action).isAllowed(action)) throw new AccessDeniedException(action);
        } catch (CerbosException e) {                 // unchecked; RPC/timeout errors
            throw new AccessDeniedException(action, e); // fail closed
        }
    }
}
```

Coarse gates (role/tenant from token claims only) go in a `OncePerRequestFilter` or
`HandlerInterceptor` after authentication; anything needing a DB-loaded attribute belongs
in the service method, after load and before mutation.

### Quarkus / Micronaut

Same placement rules. Produce the client as a CDI/DI singleton (`@Produces
@ApplicationScoped` in Quarkus, `@Singleton @Factory` in Micronaut), inject the same
service-layer wrapper, and put coarse gates in a `ContainerRequestFilter` / server filter.

## 4. Single-resource checks

`check(principal, resource, actions...)` returns a `CheckResult`; batch multiple actions
in the one call and read each with `isAllowed(action)` (or `getAll()` for a map — e.g. UI
capability flags). `CerbosException` (unchecked) signals RPC failure: catch and deny. Each
call has an overload taking a leading `requestId` string for correlation with your own IDs.

```java
Resource resource = Resource.newInstance("order", order.getId())
        .withAttribute("ownerId", stringValue(order.getOwnerId()))
        .withAttribute("status", stringValue(order.getStatus()));

CheckResult result = cerbos.check(principal, resource, "view", "update", "cancel");
boolean canView = result.isAllowed("view");
```

Multiple resources in one round trip (bulk operations — never a loop of single checks):
`cerbos.batch(principal).addResources(ResourceAction.newInstance(kind, id).withActions(...)).check()`,
then `result.find(id)` per resource.

## 5. List filtering

`plan(principal, resource, action)` (and an `Iterable<String>` actions overload) returns a
`PlanResourcesResult`. Handle all three outcomes explicitly:

```java
PlanResourcesResult plan = cerbos.plan(principal, Resource.newInstance("order"), "view");
if (plan.isAlwaysDenied()) return List.of();               // empty result, no query
if (plan.isAlwaysAllowed()) return repository.findAll();   // no extra WHERE clause
Engine.PlanResourcesFilter.Expression.Operand cond = plan.getCondition().orElseThrow();
return repository.findAll(toSpecification(cond));          // CONDITIONAL: translate the AST
```

Before hand-rolling, check https://github.com/cerbos/query-plan-adapters and the docs
index for a published Java adapter (Spring Data JPA support is an active area) — adapter
coverage evolves faster than this recipe. If none fits, hand-walk the plan AST into your
query layer (a JPA `Specification`/Criteria predicate, jOOQ `Condition`, or SQL `WHERE` +
bind params). The walk is mechanical: recurse on `Operand` — an `Expression` node has an
operator (`and`/`or`/`not` recurse over operands; `eq`, `ne`, `lt`, `le`, `gt`, `ge`,
`in`, … map to query operators), a `Variable` arrives as `request.resource.attr.<name>`
(strip the prefix, map through an explicit **allowlist** of entity fields), and a `Value`
is always a bind parameter — never inlined. Reject unknown fields and operators with an
error: that fails closed and surfaces policy drift (`plan.getRaw()` exposes the raw response).

For Elasticsearch, the public https://github.com/cerbos/query-plan-adapters repo contains
`elasticsearch-java`, translating a `PlanResourcesResult` into an Elasticsearch Query DSL
map — **copy-in code, not a published artifact**: copy its two source files per its README.

## 6. The authorization helper (real check + enforcement flag)

One helper, used at every callsite, that **always runs the real Cerbos check**; a
per-callsite mode flag decides whether a Cerbos deny blocks (`enforce`) or is only logged
while the legacy boolean stands (`shadow`). There is no separate shadow helper — shadow is
a value of the flag, so the callsite is identical in every mode and cutover is a config
change. Full contract in [ARCHITECTURE.md](../ARCHITECTURE.md) §4: in shadow the Cerbos
check runs on a short-timeout parallel call that never affects the response and mismatches
log one structured line (no attribute payloads); in enforce the Cerbos decision is returned,
failing closed. Greenfield integrations pin the mode to `enforce` and pass no legacy
boolean.

```java
// Always issues the real Cerbos check; the mode flag decides what to do with the result.
public boolean authorize(String endpoint, Principal p, Resource r, String action,
                     String principalId, String kind, String id, String requestId,
                     boolean legacy) {
    if (modes.isEnforce(endpoint)) { // per-callsite: authz.mode.<endpoint>=shadow|enforce
        try { return cerbos.check(p, r, action).isAllowed(action); }
        catch (CerbosException e) {
            log.error("cerbos_check_error endpoint={} requestId={}", endpoint, requestId, e);
            return false; // fail closed
        }
    }
    CompletableFuture.supplyAsync(() -> cerbos.check(p, r, action).isAllowed(action))
            .orTimeout(200, TimeUnit.MILLISECONDS)
            .whenComplete((cerbosAllowed, err) -> {
                if (err != null) {
                    log.warn("cerbos_shadow_error endpoint={} requestId={}", endpoint, requestId, err);
                } else if (cerbosAllowed != legacy) { // one structured line per disagreement
                    log.atWarn().addKeyValue("event", "cerbos_shadow_mismatch")
                            .addKeyValue("endpoint", endpoint).addKeyValue("principalId", principalId)
                            .addKeyValue("resourceKind", kind).addKeyValue("resourceId", id)
                            .addKeyValue("action", action).addKeyValue("legacy", legacy)
                            .addKeyValue("cerbos", cerbosAllowed).addKeyValue("requestId", requestId)
                            .log("cerbos_shadow_mismatch");
                }
            });
    return legacy; // legacy check stays exactly where it was
}
```

Use the slf4j 2.x fluent API with a JSON encoder (logback + logstash encoder or similar)
so mismatch lines are queryable. Cut over per endpoint once its mismatch rate is zero.

## 7. Testing

If the app already runs a PDP via docker-compose for local dev, reuse it in tests (point
the client at it) rather than adding a new dependency. Otherwise the SDK artifact itself
ships Testcontainers support: `dev.cerbos.sdk.CerbosContainer` extends `GenericContainer`,
runs `ghcr.io/cerbos/cerbos` (constructors take a version tag or `DockerImageName`) and
exposes `getTarget()` / `getGrpcPort()` / `getHttpPort()`. Add
`org.testcontainers:junit-jupiter` and run real checks against your actual policies:

```java
@Testcontainers
class OrderAuthorizationTest {
    @Container
    static final CerbosContainer cerbos = new CerbosContainer()
            .withClasspathResourceMapping("policies", "/policies", BindMode.READ_ONLY);

    @Test
    void ownerCanView() throws Exception {
        CerbosBlockingClient client = new CerbosClientBuilder(cerbos.getTarget())
                .withPlaintext().buildBlockingClient();
        assertTrue(client.check(
                Principal.newInstance("alice", "customer"),
                Resource.newInstance("order", "o1").withAttribute("ownerId", stringValue("alice")),
                "view").isAllowed("view"));
    }
}
```

Pure policy logic belongs in Cerbos's own YAML tests (`cerbos compile`); Java tests cover
the integration seams — principal mapping, resource attributes, plan translation, and
fail-closed paths — injecting the test client through the same bean the app uses.

Three rules that keep these tests honest:

- **Pin the policy source.** When policies live outside the app repo (a separate ops/policy
  repo), mount them from a pinned ref (git submodule, versioned artifact, or a CI checkout
  at a recorded SHA) — a floating clone makes test results irreproducible and green runs
  meaningless.
- **Seed fixtures from the policy test suite's `testdata/`.** The principals and resources
  the policy YAML tests use are the canonical scenario fixtures; build your JPA test
  entities from the same values instead of inventing a parallel set that silently drifts
  from what the policies were verified against.
- **Match the production database engine for plan-driven queries.** When a test exercises
  `PlanResources` translation (Specifications/Criteria/SQL), run the real engine via
  Testcontainers (e.g. PostgreSQL), not H2 — the generated predicates are exactly where
  dialect differences bite. H2 is fine for tests that never execute plan-compiled SQL.

## 8. Local dev PDP

`docker-compose.yaml`:

```yaml
services:
  cerbos:
    image: ghcr.io/cerbos/cerbos:latest
    command: ["server"]
    ports:
      - "3592:3592" # HTTP (curl / API explorer)
      - "3593:3593" # gRPC (the Java SDK)
    volumes:
      - ./policies:/policies
```

The container serves policies from `/policies` with watch enabled — edit a policy and the
PDP reloads it. Run the app with `CERBOS_ADDRESS=localhost:3593` (plaintext client, §1).
