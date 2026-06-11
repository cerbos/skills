
# Cerbos Synapse WASM Data Source (Python)

Python WASM modules implementing custom data source lookups; provide attribute data to other Cerbos Synapse extensions.

Load with: `shared/python-wasm-common.md` (module behaviors, host functions, memory/cache helpers, PDK shim, build pipeline), `shared/patterns-and-gotchas.md`. To run/test: `shared/run-and-test.md`.

## When to Use

- Data source requiring pure-Python libraries
- JSON-heavy query processing or data transformation
- Rapid prototyping of data source logic
- Integration with systems having Python SDK clients

## When NOT to Use

- Simple HTTP API lookups -> use Starlark data source
- SQL database queries -> use built-in sqldb data source
- Packages requiring native C extensions -> use WASM Go or TypeScript
## Exported Functions

| Export | Purpose |
|--------|---------|
| `lookup` | Handle data source lookup request, return result |
| `cerbosInit` | Called once on module load; optional lifecycle hook |
| `cerbosDeinit` | Called once on module unload; optional lifecycle hook |

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

Only `dataSource` and `query` required. `query`: any valid JSON value (string, object, etc.). When `query` is a JSON-encoded string (double-quoted), strip the outer quotes.

## Lookup Response Format

```json
{
    "result": { "department": "engineering", "role": "senior" }
}
```

`result`: any valid JSON value.

## Implementation

Kind-specific logic only; host function import declarations (`cacheGet`, `cacheSetIfNotExists`, `cacheDelete`), memory helpers, and cache helpers (`cache_get`, `cache_set_if_not_exists`, `cache_delete`) are verbatim from `shared/python-wasm-common.md`.

```python
import json
import extism

# Import declarations + memory/cache helpers: shared/python-wasm-common.md

CACHE_TTL_MS = 300000

PROFILES = {
    "alice": {"department": "engineering", "role": "admin", "clearance": "top-secret"},
    "bob": {"department": "marketing", "role": "viewer", "clearance": "public"},
}

def strip_json_quotes(s):
    if isinstance(s, str) and s.startswith('"') and s.endswith('"'):
        return json.loads(s)
    return s

@extism.plugin_fn
def cerbosInit():
    cache_set_if_not_exists("datasource:initialized", b"true", CACHE_TTL_MS)

@extism.plugin_fn
def cerbosDeinit():
    cache_delete("datasource:initialized")

@extism.plugin_fn
def lookup():
    req = json.loads(extism.input_str())
    query = strip_json_quotes(req.get("query", ""))

    cache_key = "profile:" + str(query)
    cached = cache_get(cache_key)
    if cached:
        extism.output_str(json.dumps({"result": json.loads(cached.decode())}))
        return

    profile = PROFILES.get(query)
    if profile is None:
        default_clearance = extism.config_str("defaultClearance")
        if not default_clearance:
            extism.output_str(json.dumps({"result": None}))
            return
        profile = {"department": "unknown", "role": "user", "clearance": default_clearance}

    cache_set_if_not_exists(cache_key, json.dumps(profile).encode(), CACHE_TTL_MS)
    extism.output_str(json.dumps({"result": profile}))
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

Called from proxy extensions via `cerbos.data_source_lookup()`. Starlark enricher example:

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
