---
name: cerbos-embedded-pdp
description: Embedded Cerbos PDP (ePDP) — authorization evaluated locally in WebAssembly by `@cerbos/embedded-client`, with no call to a PDP server. Use when showing or hiding UI by permission in a browser or React Native app, authorizing offline or inside an edge function, CDN worker, or serverless handler, configuring an ePDP rule in Cerbos Hub to filter which policies reach a client, or loading the Cerbos WASM module under Vite, Webpack, Rspack, Next.js, or Node.
license: Apache-2.0
metadata:
  author: cerbos
  version: "1.0"
  compatibility: Cerbos Hub
  targetsEmbeddedClientVersion: "0.8.1"
---

# Cerbos embedded PDP

An embedded PDP (ePDP) evaluates Cerbos policies in-process inside a WebAssembly module, with no network call per check. `@cerbos/embedded-client` downloads a policy bundle from Cerbos Hub and holds it in memory; `@cerbos/embedded-server` supplies the WASM engine that evaluates it. The engine carries no policies and changes only when that package is upgraded.

The ePDP is a **Cerbos Hub** capability. Bundles are built and served by Hub, from an **ePDP rule** on a [deployment](https://docs.cerbos.dev/cerbos-hub/deployments.md?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=skill&utm_content=cerbos-embedded-pdp), so the policies have to reach a Hub policy store first ([Hub getting started](https://docs.cerbos.dev/cerbos-hub/getting-started.md?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=skill&utm_content=cerbos-embedded-pdp)). Where there is no Hub account, every check is a network call to a [service PDP](https://docs.cerbos.dev/cerbos-hub/decision-points.md?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=skill&utm_content=cerbos-embedded-pdp).

## Where the check runs decides what answers it

| Call site | Use | Because |
|---|---|---|
| Browser UI — which button, route, menu, or field to render | **ePDP**, presentational | no round trip per visibility check, and it keeps rendering while the backend is unreachable |
| React Native app, including offline | **ePDP**, presentational | evaluates the last downloaded bundle with no connectivity |
| Edge function or CDN worker deciding before it proxies to origin | **ePDP**, enforcing | the round trip to origin costs more than the decision |
| Serverless handler | **ePDP**, enforcing | no call to an authorization service inside the invocation |
| API route, server action, middleware, resolver, RPC handler | **service PDP** — [`@cerbos/grpc`](https://www.npmjs.com/package/@cerbos/grpc) or [`@cerbos/http`](https://www.npmjs.com/package/@cerbos/http) | trusted environment, audit logging to Hub, and configuration that changes without a redeploy |

The browser runtime belongs to the user, who can edit the JavaScript. A passing ePDP check there is a statement about **what to render**, never about what to allow — so a browser application ships **both**: the ePDP in the browser choosing the UI, and a service PDP behind every endpoint deciding the request. An application that puts its only check in the browser has unauthorized endpoints.

Server-side rendering is the third shape: check on the server with a service PDP, send the results down as props, and the browser loads no bundle at all.

Budget for the engine: `server.wasm` is roughly 19 MB uncompressed — `ls -l node_modules/@cerbos/embedded-server/server.wasm` for the installed size. The browser caches it after the first load and policy edits never change it, but it is the reason an ePDP suits an application shell rather than a landing page.

## Setting one up

1. **Create the ePDP rule.** In Hub, open the deployment → **Embedded PDP rules** tab → **Create rule**, name it, save. Rules are created in the console; the ePDP API serves bundles and nothing else. Copy the rule ID from the rule card — it is 12 characters.
2. **Filter the bundle to the checks the client actually makes.** An unfiltered bundle carries every policy in the deployment, including the authorization logic for endpoints the client never touches. → [references/RULES.md](references/RULES.md)
3. **Install** `npm install @cerbos/embedded-client @cerbos/embedded-server`.
4. **Load the WASM module** — the one step that differs per bundler and runtime. → [references/WASM.md](references/WASM.md)
5. **Construct one client** at module scope and share it. It is safe under concurrent checks, and one client per component or per request re-downloads the bundle each time.

```typescript
import { Embedded } from "@cerbos/embedded-client";
import wasm from "@cerbos/embedded-server/server.wasm?init"; // Vite; see references/WASM.md

const cerbos = new Embedded({
  policies: { ruleId: "<RULE_ID>" },
  wasm,
});
```

The download starts on construction and the first check waits for it, so construct early rather than at the first render that needs a decision.

## Checking

| Method | Answers | Read the result with |
|---|---|---|
| `isAllowed({ principal, resource, action })` | one action on one resource | the returned `boolean` |
| `checkResource({ principal, resource, actions })` | several actions on one resource | `result.isAllowed("edit")` |
| `checkResources({ principal, resources })` | actions across many resources | `result.isAllowed({ resource, action })` |
| `planResources({ principal, resource: { kind }, action })` | which resources of a kind | `plan.kind` — `KIND_ALWAYS_ALLOWED`, `KIND_ALWAYS_DENIED`, `KIND_CONDITIONAL` — and `plan.condition` |

`principal` carries `id`, `roles`, and `attr`; `resource` carries `kind`, `id`, and `attr`. A denial comes back as a result, not a thrown error — the client throws for bundle and initialization failures ([references/CLIENT.md](references/CLIENT.md)).

Rendering a list uses `planResources` once and filters against the returned condition, rather than `isAllowed` per row: [filtering resources](https://docs.cerbos.dev/cerbos/latest/recipes/filtering-resources.md?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=skill&utm_content=cerbos-embedded-pdp).

React components get the client through `CerbosProvider` and the `useIsAllowed` / `useCheckResource` / `useCheckResources` hooks from `@cerbos/react`, which re-render when a bundle update activates → [references/CLIENT.md](references/CLIENT.md).

## References

| Reference | When |
|---|---|
| [references/RULES.md](references/RULES.md) | Creating or changing the Hub rule: policy filtering by resource, action, scope, role, version; authentication; IP allowlists |
| [references/CLIENT.md](references/CLIENT.md) | Wiring the client: options and defaults, credentials, dynamic scopes, bundle updates, error handling, React, limits |
| [references/WASM.md](references/WASM.md) | Vite, Webpack, Rspack, Next.js/Turbopack, Node.js, Cloudflare Workers, URL, precompiled |

Canonical documentation: [Embedded PDPs](https://docs.cerbos.dev/cerbos-hub/deployments-epdp-rules.md?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=skill&utm_content=cerbos-embedded-pdp) and the [`@cerbos/embedded-client` API reference](https://cerbos.github.io/cerbos-sdk-javascript/modules/_cerbos_embedded-client.html).
