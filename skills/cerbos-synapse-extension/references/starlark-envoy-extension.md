
# Cerbos Synapse Starlark Envoy Extension

`.star` scripts handling Envoy external authorization (ext_authz) requests — translate them into Cerbos authorization calls. No compilation.

Load with: `shared/starlark-environment.md` (host functions, modules, extension URL format, proto gotchas), `shared/patterns-and-gotchas.md` (run/test: `shared/run-and-test.md`).

## When to Use

- Simple Envoy ext_authz with straightforward request parsing
- Rapid prototyping of service mesh authorization
- Envoy integration without Go expertise
- Path-based routing with conditional authorization

## When NOT to Use

- Complex JWT decoding requiring third-party libraries → use WASM envoy extension
- Performance-critical service mesh paths → use WASM envoy extension
- Simple header/JWT extraction → use CEL call mapper

## Exported Functions

| Export | Purpose |
|--------|---------|
| `envoy_check` | Handle Envoy CheckRequest, return authorization result |
| `map_cerbos_response` | Map Cerbos response to Envoy CheckResponse (Cerbos request mode only) |

## Envoy CheckRequest Fields

Fields on `req`:

| Path | Description |
|------|-------------|
| `req.attributes.request.http.method` | HTTP method |
| `req.attributes.request.http.path` | HTTP path |
| `req.attributes.request.http.headers` | Headers map |
| `req.attributes.source.principal` | Source SPIFFE ID (Istio) |
| `req.attributes.destination.principal` | Destination SPIFFE ID (Istio) |

## Envoy Status Codes

- `0` = OK
- `7` = PERMISSION_DENIED

## Return Modes

### Direct Response

Return complete Envoy CheckResponse:

```python
struct(envoy_check_response = struct(
    status = struct(code = 7),
    denied_response = struct(body = "Access denied")
))
```

### Cerbos Mapping

```python
struct(cerbos_mapping = struct(
    check_request = struct(
        principal = struct(id = "user-1", roles = ["user"]),
        resources = [struct(
            resource = struct(id = "request", kind = "http_request", attr = {"path": "/api"}),
            actions = ["GET"]
        )]
    ),
    allow_response = struct(
        status = struct(code = 0),
        ok_response = struct(headers_to_remove = ["internal-header"])
    ),
    deny_response = struct(
        status = struct(code = 7),
        denied_response = struct(body = "Access denied")
    )
))
```

### Cerbos Request (with callback)

```python
struct(cerbos_check_request = struct(
    principal = struct(id = "user-1", roles = ["user"]),
    resources = [struct(
        resource = struct(id = "request", kind = "http_request"),
        actions = ["GET"]
    )]
))
```

Synapse calls PDP, then invokes `map_cerbos_response` with:

```python
struct(
    envoy_request = struct( ... ),
    cerbos_request = struct( ... ),
    cerbos_response = struct( ... )
)
```

Must return Envoy CheckResponse struct.

## Implementation

```python
def envoy_check(req):
    http_req = req.attributes.request.http
    path = http_req.path

    if path in context.extension_config["secure_paths"]:
        return struct(cerbos_mapping = struct(
            check_request = struct(
                principal = struct(id = "user", roles = ["user"]),
                resources = [struct(
                    resource = struct(id = "x", kind = "request", attr = {"path": path}),
                    actions = [http_req.method]
                )]
            ),
            allow_response = struct(
                status = struct(code = 0),
                ok_response = struct(headers_to_remove = ["internal-header"])
            ),
            deny_response = struct(
                status = struct(code = 7),
                denied_response = struct(body = "Access denied")
            )
        ))

    return struct(envoy_check_response = struct(
        status = struct(code = 0)
    ))
```

### With Cerbos Response Callback

```python
def envoy_check(req):
    http_req = req.attributes.request.http
    return struct(cerbos_check_request = struct(
        principal = struct(id = "user", roles = ["user"]),
        resources = [struct(
            resource = struct(id = "x", kind = "request", attr = {"path": http_req.path}),
            actions = [http_req.method]
        )]
    ))

def map_cerbos_response(resp):
    return struct(
        status = struct(code = 0),
        ok_response = struct(headers_to_remove = ["internal-header"])
    )
```

## Configuration

```yaml
extensions:
  envoyExternalAuthz:
    enabled: true
    extension:
      extensionURL: /extensions/envoy.star
      configuration:
        secure_paths: ["/api/v1", "/admin"]
```
