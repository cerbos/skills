# Cerbos Synapse WASM Proxy Extension (TypeScript)

Load with: `shared/typescript-wasm-common.md`, `shared/patterns-and-gotchas.md` (build/run/test: `shared/run-and-test.md`).

TypeScript WASM modules intercepting Cerbos `CheckResources` and `PlanResources` requests/responses passing through Cerbos Synapse.

## When to Use

- Principal enrichment using npm packages
- JSON-heavy attribute computation
- Rapid prototyping of proxy logic
- Response transformation with compiled performance

## When NOT to Use

- Simple attribute injection -> use Starlark proxy extension
- Static request/response mapping -> use CEL call mapper

## Exported Functions

Export at least one (WASM export names are camelCase):

| Export | Purpose |
|--------|---------|
| `cerbosInit` | Called once when the extension is loaded |
| `cerbosDeinit` | Called once when the extension is unloaded |
| `augmentCheckRequest` | Modify CheckResources request before PDP |
| `augmentCheckResponse` | Modify CheckResources response before returning |
| `augmentPlanRequest` | Modify PlanResources request before PDP |
| `augmentPlanResponse` | Modify PlanResources response before returning |
| `augmentAuthzenEvaluationRequest` | Modify AuthZEN AccessEvaluation request before PDP |
| `augmentAuthzenEvaluationResponse` | Modify AuthZEN AccessEvaluation response before returning |
| `augmentAuthzenEvaluationBatchRequest` | Modify AuthZEN AccessEvaluations (batch) request before PDP |
| `augmentAuthzenEvaluationBatchResponse` | Modify AuthZEN AccessEvaluations (batch) response before returning |

Each function: read JSON via `Host.inputString()`, write (possibly modified) JSON via `Host.outputString()`. Throwing marks the extension failed.

## CheckResources Request Format

`augmentCheckRequest` input (CheckResources request as JSON):

```json
{
  "principal": { "id": "...", "roles": ["..."], "attr": {} },
  "resources": [{ "resource": { "kind": "...", "id": "...", "attr": {} }, "actions": ["..."] }],
  "auxData": { "jwt": { "token": "...", "keySetID": "..." } },
  "requestID": "..."
}
```

## Implementation

### src/index.d.ts

```ts
/// <reference types="@extism/js-pdk" />
declare module "main" {
  export function cerbosInit(): void;
  export function cerbosDeinit(): void;
  export function augmentCheckRequest(): void;
  export function augmentCheckResponse(): void;
  export function augmentPlanRequest(): void;
  export function augmentPlanResponse(): void;
}

// Plus the `extism:host` declaration from shared/typescript-wasm-common.md
// (this module uses cacheGet, cacheSet, cacheSetIfNotExists, cacheDelete,
// dataSourceLookup).
```

### src/index.ts

```ts
// cacheGet / cacheSet / cacheSetIfNotExists / cacheDelete / dataSourceLookup
// wrappers: copy from shared/typescript-wasm-common.md (Host Function Wrappers).

const principals: Record<string, Record<string, string>> = {
  alice: { department: "engineering", role: "admin" },
  bob: { department: "marketing", role: "viewer" },
};

const defaultAttrs: Record<string, string> = { department: "unknown", role: "guest" };

function lookupPrincipalAttrs(principalID: string): Record<string, unknown> | null {
  const resp = JSON.parse(
    dataSourceLookup(JSON.stringify({ dataSource: "userProfile", query: principalID })),
  );
  return resp.result ?? null;
}

export function cerbosInit() {
  cacheSetIfNotExists("proxy:initialized", "true", 300000);
}

export function cerbosDeinit() {
  cacheDelete("proxy:initialized");
}

export function augmentCheckRequest() {
  const req = JSON.parse(Host.inputString());
  const principalID: string = req.principal?.id ?? "";
  const cacheKey = "proxy:attrs:" + principalID;

  const cached = cacheGet(cacheKey);
  if (cached) {
    const attrs = JSON.parse(cached);
    req.principal.attr = { ...req.principal.attr, ...attrs };
    Host.outputString(JSON.stringify(req));
    return;
  }

  const dsResult = lookupPrincipalAttrs(principalID);
  const attrs = dsResult ?? (principals[principalID] ?? defaultAttrs);

  cacheSet(cacheKey, JSON.stringify(attrs), 300000);
  req.principal.attr = { ...req.principal.attr, ...attrs };
  Host.outputString(JSON.stringify(req));
}

export function augmentCheckResponse() {
  Host.outputString(Host.inputString());
}

export function augmentPlanRequest() {
  const req = JSON.parse(Host.inputString());
  const principalID: string = req.principal?.id ?? "";
  const cacheKey = "proxy:attrs:" + principalID;

  const cached = cacheGet(cacheKey);
  if (cached) {
    const attrs = JSON.parse(cached);
    req.principal.attr = { ...req.principal.attr, ...attrs };
    Host.outputString(JSON.stringify(req));
    return;
  }

  const dsResult = lookupPrincipalAttrs(principalID);
  const attrs = dsResult ?? (principals[principalID] ?? defaultAttrs);

  cacheSet(cacheKey, JSON.stringify(attrs), 300000);
  req.principal.attr = { ...req.principal.attr, ...attrs };
  Host.outputString(JSON.stringify(req));
}

export function augmentPlanResponse() {
  Host.outputString(Host.inputString());
}
```

## Configuration

```yaml
extensions:
  dataDir: /tmp/data
  cacheDir: /tmp/cache
  dataSources:
    userProfile:
      extension:
        extensionURL: /extensions/datasource.star
  proxyExtensions:
    principalEnricher:
      extensionURL: /extensions/proxy.wasm
```
