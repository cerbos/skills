# Cerbos Synapse WASM Envoy Extension (TypeScript)

Load with: `shared/typescript-wasm-common.md`, `shared/patterns-and-gotchas.md` (build/run/test: `shared/run-and-test.md`).

TypeScript WASM modules handling Envoy external authorization (ext_authz) requests; translate them into Cerbos authorization calls.

## When to Use

- Envoy ext_authz with npm packages for request parsing
- JSON-heavy header manipulation
- Rapid prototyping of envoy authorization logic
- Multi-step authorization logic for service mesh

## When NOT to Use

- Simple header/JWT extraction -> use CEL call mapper
- Straightforward Envoy-to-Cerbos mapping -> use Starlark envoy extension

## Exported Functions

| Export | Purpose |
|--------|---------|
| `envoyCheck` | Handle Envoy CheckRequest, return authorization result |
| `envoyMapCerbosResponse` | Map Cerbos response to Envoy CheckResponse (Cerbos request mode only) |

## Envoy CheckRequest Fields

Fields in `envoyCheck` JSON input:

| JSON Path | Description |
|-----------|-------------|
| `attributes.request.http.method` | HTTP method |
| `attributes.request.http.path` | HTTP path |
| `attributes.request.http.headers` | Headers map |
| `attributes.source.principal` | Source SPIFFE ID (Istio) |
| `attributes.destination.principal` | Destination SPIFFE ID (Istio) |

## Envoy Status Codes

- `0` = OK
- `7` = PERMISSION_DENIED

## Return Modes

### Direct Response

Return a complete Envoy CheckResponse:

```json
{
    "envoyCheckResponse": {
        "status": { "code": 7 },
        "deniedResponse": { "body": "Access denied" }
    }
}
```

### Cerbos Mapping

```json
{
    "cerbosMapping": {
        "checkRequest": {
            "principal": { "id": "user-1", "roles": ["user"] },
            "resources": [{
                "actions": ["GET"],
                "resource": { "id": "request", "kind": "http_request", "attr": { "path": "/api" } }
            }]
        },
        "allowResponse": {
            "status": { "code": 0 },
            "okResponse": { "headersToRemove": ["internal-header"] }
        },
        "denyResponse": {
            "status": { "code": 7 },
            "deniedResponse": { "body": "Access denied" }
        }
    }
}
```

### Cerbos Request (with callback)

```json
{
    "cerbosCheckRequest": {
        "principal": { "id": "user-1", "roles": ["user"] },
        "resources": [{
            "actions": ["GET"],
            "resource": { "id": "request", "kind": "http_request" }
        }]
    }
}
```

Cerbos Synapse calls PDP, then invokes `envoyMapCerbosResponse` with:

```json
{
    "envoyRequest": { ... },
    "cerbosRequest": { ... },
    "cerbosResponse": { ... }
}
```

Must return an Envoy CheckResponse.

## Implementation

This example calls no host functions, so no `extism:host` declaration is needed; if you add caching or PDP/data source calls, copy the declaration and wrappers from `shared/typescript-wasm-common.md`.

### src/index.d.ts

```ts
/// <reference types="@extism/js-pdk" />
declare module "main" {
  export function cerbosInit(): void;
  export function cerbosDeinit(): void;
  export function envoyCheck(): void;
  export function envoyMapCerbosResponse(): void;
}
```

### src/index.ts

```ts
export function cerbosInit() {}
export function cerbosDeinit() {}

export function envoyCheck() {
  const req = JSON.parse(Host.inputString());
  const httpReq = req.attributes.request.http;

  const result = {
    cerbosMapping: {
      checkRequest: {
        principal: { id: "user-1", roles: ["user"] },
        resources: [{
          resource: { id: "request", kind: "http_request", attr: { path: httpReq.path } },
          actions: [httpReq.method]
        }]
      },
      allowResponse: { status: { code: 0 } },
      denyResponse: { status: { code: 7 }, deniedResponse: { body: "Access denied" } }
    }
  };
  Host.outputString(JSON.stringify(result));
}

export function envoyMapCerbosResponse() {
  Host.outputString(Host.inputString());
}
```

## Configuration

```yaml
extensions:
  envoyExternalAuthz:
    enabled: true
    extension:
      extensionURL: /extensions/envoy.wasm
      configuration:
        secure_paths: ["/api/v1", "/admin"]
```
