# CEL Expression Reference

## Request Context Variables

| Variable | Description |
|----------|-------------|
| `request.header["Name"]` | HTTP request header value |
| `request.body.json.*` | Parsed JSON body fields |
| `request.path` | Request URL path |
| `request.method` | HTTP method |
| `request.attributes.*` | Envoy-specific attributes |

## Response Context Variables

| Variable | Description |
|----------|-------------|
| `check.allow` | Boolean authorization result |
| `check.cerbosCallId` | Unique request identifier |
| `check.outputs` | Policy rule outputs map |
| `check.outputs["policy.rule#action"]` | Specific rule output |

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

### Resource ID from Path
```yaml
id: 'request.path.split("/")[3]'  # /api/v1/documents/{id}
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
