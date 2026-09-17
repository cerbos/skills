# JavaScript / TypeScript PEP

Source of truth: [`cerbos/cerbos-sdk-javascript`](https://github.com/cerbos/cerbos-sdk-javascript). All packages are ESM-only and require Node.js >= 20 (`require`-able from CommonJS on Node 20.19.5+, 22.15+, 24+).

## Choosing the package

| Package | Transport | Use it |
|---|---|---|
| `@cerbos/grpc` | gRPC, port 3593 | Server-side Node.js. The default choice for enforcement. |
| `@cerbos/http` | REST, port 3592 | Browsers, edge runtimes, and anywhere `fetch` is the only transport. Requires a global `fetch`. |
| `@cerbos/embedded-client` + `@cerbos/embedded-server` | none — WASM, in-process | Browser and edge permission checks with no network hop. Hub feature; see the `cerbos-embedded-pdp` skill ([Embedded PDPs](https://docs.cerbos.dev/cerbos-hub/deployments-epdp-rules?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=skill&utm_content=cerbos-pep-integration)). |
| `@cerbos/react` | wraps a client | React hooks over any of the above. |
| `@cerbos/opentelemetry` | — | Traces for `@cerbos/grpc` and `@cerbos/http`. |
| `@cerbos/core` | — | Shared types (`PlanKind`, `Effect`, `PlanExpression`, …). A dependency of the others; import types from it. |

`@cerbos/hub` and `@cerbos/files` are policy-authoring tools, not PEP packages.

## Connecting

```typescript
import { GRPC } from "@cerbos/grpc";

const cerbos = new GRPC("localhost:3593", { tls: false });
```

`options` is required for `GRPC` because `tls` is: `false` for plaintext, `true` to verify against the well-known root CAs, or a `SecureContext` from `tls.createSecureContext()` for custom CAs or mutual TLS. `target` also accepts `"unix:/var/run/cerbos.grpc.sock"`, which is the lowest-latency option for a sidecar. `cerbos.close()` releases the channel.

```typescript
import { HTTP } from "@cerbos/http";

const cerbos = new HTTP("http://localhost:3592");
```

Options shared by both (`@cerbos/core`): `headers` (static or a function returning headers per request — the hook for propagating a trace header), `onValidationError` (`"throw"`, a callback, or leave unset to read `validationErrors` off the response), `userAgent`, `playgroundInstance` (the hosted demo PDP, for prototyping only), `adminCredentials`.

There is no timeout or deadline option. Cancel a request with `RequestOptions.signal`, the second argument to every method:

```typescript
await cerbos.isAllowed(request, { signal: AbortSignal.timeout(500) });
```

## The four calls

```typescript
// One action, one resource — a guard clause.
const allowed: boolean = await cerbos.isAllowed({
  principal: { id: "user@example.com", roles: ["USER"], attr: { tier: "PREMIUM" } },
  resource: { kind: "document", id: "1", attr: { owner: "user@example.com" } },
  action: "view",
});

// Several actions on one resource — one round trip, e.g. to build a permissions map.
const decision = await cerbos.checkResource({
  principal,
  resource: { kind: "document", id: "1", attr: { owner: "user@example.com" } },
  actions: ["view", "edit", "delete"],
});
decision.isAllowed("view");    // boolean | undefined
decision.allowedActions();     // string[]
decision.allAllowed();         // boolean

// Several resources you already hold.
const decisions = await cerbos.checkResources({
  principal,
  resources: [
    { resource: { kind: "document", id: "1" }, actions: ["view", "edit"] },
    { resource: { kind: "image", id: "1" }, actions: ["delete"] },
  ],
});
decisions.isAllowed({ resource: { kind: "document", id: "1" }, action: "view" });
decisions.findResult({ kind: "document", id: "1" });  // CheckResourcesResult | undefined

// Filtering a list — see query-plan.md.
const plan = await cerbos.planResources({
  principal,
  resource: { kind: "document" },   // no id: this is a ResourceQuery
  actions: ["view"],
});
```

Watch the asymmetry when reading decisions: on a `CheckResourcesResponse` the selector is an object (`{ resource, action }`); on a single `CheckResourcesResult` it is a bare action string (`isAllowed("view")`). `checkResource` returns the result, `checkResources` returns the response.

Every accessor on the response returns `undefined` when the resource is not in the results — treat `undefined` as a denial, never as an allow. `kind` and `id` identify a result; add `policyVersion` and `scope` when one batch mixes them.

`isAllowed` and `checkResource` are implemented on top of `checkResources`, so they cost the same round trip. Pick whichever expresses the intent.

Request-level extras on all four: `auxData`, `includeMetadata` (note the SDK spells it in full, unlike the wire field `includeMeta`), `requestId` (defaults to a random UUID — set it to your trace ID).

## Principal and resource

```typescript
interface Principal {
  id: string;                  // required
  roles: string[];             // required, at least one
  attr?: Record<string, Value>;
  policyVersion?: string;
  scope?: string;
}

interface Resource {
  kind: string;                // required
  id: string;                  // required
  attr?: Record<string, Value>;
  policyVersion?: string;
  scope?: string;
}
```

Use `attr`. The `attributes` alias is deprecated (and if both are set, `attr` wins). Older examples in the wild — including some Cerbos tutorials — still show `attributes`; prefer `attr` for consistency with the `R.attr` / `P.attr` you write in policies.

Anonymous users still need a role. Define one (`"anonymous"`, `"guest"`) and send it rather than omitting `roles`, which fails request validation.

When one request handler makes several checks for the same user, pin the principal:

```typescript
const user = cerbos.withPrincipal(principal, { jwt: { token } });
await user.isAllowed({ resource, action: "view" });
```

## JWT auxiliary data

```typescript
await cerbos.isAllowed({
  principal,
  resource,
  action: "view",
  auxData: { jwt: { token: rawJwt, keySetId: "ks1" } },
});
```

`keySetId` is optional only while the PDP has one keyset configured. Omit `auxData` entirely when there is no token — the SDK drops the field rather than sending an empty one. Semantics and PDP-side verification: [api-shapes.md](api-shapes.md).

The embedded client has no server to verify against, so it needs a `decodeJWTPayload` option (its docs show a `jose` implementation) before it will accept a JWT at all.

## Query plans

```typescript
import { PlanKind } from "@cerbos/core";

switch (plan.kind) {
  case PlanKind.ALWAYS_ALLOWED: // run the query unfiltered
  case PlanKind.ALWAYS_DENIED:  // return [] without querying
  case PlanKind.CONDITIONAL:    // plan.condition is the AST root
}
```

`PlanResourcesResponse` is a discriminated union on `kind`, so `condition` exists only on the conditional branch; `planResourcesResponseIsConditional(plan)` is the exported type guard. The AST nodes are classes — `PlanExpression` (`operator`, `operands`), `PlanExpressionValue` (`value`), `PlanExpressionVariable` (`name`) — so `instanceof` narrows them.

`actions: string[]` needs PDP v0.44+; the singular `action: string` is deprecated but still accepted, and still appears in adapter examples.

Set `includeMetadata: true` and read `metadata.conditionString` to see the condition as readable CEL while you build a mapper.

Adapters: `@cerbos/orm-prisma`, `@cerbos/orm-drizzle`, `@cerbos/orm-mongoose`, `@cerbos/orm-convex`, `@cerbos/langchain-chromadb`. See [query-plan.md](query-plan.md).

## Errors

- `NotOK` — the PDP returned an error status. Carries `code` and `details`.
- `ValidationFailed` — thrown when `onValidationError: "throw"` is set and attribute schema enforcement rejected the request. Without that option the errors come back on the response as `validationErrors` instead.
