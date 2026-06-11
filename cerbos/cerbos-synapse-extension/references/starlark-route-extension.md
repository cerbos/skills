
# Cerbos Synapse Starlark Route Extension

`.star` scripts handling custom HTTP endpoints on Cerbos Synapse — translate arbitrary requests into Cerbos authorization calls. No compilation.

Load with: `shared/starlark-environment.md` (host functions, modules, extension URL format, proto gotchas), `shared/patterns-and-gotchas.md` (run/test: `shared/run-and-test.md`).

## When to Use

- Simple protocol translation or API integration
- Rapid prototyping of custom authorization endpoints
- Route handling without Go expertise
- Straightforward request-to-Cerbos mapping

## When NOT to Use

- Complex protocol adapters requiring third-party libraries → use WASM route extension
- High-throughput endpoints needing compiled performance → use WASM route extension
- Simple HTTP-to-Cerbos mapping → use CEL call mapper

## Exported Functions

| Export | Purpose |
|--------|---------|
| `handle_http_route` | Handle incoming HTTP request, return authorization result |
| `handle_cerbos_response` | Map Cerbos response to HTTP response (Cerbos request mode only) |

## HTTP Request Object

`handle_http_route` receives:

```python
struct(
    method = "POST",
    headers = {
        "X-Forwarded-For": struct(values = ["127.0.0.1:2090"])
    },
    raw_url = "https://example.com/ext/path/to/foo?a=av",
    host = "example.com",
    path = "/ext/path/to/foo",
    query_params = {
        "a": struct(values = ["av"])
    },
    body = "Hello"
)
```

Body: raw bytes (not base64-encoded like WASM).

**Note**: `req.path` includes the `/ext/` prefix. Route mapped to `/health` receives `req.path = "/ext/health"`.

**Note**: `query_params` and `headers` are proto maps, not dicts — no `.get()`; use `"key" in req.query_params` and `req.query_params["key"].values[0]`. See `shared/starlark-environment.md`.

## Return Modes

### Direct Response

```python
struct(http_response = struct(
    status = 200,
    headers = { "content-type": struct(values = ["application/json"]) },
    body = '{"ok": true}'
))
```

### Cerbos Mapping

```python
struct(cerbos_mapping = struct(
    check_request = struct(
        principal = struct(id = "user-1", roles = ["user"]),
        resources = [struct(
            resource = struct(id = "doc-1", kind = "document", attr = {"path": req.path}),
            actions = [req.method]
        )]
    ),
    allow_response = struct(status = 200, body = "Welcome"),
    deny_response = struct(status = 403, body = "Access denied")
))
```

### Cerbos Request (with callback)

Return only the check request:

```python
struct(check_request = struct(
    principal = struct(id = "user-1", roles = ["user"]),
    resources = [struct(
        resource = struct(id = "doc-1", kind = "document"),
        actions = ["view"]
    )]
))
```

Synapse calls PDP, then invokes `handle_cerbos_response` with:

```python
struct(
    http_request = struct( ... ),
    cerbos_request = struct( ... ),
    cerbos_response = struct( ... )
)
```

Must return HTTP response struct.

## Implementation

```python
def handle_http_route(req):
    return struct(cerbos_mapping = struct(
        check_request = struct(
            principal = struct(id = "daffy", roles = ["user"]),
            resources = [struct(
                resource = struct(id = "x", kind = "request", attr = {"path": req.path}),
                actions = [req.method]
            )]
        ),
        allow_response = struct(
            status = 200,
            headers = {"content-type": struct(values = ["application/json"])},
            body = "Welcome"
        ),
        deny_response = struct(
            status = 403,
            headers = {"content-type": struct(values = ["application/json"])},
            body = "No entry"
        )
    ))
```

### With JSON Body Parsing and Multiple Routes

```python
load("json", "json")

def handle_http_route(req):
    if req.path == "/ext/health":
        return struct(http_response = struct(
            status = 200,
            headers = {"content-type": struct(values = ["application/json"])},
            body = '{"status":"ok"}'
        ))

    if req.path == "/ext/check":
        request = json.decode(str(req.body), {})
        user_id = request.get("userId", "anonymous")
        resource_kind = request.get("resourceKind", "unknown")
        resource_id = request.get("resourceId", "unknown")
        action = request.get("action", "view")
        roles = request.get("roles", ["user"])

        return struct(cerbos_mapping = struct(
            check_request = struct(
                principal = struct(id = user_id, roles = roles),
                resources = [struct(
                    resource = struct(id = resource_id, kind = resource_kind),
                    actions = [action]
                )]
            ),
            allow_response = struct(
                status = 200,
                headers = {"content-type": struct(values = ["application/json"])},
                body = '{"result":"allowed"}'
            ),
            deny_response = struct(
                status = 403,
                headers = {"content-type": struct(values = ["application/json"])},
                body = '{"result":"denied"}'
            )
        ))

    return struct(http_response = struct(status = 404, body = "not found"))
```

## Configuration

Routes are served under the `/ext/` prefix.

```yaml
extensions:
  dataDir: /tmp/data
  cacheDir: /tmp/cache
  routeExtensions:
    testRoute:
      extension:
        extensionURL: /extensions/route.star
      routes:
        "/health": ["GET"]
        "/check": ["POST"]
```
