# Cerbos Synapse WASM Route Extension (Go)

Load with: `shared/go-wasm-common.md`, `shared/patterns-and-gotchas.md` (build/run/test: `shared/run-and-test.md`).

Go WASM modules handling custom HTTP endpoints on Cerbos Synapse; translate arbitrary requests into Cerbos authorization calls.

## When to Use

- Custom protocol adapters requiring compiled code
- Complex request transformation with Go libraries
- Infrastructure authorization endpoints (Kafka, custom gateways)
- Response formatting requiring compiled-code performance

## When NOT to Use

- Simple HTTP-to-Cerbos mapping -> use CEL call mapper
- Straightforward request translation -> use Starlark route extension
## Exported Functions

| Export | Purpose |
|--------|---------|
| `handleHTTPRoute` | Handle incoming HTTP request, return authorization result |
| `handleCerbosResponse` | Map Cerbos response to HTTP response (Cerbos request mode only) |
| `cerbosInit` | Called once on module load; optional lifecycle hook |
| `cerbosDeinit` | Called once on module unload; optional lifecycle hook |

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

Return only `checkRequest` in a `cerbosMapping`. Cerbos Synapse calls PDP, then invokes `handleCerbosResponse` with:

```json
{
    "httpRequest": { ... },
    "cerbosRequest": { ... },
    "cerbosResponse": { ... }
}
```

`handleCerbosResponse` must return an HTTP response JSON.

## Implementation

`tidwall/gjson` for JSON path queries.

**IMPORTANT**: Decode the base64-encoded body with `base64.StdEncoding.DecodeString()`.

```go
package main

import (
    "encoding/base64"

    "github.com/extism/go-pdk"
    "github.com/tidwall/gjson"
)

// Host import declarations (_checkResources, _cacheGet, _dataSourceLookup, ...)
// and the outputJSON helper come from shared/go-wasm-common.md — declare only
// the imports this module uses.

type HeaderValues struct {
    Values []string `json:"values"`
}

type HTTPResponse struct {
    Status  int                     `json:"status"`
    Headers map[string]HeaderValues `json:"headers,omitempty"`
    Body    []byte                  `json:"body,omitempty"`
}

type Principal struct {
    ID    string   `json:"id"`
    Roles []string `json:"roles"`
}

type Resource struct {
    ID   string `json:"id"`
    Kind string `json:"kind"`
}

type ResourceEntry struct {
    Resource Resource `json:"resource"`
    Actions  []string `json:"actions"`
}

type CheckRequest struct {
    Principal Principal       `json:"principal"`
    Resources []ResourceEntry `json:"resources"`
}

type CerbosMapping struct {
    CheckRequest  CheckRequest `json:"checkRequest"`
    AllowResponse HTTPResponse `json:"allowResponse"`
    DenyResponse  HTTPResponse `json:"denyResponse"`
}

type Result struct {
    HTTPResponse  *HTTPResponse  `json:"httpResponse,omitempty"`
    CerbosMapping *CerbosMapping `json:"cerbosMapping,omitempty"`
}

type HTTPRequest struct {
    Method string `json:"method"`
    Path   string `json:"path"`
    Body   string `json:"body"`
}

//go:wasmexport cerbosInit
func cerbosInit() int32 { return 0 }

//go:wasmexport cerbosDeinit
func cerbosDeinit() int32 { return 0 }

//go:wasmexport handleCerbosResponse
func handleCerbosResponse() int32 {
    pdk.Output(pdk.Input())
    return 0
}

//go:wasmexport handleHTTPRoute
func handleHTTPRoute() int32 {
    var httpReq HTTPRequest
    if err := pdk.InputJSON(&httpReq); err != nil {
        pdk.SetError(err)
        return 1
    }

    switch httpReq.Path {
    case "/ext/health":
        return handleHealth()
    case "/ext/check":
        return handleCheck(httpReq)
    default:
        return outputJSON(Result{
            HTTPResponse: &HTTPResponse{
                Status: 404,
                Body:   []byte("not found"),
            },
        })
    }
}

func handleHealth() int32 {
    return outputJSON(Result{
        HTTPResponse: &HTTPResponse{
            Status: 200,
            Headers: map[string]HeaderValues{
                "content-type": {Values: []string{"application/json"}},
            },
            Body: []byte(`{"status":"ok"}`),
        },
    })
}

func handleCheck(httpReq HTTPRequest) int32 {
    bodyBytes, err := base64.StdEncoding.DecodeString(httpReq.Body)
    if err != nil {
        pdk.SetError(err)
        return 1
    }

    body := string(bodyBytes)
    userID := gjson.Get(body, "userId").String()
    resourceKind := gjson.Get(body, "resourceKind").String()
    resourceID := gjson.Get(body, "resourceId").String()
    action := gjson.Get(body, "action").String()

    var roles []string
    rolesResult := gjson.Get(body, "roles")
    if rolesResult.Exists() {
        for _, r := range rolesResult.Array() {
            roles = append(roles, r.String())
        }
    } else {
        roles = []string{"user"}
    }

    return outputJSON(Result{
        CerbosMapping: &CerbosMapping{
            CheckRequest: CheckRequest{
                Principal: Principal{
                    ID:    userID,
                    Roles: roles,
                },
                Resources: []ResourceEntry{{
                    Resource: Resource{
                        ID:   resourceID,
                        Kind: resourceKind,
                    },
                    Actions: []string{action},
                }},
            },
            AllowResponse: HTTPResponse{
                Status: 200,
                Headers: map[string]HeaderValues{
                    "content-type": {Values: []string{"application/json"}},
                },
                Body: []byte(`{"result":"allowed"}`),
            },
            DenyResponse: HTTPResponse{
                Status: 403,
                Headers: map[string]HeaderValues{
                    "content-type": {Values: []string{"application/json"}},
                },
                Body: []byte(`{"result":"denied"}`),
            },
        },
    })
}

func main() {}
```

## Configuration

Routes served under `/ext/` prefix.

```yaml
extensions:
  dataDir: /tmp/data
  cacheDir: /tmp/cache
  routeExtensions:
    testRoute:
      extension:
        extensionURL: /extensions/route.wasm
      routes:
        "/health": ["GET"]
        "/check": ["POST"]
```
