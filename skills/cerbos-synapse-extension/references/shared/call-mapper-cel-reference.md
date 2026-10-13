# CEL Expression Reference

## Mapping Fields

Every value is a CEL expression, so string literals need inner quotes: `kind: '"document"'` (bare `kind: document` is a reference to an undefined variable).

| Field | Returns |
|-------|---------|
| `request.requestID` | string |
| `request.principal.id` | string (required) |
| `request.principal.roles` | list of strings, or a YAML list of expressions each returning a string (required) |
| `request.principal.attr` | map, or a YAML map of expressions |
| `request.principal.policyVersion`, `.scope` | string |
| `request.resource.kind`, `.id` | string (required) |
| `request.resource.attr` | map, or a YAML map of expressions |
| `request.resource.policyVersion`, `.scope` | string |
| `request.action` | string (required) |
| `request.auxData.jwt.token`, `.keySetID` | string |
| `response.status` | int; defaults to 200 when allowed, 403 when denied |
| `response.headers` | map of strings, or a YAML map of expressions |
| `response.body` | string or bytes |

## Request Context Variables

Request expressions see the incoming HTTP request as `request`:

| Variable | Description |
|----------|-------------|
| `request.method` | HTTP method, uppercase |
| `request.header["Name"]` | Header value as a string (comma-joined when repeated); keys in canonical case |
| `request.headers["Name"]` | Header values as a list |
| `request.body.json.*` | Parsed JSON body |
| `request.body.text` | Body as a string |
| `request.body.bytes` | Raw body |

These are the only fields: path, URL and query string are not available. When a value lives in the path, use a Starlark or WASM route extension.

For `envoyExternalAuthz`, `request` is the Envoy `CheckRequest` instead: read `request.attributes.request.http.{method,path,headers}`.

## Response Context Variables

Response expressions see the decision as `check`; `request` is not available here:

| Variable | Description |
|----------|-------------|
| `check.allow` | Boolean authorization result |
| `check.cerbosCallId` | Audit log call ID |
| `check.requestId`, `check.principal`, `check.resource`, `check.action` | The inputs the request expressions produced |
| `check.outputs` | Policy outputs, keyed by `<policy-id>#<rule-name>` |
| `check.outputs["resource.document.vdefault#approve-rule"]` | One rule's output; an unnamed rule is keyed `#rule-NNN` by position |
| `check.validationErrors` | Schema validation errors for principal and resource |

## String Functions

| Function | Description | Example |
|----------|-------------|---------|
| `.replace(old, new, n)` | Replace n occurrences | `header.replace("Bearer ", "", 1)` |
| `.split(delimiter)` | Split to list | `"a,b,c".split(",")` |
| `.lowerAscii()` | Lowercase | `header.lowerAscii()` |
| `.upperAscii()` | Uppercase | `header.upperAscii()` |
| `.startsWith(prefix)` | Check prefix | `key.startsWith("x-")` |
| `.endsWith(suffix)` | Check suffix | `path.endsWith(".json")` |
| `.contains(substr)` | Check contains | `s.contains("admin")` |
| `.matches(regex)` | Regex match | `s.matches("^[a-z]+$")` |
| `string(v)` | Convert to string | `string(123)` |

## JSON Functions

| Function | Description | Example |
|----------|-------------|---------|
| `json.encode(value)` | Serialize to JSON | `json.encode({"key": "value"})` |
| `json.decode(string)` | Parse JSON | `json.decode(body)` |

## Base64 Functions

| Function | Description | Example |
|----------|-------------|---------|
| `base64.encode(bytes)` | Encode to base64 | `base64.encode(data)` |
| `base64.decode(string)` | Decode base64 | `base64.decode(token)` |

## Collection Functions

| Function | Description | Example |
|----------|-------------|---------|
| `has(field)` | Check field exists | `has(check.outputs)` |
| `size(collection)` | Get length | `size(list) > 0` |
| `type(value)` | Get type | `type(v) == list` |
| `.filter(item, expr)` | Filter list | `list.filter(h, h.valid)` |
| `.map(item, expr)` | Map list | `list.map(x, x.id)` |
| `.all(item, expr)` | All match | `list.all(x, x > 0)` |
| `.exists(item, expr)` | Any match | `list.exists(x, x > 0)` |
| `.flatten()` | Flatten nested | `nested.flatten()` |
| `.transformList(k, v, expr)` | Transform map | `m.transformList(k, v, {...})` |

## Conditional Expressions

Ternary:
```yaml
status: 'check.allow ? 200 : 403'
```

Multi-line ternary:
```yaml
response: |-
  check.allow ?
  {"status": 200, "body": "allowed"} :
  {"status": 403, "body": "denied"}
```

Nested ternary:
```yaml
action: |-
  request.method == "GET" ? "read" :
  request.method == "POST" ? "create" :
  request.method == "PUT" ? "update" :
  request.method == "DELETE" ? "delete" : "unknown"
```

## Common Patterns

### Extract JWT Claims (inline)
```yaml
id: 'json.decode(base64.decode(request.header["Authorization"].replace("Bearer ", "", 1).split(".")[1].replace("-", "+").replace("_", "/"))).sub'
```

### Dynamic Action from Method
```yaml
action: |-
  request.method == "GET" ? "read" :
  request.method == "POST" ? "create" :
  request.method == "PUT" ? "update" :
  request.method == "DELETE" ? "delete" : "unknown"
```

### Conditional Response with Outputs
```yaml
body: |-
  check.allow
    ? json.encode({"authorized": true})
    : json.encode({
        "authorized": false,
        "reason": has(check.outputs) ? check.outputs : "access denied"
      })
```
