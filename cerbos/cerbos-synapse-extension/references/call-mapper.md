
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

Add to the Synapse `config.yaml` under `extensions`.

## Basic HTTP Route Mapping

```yaml
extensions:
  routeExtensions:
    builtinRouteExtension:
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

- CEL request/response variables (`request.header`, `request.body.json`, `check.allow`, `check.outputs`, ...), string/JSON/base64/collection functions, and common patterns (JWT claim extraction, method→action mapping, path-based resource IDs): `shared/call-mapper-cel-reference.md`
- Full configuration examples (REST API with JWT verification, Envoy ext_authz with output-driven headers, output-driven status/body): `shared/call-mapper-examples.md`
