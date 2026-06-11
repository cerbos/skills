# Cerbos Synapse WASM Proxy Extension (Go)

Load with: `shared/go-wasm-common.md`, `shared/patterns-and-gotchas.md` (build/run/test: `shared/run-and-test.md`).

Go WASM modules intercepting Cerbos `CheckResources` and `PlanResources` requests/responses passing through Cerbos Synapse.

## When to Use

- Principal enrichment requiring third-party Go libraries
- Complex attribute computation from external data sources
- Response transformation with compiled-code performance
- Audit logging, compliance integration, or side effects

## When NOT to Use

- Simple attribute injection -> use Starlark proxy extension
- Static request/response mapping -> use CEL call mapper
## Exported Functions

Export at least one (WASM export names are camelCase):

| Export | Purpose |
|--------|---------|
| `augmentCheckRequest` | Modify CheckResources request before PDP |
| `augmentCheckResponse` | Modify CheckResources response before returning |
| `augmentPlanRequest` | Modify PlanResources request before PDP |
| `augmentPlanResponse` | Modify PlanResources response before returning |
| `augmentAuthzenEvaluationRequest` | Modify AuthZEN AccessEvaluation request before PDP |
| `augmentAuthzenEvaluationResponse` | Modify AuthZEN AccessEvaluation response before returning |
| `augmentAuthzenEvaluationBatchRequest` | Modify AuthZEN AccessEvaluations (batch) request before PDP |
| `augmentAuthzenEvaluationBatchResponse` | Modify AuthZEN AccessEvaluations (batch) response before returning |
| `cerbosInit` | Called once on module load; optional lifecycle hook |
| `cerbosDeinit` | Called once on module unload; optional lifecycle hook |

Each reads JSON input, writes JSON output. Return `0` success, non-zero failure.

## CheckResources Request Format

`augmentCheckRequest` receives Cerbos CheckResources request as JSON:

```json
{
  "principal": { "id": "...", "roles": ["..."], "attr": {} },
  "resources": [{ "resource": { "kind": "...", "id": "...", "attr": {} }, "actions": ["..."] }],
  "auxData": { "jwt": { "token": "...", "keySetID": "..." } },
  "requestID": "..."
}
```

## Implementation

`tidwall/gjson` and `tidwall/sjson` for JSON manipulation.

```go
package main

import (
    "encoding/json"
    "fmt"

    "github.com/extism/go-pdk"
    "github.com/tidwall/gjson"
    "github.com/tidwall/sjson"
)

// Host import declarations (_cacheGet, _cacheSet, _cacheSetIfNotExists,
// _cacheDelete, _dataSourceLookup) and the cacheGetHelper / cacheSetHelper /
// cacheSetIfNotExistsHelper / cacheDeleteHelper / dataSourceLookupHelper
// wrappers come from shared/go-wasm-common.md.

var principals = map[string]map[string]string{
    "alice": {"department": "engineering", "role": "admin"},
    "bob":   {"department": "marketing", "role": "viewer"},
}

func enrichPrincipal(input []byte) ([]byte, error) {
    principalID := gjson.GetBytes(input, "principal.id").String()
    cacheKey := "proxy:attrs:" + principalID

    var attrs map[string]string
    if cached, ok := cacheGetHelper(cacheKey); ok {
        if err := json.Unmarshal(cached, &attrs); err == nil {
            return mergeAttrs(input, attrs)
        }
    }

    if dsAttrs, ok := dataSourceLookupHelper("userProfile", principalID); ok {
        attrs = make(map[string]string, len(dsAttrs))
        for k, v := range dsAttrs {
            attrs[k] = fmt.Sprintf("%v", v)
        }
    } else if hardcoded, ok := principals[principalID]; ok {
        attrs = hardcoded
    } else {
        attrs = map[string]string{"department": "unknown", "role": "guest"}
    }

    if data, err := json.Marshal(attrs); err == nil {
        cacheSetHelper(cacheKey, data, 60000)
    }
    return mergeAttrs(input, attrs)
}

func mergeAttrs(input []byte, attrs map[string]string) ([]byte, error) {
    modified := input
    var err error
    for k, v := range attrs {
        modified, err = sjson.SetBytes(modified, "principal.attr."+k, v)
        if err != nil {
            return nil, err
        }
    }
    return modified, nil
}

//go:wasmexport cerbosInit
func cerbosInit() int32 {
    cacheSetIfNotExistsHelper("proxy:initialized", []byte("active"), 0)
    return 0
}

//go:wasmexport cerbosDeinit
func cerbosDeinit() int32 {
    cacheDeleteHelper("proxy:initialized")
    return 0
}

//go:wasmexport augmentCheckRequest
func augmentCheckRequest() int32 {
    input := pdk.Input()
    modified, err := enrichPrincipal(input)
    if err != nil {
        pdk.SetError(err)
        return 1
    }
    pdk.Output(modified)
    return 0
}

//go:wasmexport augmentCheckResponse
func augmentCheckResponse() int32 {
    pdk.Output(pdk.Input())
    return 0
}

//go:wasmexport augmentPlanRequest
func augmentPlanRequest() int32 {
    input := pdk.Input()
    modified, err := enrichPrincipal(input)
    if err != nil {
        pdk.SetError(err)
        return 1
    }
    pdk.Output(modified)
    return 0
}

//go:wasmexport augmentPlanResponse
func augmentPlanResponse() int32 {
    pdk.Output(pdk.Input())
    return 0
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
        extensionURL: /extensions/datasource.star
  proxyExtensions:
    principalEnricher:
      extensionURL: /extensions/proxy.wasm
```
