# The embedded client

Wiring `@cerbos/embedded-client` beyond the minimal `new Embedded({ policies: { ruleId }, wasm })`. API reference: [`@cerbos/embedded-client`](https://cerbos.github.io/cerbos-sdk-javascript/modules/_cerbos_embedded-client.html).

`@cerbos/embedded-client` 0.8.1 needs Node 22+ and is ESM-only, though Node 22.15+ and 24+ can `require` it. `@cerbos/embedded-server` is a peer dependency, so both go in `package.json`.

An older package, `@cerbos/embedded`, takes a bundle URL instead of a rule ID. New work uses `@cerbos/embedded-client` with a rule ID.

## Where the policies come from

`policies` accepts three shapes:

| Value | Use |
|---|---|
| `{ ruleId, ... }` | The common case — the client builds a `PolicyLoader` and polls Hub. |
| a `PolicyLoader` instance | When activation timing matters, or several clients share one bundle. |
| bundle bytes, or a promise of them | The backend-for-frontend pattern: a server downloads the bundle with its credentials and hands the bytes to a browser client, which never polls Hub. |

## Credentials

With the rule set to **Client credential**, pass a client ID and secret:

```typescript
const cerbos = new Embedded({
  policies: {
    ruleId: "<RULE_ID>",
    credentials: {
      clientId: process.env.CERBOS_HUB_CLIENT_ID,
      clientSecret: process.env.CERBOS_HUB_CLIENT_SECRET,
    },
  },
  wasm,
});
```

`credentialsFromEnv()` reads those two variables for you, but it is exported by `@cerbos/hub` — a third package that the two-package install does not put in `package.json`. Add it explicitly rather than importing through a transitive dependency:

```typescript
import { credentialsFromEnv } from "@cerbos/hub";

const cerbos = new Embedded({
  policies: { ruleId: "<RULE_ID>", credentials: credentialsFromEnv() },
  wasm,
});
```

Credentials belong in server-side runtimes only; the browser patterns are in [RULES.md](RULES.md).

## Bundle updates

The loader polls Hub and swaps the bundle in place — no restart, no redeploy. Updates are conditional on the bundle already held, so an unchanged bundle costs one small request.

| Option | Default | Behaviour |
|---|---|---|
| `interval` | `60` (seconds) | Values below 10 are raised to 10. `0` disables polling, pinning the client to the bundle it loaded at construction. |
| `onUpdate` | no-op | Called after each update attempt with a `NotOK` error, or `undefined` on success. |
| `activateOnLoad` | `true` | `false` downloads updates without using them until `activate()` is called. |

Update failures are otherwise silent and the client keeps serving the bundle it has, so `onUpdate` is the only place a stale-policy incident becomes visible. Log from it.

Deferring activation keeps a decision stable mid-interaction — applying updates on route change instead of mid-render, or behind a "refresh permissions" control:

```typescript
import { Embedded, PolicyLoader } from "@cerbos/embedded-client";

const loader = new PolicyLoader({
  ruleId: "<RULE_ID>",
  activateOnLoad: false,
  onUpdate: (error) => {
    if (!error) console.info("New policy bundle ready");
  },
});

const cerbos = new Embedded({ policies: loader, wasm });

loader.activate(); // later, when the moment is right
```

`loader.stop()` ends polling — on shutdown, or when the page holding the client goes away.

Short-lived runtimes never reach the second poll: a serverless invocation downloads the current bundle on cold start and that is the snapshot it evaluates.

## Engine options

Set on the `Embedded` constructor beside `policies` and `wasm`, and fixed for the life of the client. Full list: [`Options`](https://cerbos.github.io/cerbos-sdk-javascript/interfaces/_cerbos_embedded-client.Options.html).

| Option | Default | Effect |
|---|---|---|
| `defaultPolicyVersion` | `"default"` | [Policy version](https://docs.cerbos.dev/cerbos/latest/configuration/engine.md?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=skill&utm_content=cerbos-embedded-pdp) for requests that name none; a request can override it. |
| `defaultScope` | `""` | Scope for requests that name none; a request can override it. |
| `globals` | `{}` | Values exposed to policy conditions — feature flags, region, environment. |
| `lenientScopeSearch` | `false` | On, a missing exact scope falls back through its ancestors. Off, the exact scope must exist. |
| `schemaEnforcement` | `NONE` | `NONE` skips input schema validation, `WARN` reports errors in the response, `REJECT` denies on a validation failure. See [schema enforcement](https://docs.cerbos.dev/cerbos/latest/configuration/schema.md?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=skill&utm_content=cerbos-embedded-pdp). |
| `onDecision` | no-op | Receives a decision log entry per check — request, response, metadata. The local substitute for Hub audit logging. |
| `decodeJWTPayload` | throws | Verifies and decodes JWTs passed as [auxiliary data](https://docs.cerbos.dev/cerbos/latest/configuration/auxdata.md?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=skill&utm_content=cerbos-embedded-pdp). Policies that read JWT claims need it supplied, typically via `jose`. |

## Errors

Checks resolve; a denial is a result. What throws is the bundle: the failure surfaces on construction or on the first check that waits for it.

```typescript
import { NotOK, Status } from "@cerbos/core";

try {
  await cerbos.isAllowed({ /* ... */ });
} catch (error) {
  if (error instanceof NotOK) {
    // error.code
  }
}
```

| `Status` | Cause |
|---|---|
| `UNAUTHENTICATED` | Credentials required but missing or invalid |
| `PERMISSION_DENIED` | Caller's IP outside the rule's allowlist |
| `NOT_FOUND` | No such rule ID |
| `FAILED_PRECONDITION` | The rule is disabled |
| `INVALID_ARGUMENT` | The rule requires scopes at fetch time and none were given |

## React

`@cerbos/react` wraps any Cerbos client, embedded or HTTP. `CerbosProvider` takes the client and the principal — give signed-out users an arbitrary id and an `anonymous` role rather than skipping the provider — and the hooks re-render when a bundle update activates.

```tsx
import { Embedded } from "@cerbos/embedded-client";
import { CerbosProvider, useIsAllowed } from "@cerbos/react";

const client = new Embedded({ policies: { ruleId: "<RULE_ID>" }, wasm });

<CerbosProvider client={client} principal={{ id: user.id, roles: user.roles }}>
  {children}
</CerbosProvider>;

function DeleteButton() {
  const check = useIsAllowed({
    resource: { kind: "document", id: "1", attr: { owner: user.email } },
    action: "delete",
  });

  if (check.isLoading || check.error || !check.data) return null;
  return <button>Delete</button>;
}
```

`useCheckResource` and `useCheckResources` return the same `{ isLoading, error, data }` shape for multi-action and multi-resource checks; `useCerbos` hands back the client itself for anything else, including `planResources`, which has no hook.

## What the WASM runtime does not do

- **Audit logging to Hub or an external sink.** `onDecision` gives you the entries locally; shipping them is yours.
- **The Admin API.** No administrative endpoints exist in the embedded runtime.
- **Runtime reconfiguration.** `globals`, `schemaEnforcement` and the rest are settled at construction.

Platform support covers browsers, Node.js, edge runtimes and React Native. Native iOS and Android SDKs are planned; Go, Python and the other server-side languages use a [service PDP](https://docs.cerbos.dev/cerbos-hub/decision-points.md?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=skill&utm_content=cerbos-embedded-pdp).

One `Embedded` client is safe under concurrent checks. Several clients built on one `PolicyLoader` share the bundle, and an activation reaches all of them.

Bundle size grows with the number of resource kinds, actions and roles, the complexity of the CEL conditions, the number of scopes, and the schemas. Watch it as policies grow in a browser application, and trim it with [rule filtering](RULES.md).
