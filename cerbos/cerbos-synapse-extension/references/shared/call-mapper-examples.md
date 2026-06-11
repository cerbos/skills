# Call Mapper Examples

Full configuration examples. Mapping basics and when to use the call mapper: `../call-mapper.md`. CEL variables, functions, and expression patterns: `call-mapper-cel-reference.md`.

## REST API Authorization

```yaml
server:
  listenAddress: ":3594"

pdp:
  inProcess:
    storage:
      driver: disk
      disk:
        directory: /policies
    auxData:
      jwt:
        disableVerification: false
        keySets:
          - id: auth-keys
            local:
              file: /certs/jwks.json
    engine:
      defaultPolicyVersion: "1"

extensions:
  dataDir: /tmp/data
  cacheDir: /tmp/cache
  routeExtensions:
    builtinRouteExtension:
      routes:
        "/api/v1/documents": ["GET", "POST"]
        "/api/v1/documents/{id}": ["GET", "PUT", "DELETE"]
      mapping:
        request:
          principal:
            id: 'request.header["X-User-Id"]'
            roles: 'request.header["X-Roles"].split(",")'
          resource:
            kind: '"document"'
            id: 'size(request.path.split("/")) > 4 ? request.path.split("/")[4] : "new"'
            attr:
              org_id: 'request.header["X-Org-Id"]'
          action: |-
            request.method == "GET" ? "read" :
            request.method == "POST" ? "create" :
            request.method == "PUT" ? "update" :
            request.method == "DELETE" ? "delete" : "unknown"
          auxData:
            jwt:
              token: 'request.header["Authorization"].replace("Bearer ", "", 1)'
              keySetID: '"auth-keys"'
        response:
          status: 'check.allow ? 200 : 403'
          headers:
            X-Cerbos-Request-Id: 'check.cerbosCallId'
          body: |-
            check.allow
              ? json.encode({"authorized": true})
              : json.encode({
                  "authorized": false,
                  "error": "Access denied",
                  "request_id": check.cerbosCallId
                })
```

## Envoy External Authorization (Full)

```yaml
extensions:
  envoyExternalAuthz:
    enabled: true
    mapping:
      request:
        requestID: 'request.attributes.request.http.headers["x-request-id"]'
        principal:
          id: 'json.decode(base64.decode(request.attributes.request.http.headers["authorization"].replace("Bearer ", "", 1).split(".")[1].replace("-", "+").replace("_", "/"))).sub'
          roles: 'json.decode(base64.decode(request.attributes.request.http.headers["authorization"].replace("Bearer ", "", 1).split(".")[1].replace("-", "+").replace("_", "/"))).roles'
        resource:
          kind: '"api_gateway"'
          id: 'request.attributes.request.http.path'
          attr:
            path: 'request.attributes.request.http.path'
            method: 'request.attributes.request.http.method'
        action: '"route"'
        auxData:
          jwt:
            token: 'request.attributes.request.http.headers["authorization"].replace("Bearer ", "", 1)'
            keySetID: '"local-dev-cert"'
      response: |-
        check.allow ?
        {
          "status": {"code": google.rpc.Code.OK},
          "ok_response": {
            "headers": has(check.outputs) && size(check.outputs) > 0
              ? check.outputs.transformList(ruleKey, ruleOutput,
                  ruleOutput.transformList(k, v,
                    {"header": {"key": k.lowerAscii(), "value": type(v) == list ? json.encode(v) : string(v)}, "append_action": 2}
                  )
                ).flatten().filter(h, h.header.key.startsWith("x-authz-"))
              : []
          }
        }
        :
        {
          "status": {"code": google.rpc.Code.PERMISSION_DENIED},
          "denied_response": {
            "status": {"code": 403},
            "body": "access denied"
          }
        }
```

## Simple Beverage API

```yaml
extensions:
  routeExtensions:
    builtinRouteExtension:
      routes:
        "/teapot": ["POST"]
      mapping:
        request:
          principal:
            id: 'request.header["X-User-Id"]'
            roles: '["user"]'
          resource:
            kind: '"beverage"'
            id: 'request.body.json.beverage'
          action: '"brew"'
          auxData:
            jwt:
              token: 'request.header["Authorization"].replace("Bearer ", "", 1)'
        response:
          status: 'check.allow ? 204 : check.outputs["resource.beverage.v1#brew"].status'
          headers:
            X-Cerbos-Call-Id: 'check.cerbosCallId'
          body: 'check.allow ? "" : json.encode(check.outputs["resource.beverage.v1#brew"].body)'
```

