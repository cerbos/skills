# Cerbos Synapse WASM Data Source (TypeScript)

Load with: `shared/typescript-wasm-common.md`, `shared/patterns-and-gotchas.md` (build/run/test: `shared/run-and-test.md`).

TypeScript WASM modules implementing custom data source lookups; supply attribute data to other Cerbos Synapse extensions.

## When to Use

- Data source requiring npm packages
- JSON-heavy query processing or data transformation
- Rapid prototyping of data source integrations
- High-throughput lookups needing compiled performance

## When NOT to Use

- Simple HTTP API lookups -> use Starlark data source
- SQL database queries -> use built-in sqldb data source

## Exported Functions

| Export | Purpose |
|--------|---------|
| `cerbosInit` | Called once when the extension is loaded |
| `cerbosDeinit` | Called once when the extension is unloaded |
| `lookup` | Handle data source lookup request, return result |

## Lookup Request Format

`lookup` receives JSON:

```json
{
    "dataSource": "myDataSource",
    "query": "SELECT dept FROM employees WHERE id = :emp_id",
    "queryParameters": {
        "emp_id": "simon"
    },
    "cacheOptions": {
        "cacheKey": "simon",
        "cacheExpiry": "300s",
        "ifNotExists": true
    }
}
```

Only `dataSource` and `query` are required. `query` can be any valid JSON value.

## Lookup Response Format

```json
{
    "result": { "department": "engineering", "role": "senior" }
}
```

`result` can be any valid JSON value.

## Implementation

### src/index.d.ts

```ts
/// <reference types="@extism/js-pdk" />

declare module "main" {
  export function cerbosInit(): void;
  export function cerbosDeinit(): void;
  export function lookup(): void;
}

// Plus the `extism:host` declaration from shared/typescript-wasm-common.md —
// this module uses the cache functions only (cacheGet, cacheSet,
// cacheSetIfNotExists, cacheDelete).
```

### src/index.ts

```ts
// cacheGet / cacheSetIfNotExists / cacheDelete wrappers:
// copy from shared/typescript-wasm-common.md (Host Function Wrappers).

interface LookupRequest {
  dataSource: string;
  query: string;
}

interface UserProfile {
  department: string;
  role: string;
  clearance: string;
}

const profiles: Record<string, UserProfile> = {
  alice: { department: "engineering", role: "admin", clearance: "top-secret" },
  bob: { department: "marketing", role: "viewer", clearance: "public" },
};

export function cerbosInit() {
  cacheSetIfNotExists("datasource:initialized", "true", 300000);
}

export function cerbosDeinit() {
  cacheDelete("datasource:initialized");
}

export function lookup() {
  const req: LookupRequest = JSON.parse(Host.inputString());
  const cacheKey = "profile:" + req.query;

  const cached = cacheGet(cacheKey);
  if (cached) {
    Host.outputString(JSON.stringify({ result: JSON.parse(cached) }));
    return;
  }

  let profile: UserProfile | undefined = profiles[req.query];

  if (!profile) {
    const defaultClearance = Config.get("defaultClearance");
    if (!defaultClearance) {
      Host.outputString(JSON.stringify({ result: null }));
      return;
    }
    profile = { department: "unknown", role: "user", clearance: defaultClearance };
  }

  const profileJSON = JSON.stringify(profile);
  cacheSetIfNotExists(cacheKey, profileJSON, 300000);
  Host.outputString(JSON.stringify({ result: profile }));
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
        extensionURL: /extensions/datasource.wasm
        configuration:
          defaultClearance: restricted
```

## Consuming a Data Source

Called from proxy extensions via `cerbos.data_source_lookup()`. Example Starlark enricher:

```python
def augment_check_request(req):
    if req.principal.id != "":
        response = cerbos.data_source_lookup("userProfile", req.principal.id)
        if response != None and response.result != None:
            req.principal.attr = response.result
    return req
```

Wire both in config:

```yaml
extensions:
  dataDir: /tmp/data
  cacheDir: /tmp/cache
  dataSources:
    userProfile:
      extension:
        extensionURL: /extensions/datasource.wasm
        configuration:
          defaultClearance: restricted
  proxyExtensions:
    principalEnricher:
      extensionURL: /extensions/enricher.star
```
