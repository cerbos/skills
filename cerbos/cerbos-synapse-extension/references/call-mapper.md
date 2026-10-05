
# Cerbos Synapse Call Mapper

Declarative YAML mappings: HTTP requests → Cerbos calls, responses formatted via CEL expressions. No code required.

## When to Use

- Simple HTTP → Cerbos mapping
- Standard REST API authorization
- Envoy external authorization
- Transformation logic fits in CEL expressions

## When NOT to Use (Use Route Extension Instead)

- Complex protocol translation
- Custom response formats (Trino, etc.)
- Filter conversion (UCAST, SQL)
- External data fetching

## Configuration Location

Add to the Synapse `config.yaml` under `extensions`. Any `routeExtensions.<name>` entry with a `mapping:` block is a call mapper; the name is yours to choose.

## Basic HTTP Route Mapping

```yaml
extensions:
  routeExtensions:
    documentCheck:
      routes:
        "/api/check": ["POST"]
      mapping:
        request:
          principal:
            id: 'request.header["X-User-Id"]'
            roles: '["user"]'
          resource:
            kind: '"document"'
            id: 'request.body.json.resourceId'
          action: 'request.body.json.action'
          auxData:
            jwt:
              token: 'request.header["Authorization"].replace("Bearer ", "", 1)'
        response:
          status: 'check.allow ? 200 : 403'
          headers:
            X-Request-Id: 'check.cerbosCallId'
          body: 'json.encode({"allowed": check.allow})'
```

Routes are served under `/ext/` (`/ext/api/check` above). Mapping CEL sees the method, headers and body but not the path, so carry resource IDs in a header or the body; when the ID lives in the URL path, write a Starlark or WASM route extension, which receives `path`.

## Route patterns

These rules apply to every route extension (call mapper, Starlark, WASM). Patterns use [gorilla/mux](https://github.com/gorilla/mux) syntax:

| Pattern | Matches |
|---------|---------|
| `/orders/status` | That exact path only, no subpaths (`/ext/orders/status/` is a 404) |
| `/orders/{version}` | One segment: `/ext/orders/v1`, not `/ext/orders/v1/billing` |
| `/orders/{id:[0-9]+}` | One segment matching the inline Go regex |
| `/orders/{rest:.*}` | Any depth, including `/`: `/ext/orders/v1/billing/invoices` |

- Use `{name:.*}` for a multi-segment wildcard; `{name...}` matches only one segment.
- The map value lists allowed methods; an empty list `[]` allows all methods.
- Matched path variables are not passed to the extension. Code-based extensions read `path` (which keeps the `/ext/` prefix) instead.
- All route extensions share one router and registration order is not guaranteed, so give each extension non-overlapping patterns (for example one disjoint prefix per team, with `"/orders": []` plus `"/orders/{path:.*}": []`). The same pattern under two extensions is a startup error.

## Envoy External Authorization

```yaml
extensions:
  envoyExternalAuthz:
    enabled: true
    mapping:
      request:
        principal:
          id: 'json.decode(base64.decode(request.attributes.request.http.headers["authorization"].replace("Bearer ", "", 1).split(".")[1])).sub'
          roles: '["user"]'
        resource:
          kind: '"api_gateway"'
          id: 'request.attributes.request.http.path'
        action: '"route"'
      response: |-
        check.allow ?
        {"status": {"code": google.rpc.Code.OK}} :
        {"status": {"code": google.rpc.Code.PERMISSION_DENIED}, "denied_response": {"status": {"code": 403}}}
```

## Reference

- Mapping fields, CEL request/response variables (`request.header`, `request.body.json`, `check.allow`, `check.outputs`, ...), string/JSON/base64/collection functions, and common patterns (JWT claim extraction, method→action mapping): `shared/call-mapper-cel-reference.md`
- Full configuration examples (REST API with JWT verification, Envoy ext_authz with output-driven headers, output-driven status/body): `shared/call-mapper-examples.md`
