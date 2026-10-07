# Cerbos Synapse WASM Data Source (Go)

Load with: `shared/go-wasm-common.md`, `shared/patterns-and-gotchas.md` (build/run/test: `shared/run-and-test.md`).

Go WASM modules implementing custom data source lookups; provide attribute data to other Cerbos Synapse extensions.

## When to Use

- Data source requiring third-party Go libraries (database drivers, SDK clients)
- Complex query processing or data transformation
- Integration with systems requiring compiled-code SDKs
- High-throughput lookups needing compiled performance

## When NOT to Use

- Simple HTTP API lookups -> use Starlark data source
- SQL database queries -> use built-in sqldb data source
## Exported Functions

| Export | Purpose |
|--------|---------|
| `lookup` | Handle data source lookup request, return result |
| `cerbosInit` | Optional. Runs once per pooled instance, so several times per module; set up per-instance state |
| `cerbosDeinit` | Optional. Runs on every instance at graceful shutdown; release per-instance resources |

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

Only `dataSource` and `query` required. `query`: any valid JSON value.

## Lookup Response Format

```json
{
    "result": { "department": "engineering", "role": "senior" }
}
```

`result`: any valid JSON value.

## Implementation

```go
package main

import (
    "encoding/json"

    "github.com/extism/go-pdk"
)

// Host import declarations (_cacheGet, _cacheSetIfNotExists) and the
// cacheGetHelper / cacheSetIfNotExistsHelper / outputJSON wrappers come from
// shared/go-wasm-common.md.

type LookupRequest struct {
    DataSource string          `json:"dataSource"`
    Query      json.RawMessage `json:"query"`
}

type LookupResponse struct {
    Result json.RawMessage `json:"result"`
}

var profiles = map[string]map[string]string{
    "alice": {"department": "engineering", "role": "admin", "clearance": "top-secret"},
    "bob":   {"department": "marketing", "role": "viewer", "clearance": "public"},
}

// Per-instance state, set by cerbosInit in every pooled instance.
var defaultClearance string
var hasDefault bool

//go:wasmexport cerbosInit
func cerbosInit() int32 {
    defaultClearance, hasDefault = pdk.GetConfig("defaultClearance")
    return 0
}

// Release per-instance resources (connections, handles) here.
//go:wasmexport cerbosDeinit
func cerbosDeinit() int32 {
    return 0
}

//go:wasmexport lookup
func lookup() int32 {
    var req LookupRequest
    if err := pdk.InputJSON(&req); err != nil {
        pdk.SetError(err)
        return 1
    }

    var query string
    if err := json.Unmarshal(req.Query, &query); err != nil {
        pdk.SetError(err)
        return 1
    }

    cacheKey := "profile:" + query
    if cached, ok := cacheGetHelper(cacheKey); ok {
        return outputJSON(LookupResponse{Result: cached})
    }

    profile, ok := profiles[query]
    if !ok {
        if !hasDefault {
            return outputJSON(LookupResponse{Result: json.RawMessage("null")})
        }
        profile = map[string]string{
            "department": "unknown",
            "role":       "user",
            "clearance":  defaultClearance,
        }
    }

    resultBytes, err := json.Marshal(profile)
    if err != nil {
        pdk.SetError(err)
        return 1
    }

    cacheSetIfNotExistsHelper(cacheKey, resultBytes, 300_000)
    return outputJSON(LookupResponse{Result: resultBytes})
}

func main() {}
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
            result = json.decode(json.encode(response.result))
            for k in result:
                req.principal.attr[k] = result[k]   # per-key writes keep caller-sent attributes
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
