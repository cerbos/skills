# Cerbos Synapse WASM Envoy Extension (Go)

Load with: `shared/go-wasm-common.md`, `shared/patterns-and-gotchas.md` (build/run/test: `shared/run-and-test.md`).

Go WASM modules handling Envoy external authorization (ext_authz) requests; translate into Cerbos authorization calls.

## When to Use

- Envoy ext_authz with complex request parsing requiring compiled code
- JWT decoding or token validation with Go libraries
- Custom header manipulation beyond CEL capabilities
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

JSON input fields to `envoyCheck`:

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

`tidwall/gjson` for JSON path queries. Host functions (cache, data source, PDP) available as in `shared/go-wasm-common.md` if needed; this example uses none.

```go
package main

import (
    "github.com/extism/go-pdk"
    "github.com/tidwall/gjson"
)

type Status struct {
    Code int32 `json:"code"`
}

type EnvoyCheckResponse struct {
    Status         Status         `json:"status"`
    DeniedResponse map[string]any `json:"deniedResponse,omitempty"`
    OKResponse     map[string]any `json:"okResponse,omitempty"`
}

type Principal struct {
    ID    string         `json:"id"`
    Roles []string       `json:"roles"`
    Attr  map[string]any `json:"attr,omitempty"`
}

type Resource struct {
    ID   string         `json:"id"`
    Kind string         `json:"kind"`
    Attr map[string]any `json:"attr,omitempty"`
}

type ResourceEntry struct {
    Resource Resource `json:"resource"`
    Actions  []string `json:"actions"`
}

type CheckRequest struct {
    Principal Principal       `json:"principal"`
    Resources []ResourceEntry `json:"resources"`
}

type EnvoyCerbosMapping struct {
    CheckRequest  CheckRequest       `json:"checkRequest"`
    AllowResponse EnvoyCheckResponse `json:"allowResponse"`
    DenyResponse  EnvoyCheckResponse `json:"denyResponse"`
}

type Result struct {
    EnvoyCheckResponse *EnvoyCheckResponse `json:"envoyCheckResponse,omitempty"`
    EnvoyCerbosMapping *EnvoyCerbosMapping `json:"cerbosMapping,omitempty"`
    CheckRequest       *CheckRequest       `json:"cerbosCheckRequest,omitempty"`
}

//go:wasmexport envoyCheck
func envoyCheck() int32 {
    inputBytes := pdk.Input()
    values := gjson.GetManyBytes(inputBytes,
        "attributes.request.http.method",
        "attributes.request.http.path",
    )
    method := values[0].String()
    path := values[1].String()

    result := Result{
        EnvoyCerbosMapping: &EnvoyCerbosMapping{
            CheckRequest: CheckRequest{
                Principal: Principal{ID: "user-1", Roles: []string{"user"}},
                Resources: []ResourceEntry{{
                    Resource: Resource{
                        ID: "request", Kind: "http_request",
                        Attr: map[string]any{"path": path},
                    },
                    Actions: []string{method},
                }},
            },
            AllowResponse: EnvoyCheckResponse{
                Status:     Status{Code: 0},
                OKResponse: map[string]any{"headersToRemove": []string{"internal-header"}},
            },
            DenyResponse: EnvoyCheckResponse{
                Status:         Status{Code: 7},
                DeniedResponse: map[string]any{"body": "Access denied"},
            },
        },
    }

    if err := pdk.OutputJSON(result); err != nil {
        pdk.SetError(err)
        return 1
    }
    return 0
}

//go:wasmexport envoyMapCerbosResponse
func envoyMapCerbosResponse() int32 {
    output := EnvoyCheckResponse{
        Status:     Status{Code: 0},
        OKResponse: map[string]any{"headersToRemove": []string{"internal-header"}},
    }
    if err := pdk.OutputJSON(output); err != nil {
        pdk.SetError(err)
        return 1
    }
    return 0
}

func main() {}
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
