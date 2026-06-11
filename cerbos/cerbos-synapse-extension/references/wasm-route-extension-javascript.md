# Cerbos Synapse WASM Route Extension (TypeScript)

Load with: `shared/typescript-wasm-common.md`, `shared/patterns-and-gotchas.md` (build/run/test: `shared/run-and-test.md`).

TypeScript WASM modules handling custom HTTP endpoints on Cerbos Synapse; translate arbitrary requests into Cerbos authorization calls.

## When to Use

- Custom protocol adapters using npm packages
- JSON-heavy request transformation
- Rapid prototyping of route extensions
- Response formatting requiring compiled performance

## When NOT to Use

- Simple HTTP-to-Cerbos mapping -> use CEL call mapper
- Straightforward request translation -> use Starlark route extension

## Exported Functions

| Export | Purpose |
|--------|---------|
| `cerbosInit` | Called once when the extension is loaded |
| `cerbosDeinit` | Called once when the extension is unloaded |
| `handleHTTPRoute` | Handle incoming HTTP request, return authorization result |
| `handleCerbosResponse` | Map Cerbos response to HTTP response (Cerbos request mode only) |

## HTTP Request Format

`handleHTTPRoute` receives JSON:

```json
{
    "method": "POST",
    "headers": {
        "X-Forwarded-For": { "values": ["127.0.0.1:2090"] }
    },
    "rawUrl": "https://example.com/ext/path/to/foo?a=av",
    "host": "example.com",
    "path": "/ext/path/to/foo",
    "queryParams": {
        "a": { "values": ["av"] }
    },
    "body": "aGVsbG8K"
}
```

**Body is base64-encoded** (unlike Starlark which receives raw bytes).

**Note**: `path` includes the `/ext/` prefix. Route mapped to `/health` receives `path = "/ext/health"`.

## Return Modes

### Direct Response

```json
{
    "httpResponse": {
        "status": 200,
        "headers": { "content-type": { "values": ["application/json"] } },
        "body": "eyJvayI6IHRydWV9"
    }
}
```

### Cerbos Mapping

```json
{
    "cerbosMapping": {
        "checkRequest": {
            "principal": { "id": "user-1", "roles": ["user"], "attr": {} },
            "resources": [{
                "actions": ["GET"],
                "resource": { "id": "doc-1", "kind": "document", "attr": { "path": "/foo" } }
            }]
        },
        "allowResponse": { "status": 200, "body": "V2VsY29tZQ==" },
        "denyResponse": { "status": 403, "body": "RGVuaWVk" }
    }
}
```

### Cerbos Request (with callback)

Return only `checkRequest` in a `cerbosMapping`. Cerbos Synapse calls PDP, then invokes `handleCerbosResponse`:

```json
{
    "httpRequest": { ... },
    "cerbosRequest": { ... },
    "cerbosResponse": { ... }
}
```

`handleCerbosResponse` must return an HTTP response JSON.

## Implementation

### src/index.d.ts

```ts
/// <reference types="@extism/js-pdk" />
declare module "main" {
  export function cerbosInit(): void;
  export function cerbosDeinit(): void;
  export function handleHTTPRoute(): void;
  export function handleCerbosResponse(): void;
}

// Plus the `extism:host` declaration from shared/typescript-wasm-common.md
// (this module uses checkResources, planResources, cacheGet, cacheSet,
// cacheSetIfNotExists, cacheDelete, dataSourceLookup).
```

### src/index.ts

```ts
// Copy from shared/typescript-wasm-common.md:
// - encodeBase64 / decodeBase64 (Runtime Limitations)
// - cacheGet / cacheSet / cacheSetIfNotExists / cacheDelete,
//   checkResources / planResources / dataSourceLookup (Host Function Wrappers)

export function cerbosInit() {}
export function cerbosDeinit() {}

interface HTTPRequest {
  method: string;
  path: string;
  headers: Record<string, { values: string[] }>;
  body?: string;
}

interface CheckBody {
  userId: string;
  roles?: string[];
  resourceKind: string;
  resourceId: string;
  action: string;
}

function httpResponse(status: number, body: unknown): void {
  Host.outputString(JSON.stringify({
    httpResponse: {
      status,
      headers: { "content-type": { values: ["application/json"] } },
      body: encodeBase64(JSON.stringify(body)),
    },
  }));
}

export function handleHTTPRoute() {
  const req: HTTPRequest = JSON.parse(Host.inputString());

  if (req.path === "/ext/health") {
    httpResponse(200, { status: "ok" });
    return;
  }

  if (req.path === "/ext/check") {
    const body: CheckBody = JSON.parse(decodeBase64(req.body ?? ""));
    Host.outputString(JSON.stringify({
      cerbosMapping: {
        checkRequest: {
          principal: { id: body.userId, roles: body.roles ?? ["user"] },
          resources: [{
            resource: { id: body.resourceId, kind: body.resourceKind },
            actions: [body.action],
          }],
        },
        allowResponse: { status: 200, body: encodeBase64(JSON.stringify({ allowed: true })) },
        denyResponse: { status: 403, body: encodeBase64(JSON.stringify({ allowed: false })) },
      },
    }));
    return;
  }

  if (req.path === "/ext/cache-test") {
    const results: Record<string, unknown> = {};

    const setResult = cacheSet("test-key", "test-value", 60000);
    results.cacheSet = { status: setResult === 0 ? "ok" : "error" };

    const getValue = cacheGet("test-key");
    results.cacheGet = { status: getValue === "test-value" ? "ok" : "error", value: getValue };

    const setIfNotExistsResult = cacheSetIfNotExists("test-key", "other-value", 60000);
    results.cacheSetIfNotExists = { status: setIfNotExistsResult === 0 ? "ok" : "error" };

    const getAfterSetIfNotExists = cacheGet("test-key");
    results.cacheSetIfNotExistsVerify = {
      status: getAfterSetIfNotExists === "test-value" ? "ok" : "error",
      value: getAfterSetIfNotExists,
    };

    const deleteResult = cacheDelete("test-key");
    results.cacheDelete = { status: deleteResult === 0 ? "ok" : "error" };

    const getAfterDelete = cacheGet("test-key");
    results.cacheDeleteVerify = { status: getAfterDelete === null ? "ok" : "error", value: getAfterDelete };

    httpResponse(200, results);
    return;
  }

  if (req.path === "/ext/check-direct") {
    const body = decodeBase64(req.body ?? "");
    const result = checkResources(body);
    httpResponse(200, JSON.parse(result));
    return;
  }

  if (req.path === "/ext/plan") {
    const body = decodeBase64(req.body ?? "");
    const result = planResources(body);
    httpResponse(200, JSON.parse(result));
    return;
  }

  if (req.path === "/ext/lookup") {
    const body = decodeBase64(req.body ?? "");
    const result = dataSourceLookup(body);
    httpResponse(200, JSON.parse(result));
    return;
  }

  httpResponse(404, { error: "not found" });
}

export function handleCerbosResponse() {
  Host.outputString(Host.inputString());
}
```

## Configuration

Routes served under `/ext/` prefix.

```yaml
extensions:
  dataDir: /tmp/data
  cacheDir: /tmp/cache
  dataSources:
    testData:
      extension:
        extensionURL: /extensions/datasource.star
  routeExtensions:
    testRoute:
      extension:
        extensionURL: /extensions/route.wasm
      routes:
        "/health": ["GET"]
        "/check": ["POST"]
        "/cache-test": ["POST"]
        "/check-direct": ["POST"]
        "/plan": ["POST"]
        "/lookup": ["POST"]
```
