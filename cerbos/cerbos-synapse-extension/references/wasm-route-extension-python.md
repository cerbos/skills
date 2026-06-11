
# Cerbos Synapse WASM Route Extension (Python)

Python WASM modules handling custom HTTP endpoints on Cerbos Synapse; translate arbitrary requests into Cerbos authorization calls.

Load with: `shared/python-wasm-common.md` (module behaviors, host functions, memory/cache helpers, PDK shim, build pipeline), `shared/patterns-and-gotchas.md`. To run/test: `shared/run-and-test.md`.

## When to Use

- Custom protocol adapters using pure-Python libraries
- JSON-heavy request transformation
- Rapid prototyping of route logic
- Infrastructure authorization endpoints

## When NOT to Use

- Simple HTTP-to-Cerbos mapping -> use CEL call mapper
- Straightforward request translation -> use Starlark route extension
- Packages requiring native C extensions -> use WASM Go or TypeScript
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

**Body is base64-encoded**. Decode with `base64.b64decode()`.

**Note**: `path` includes the `/ext/` prefix. Route mapped to `/health` receives `path = "/ext/health"`.

## Return Modes

### Direct Response

Body must be base64-encoded (use `base64.b64encode(data).decode()`):

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
                "resource": { "id": "doc-1", "kind": "document", "attr": {} }
            }]
        },
        "allowResponse": { "status": 200, "body": "V2VsY29tZQ==" },
        "denyResponse": { "status": 403, "body": "RGVuaWVk" }
    }
}
```

## Implementation

**IMPORTANT**: All response `body` fields must be base64-encoded strings, not raw bytes. Helper: `base64.b64encode(data).decode()`.

This example needs no host functions. To call `checkResources` directly or use the cache, add the import declarations and memory/cache helpers from `shared/python-wasm-common.md`.

```python
import json
import base64
import extism

def b64body(data):
    if isinstance(data, str):
        data = data.encode()
    return base64.b64encode(data).decode()

def json_header():
    return {"content-type": {"values": ["application/json"]}}

def http_response(status, body, headers=None):
    resp = {"httpResponse": {"status": status, "body": b64body(body)}}
    if headers:
        resp["httpResponse"]["headers"] = headers
    return resp

def handle_health():
    return http_response(200, b'{"status":"ok"}', json_header())

def handle_check(http_req):
    body = json.loads(base64.b64decode(http_req.get("body", "")))
    user_id = body.get("userId", "")
    resource_kind = body.get("resourceKind", "unknown")
    resource_id = body.get("resourceId", "unknown")
    action = body.get("action", "view")
    roles = body.get("roles", ["user"])

    return {
        "cerbosMapping": {
            "checkRequest": {
                "principal": {"id": user_id, "roles": roles},
                "resources": [{"resource": {"id": resource_id, "kind": resource_kind}, "actions": [action]}],
            },
            "allowResponse": {"status": 200, "headers": json_header(), "body": b64body(b'{"result":"allowed"}')},
            "denyResponse": {"status": 403, "headers": json_header(), "body": b64body(b'{"result":"denied"}')},
        }
    }

@extism.plugin_fn
def cerbosInit():
    pass

@extism.plugin_fn
def cerbosDeinit():
    pass

@extism.plugin_fn
def handleCerbosResponse():
    extism.output_str(extism.input_str())

@extism.plugin_fn
def handleHTTPRoute():
    http_req = json.loads(extism.input_str())
    path = http_req.get("path", "")

    handlers = {
        "/ext/health": lambda req: handle_health(),
        "/ext/check": handle_check,
    }

    handler = handlers.get(path)
    if handler:
        result = handler(http_req)
    else:
        result = http_response(404, b"not found")

    extism.output_str(json.dumps(result))
```

## Configuration

Routes served under the `/ext/` prefix.

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
