# Cerbos PDP API shapes

Wire-level ground truth. Every SDK is a typed wrapper over these two calls, so when an SDK's naming is ambiguous, read the request it builds against this page.

A running PDP serves its own OpenAPI explorer at `http://localhost:3592/`. That is the authoritative schema for the version you are on; this page is the summary.

## Endpoints

| | REST (default port 3592) | gRPC (default port 3593) |
|---|---|---|
| Check | `POST /api/check/resources` | `cerbos.svc.v1.CerbosService/CheckResources` |
| Query plan | `POST /api/plan/resources` | `cerbos.svc.v1.CerbosService/PlanResources` |
| Server info | `GET /api/server_info` | `cerbos.svc.v1.CerbosService/ServerInfo` |

The PDP also exposes an [OpenID AuthZEN](https://openid.github.io/authzen/) façade at `/access/v1/evaluation` and `/access/v1/evaluations`, mapping subject→principal, resource→resource, action→action. Reach for it only when a third-party system speaks AuthZEN; the native API is richer.

## CheckResources

```json
{
  "requestId": "test",
  "principal": {
    "id": "alice",
    "roles": ["employee"],
    "attr": { "department": "accounting", "geography": "GB" },
    "policyVersion": "20210210",
    "scope": "acme.corp"
  },
  "resources": [
    {
      "resource": {
        "id": "XX125",
        "kind": "leave_request",
        "attr": { "owner": "john", "status": "PENDING_APPROVAL" },
        "policyVersion": "20210210",
        "scope": "acme.corp"
      },
      "actions": ["view:public", "approve", "create"]
    }
  ],
  "auxData": { "jwt": { "token": "xxx.yyy.zzz", "keySetId": "ks1" } },
  "includeMeta": true
}
```

Required, enforced by request validation (`cerbos/engine/v1/engine.proto`):

- `principal.id` — non-empty string.
- `principal.roles` — at least one, unique, each non-empty.
- `resource.kind` — non-empty; selects the resource policy.
- `resource.id` — non-empty; the instance identifier, and available in conditions as `R.id`.

Optional: `attr` on either side (free-form JSON, the whole basis for ABAC conditions), `policyVersion`, `scope` (dot-separated, drives [scoped policy](https://docs.cerbos.dev/cerbos/latest/policies/scoped_policies) inheritance), `requestId` (echoed back; put your trace ID here), `includeMeta`.

**Batch limits**: 50 resources per request and 50 actions per resource, both defaults, both raisable under `server.requestLimits` in the PDP config ([server configuration](https://docs.cerbos.dev/cerbos/latest/configuration/server)). Chunk larger batches client-side rather than raising the limit.

### Response

```json
{
  "requestId": "test",
  "results": [
    {
      "resource": { "id": "XX125", "kind": "leave_request" },
      "actions": { "view:public": "EFFECT_ALLOW", "approve": "EFFECT_DENY" },
      "outputs": [ { "src": "resource.leave_request.vdefault#rule-001", "val": "create_allowed:john" } ],
      "validationErrors": [
        { "path": "/department", "message": "value must be one of \"marketing\", \"engineering\"", "source": "SOURCE_PRINCIPAL" }
      ],
      "meta": {
        "actions": { "view:public": { "matchedPolicy": "resource.leave_request.vdefault/acme.corp", "matchedScope": "acme" } },
        "effectiveDerivedRoles": ["any_employee"]
      }
    }
  ],
  "cerbosCallId": "01HHENANTHFD5DV3HZGDKB87PJ"
}
```

- `results` comes back in request order, one entry per resource.
- Every action maps to `EFFECT_ALLOW` or `EFFECT_DENY`. Cerbos is deny-by-default: an action no rule allows is `EFFECT_DENY`, and a policy that fails to load produces denials rather than errors.
- `outputs` carries [policy output expressions](https://docs.cerbos.dev/cerbos/latest/policies/outputs) — the mechanism behind returning a permitted-field list for field-level security.
- `validationErrors` appears when [schema enforcement](https://docs.cerbos.dev/cerbos/latest/policies/schemas) is on and the attributes you sent did not match. Surface these in development; they mean the PEP is sending the wrong shape.
- `meta` is populated only when `includeMeta` was set. It names the matched policy and the derived roles that activated — the first thing to look at when a decision surprises you.
- `cerbosCallId` ties the decision to the PDP's audit log entry. Log it next to your own request ID.

### curl

```bash
cat <<EOF | curl --silent "localhost:3592/api/check/resources?pretty" -d @-
{
  "principal": { "id": "alice", "roles": ["employee"], "attr": {} },
  "resources": [
    { "resource": { "kind": "leave_request", "id": "XX125", "attr": {} }, "actions": ["view:public", "approve"] }
  ]
}
EOF
```

## PlanResources

```json
{
  "requestId": "test01",
  "actions": ["approve"],
  "principal": { "id": "alicia", "roles": ["user"], "attr": { "geography": "GB" } },
  "resource": { "kind": "leave_request", "attr": { "owner": "alicia" } },
  "includeMeta": true
}
```

The resource here is a *description*, not an instance: `kind` is required and there is no `id`. `resource.attr` holds whatever you already know about the whole set under consideration — anything you omit stays as a variable in the returned AST, which is exactly what you want for columns you intend to filter on in the database.

`action` (singular) and `actions` are mutually exclusive and exactly one must be set. The proto marks singular `action` deprecated; `actions` takes up to 20 unique actions and the plan returned is the logical AND of the per-action plans. Some SDKs and adapter examples still show the singular form — both work.

### Response

```json
{
  "requestId": "test01",
  "action": "approve",
  "resourceKind": "leave_request",
  "filter": {
    "kind": "KIND_CONDITIONAL",
    "condition": {
      "expression": {
        "operator": "eq",
        "operands": [ { "variable": "request.resource.attr.status" }, { "value": "PENDING_APPROVAL" } ]
      }
    }
  },
  "meta": { "filterDebug": "(request.resource.attr.status == \"PENDING_APPROVAL\")" },
  "cerbosCallId": "01HHENANTHFD5DV3HZGDKB87PJ"
}
```

`filter.kind` is one of `KIND_ALWAYS_ALLOWED`, `KIND_ALWAYS_DENIED`, `KIND_CONDITIONAL`; `condition` is populated only for the last. Handling all three is not optional — see [query-plan.md](query-plan.md).

`meta.filterDebug` renders the AST as a readable CEL string when `includeMeta` is set. Log it while developing a mapper; it tells you instantly which attribute paths your mapper has to cover.

### Condition AST

An expression node is `{ "operator": ..., "operands": [...] }`; an operand is a nested `expression`, a `{ "variable": "request.resource.attr.foo" }`, or a `{ "value": ... }`.

Operators emitted: `add`, `and`, `div`, `eq`, `ge`, `gt`, `in`, `index`, `lambda`, `le`, `list`, `lt`, `mod`, `mult`, `ne`, `not`, `or`, `sub`. Collection conditions additionally emit `filter`, `exists`, `exists_one`, `all`, `map`, `hasIntersection`.

Nested example — `(R.attr.department == "marketing") && (R.attr.team != "design")`:

```json
{ "expression": { "operator": "and", "operands": [
  { "expression": { "operator": "eq", "operands": [ { "variable": "request.resource.attr.department" }, { "value": "marketing" } ] } },
  { "expression": { "operator": "ne", "operands": [ { "variable": "request.resource.attr.team" }, { "value": "design" } ] } }
] } }
```

A lambda (`R.attr.values.filter(t, t > 0)`) nests an `operator: "lambda"` node whose first operand is the bound `{ "variable": "t" }` and whose second is the body.

## Auxiliary data (JWT)

`auxData` is optional on both calls and takes one of two mutually exclusive forms:

```json
"auxData": { "jwt": { "token": "xxx.yyy.zzz", "keySetId": "ks1" } }
```

```json
"auxData": { "jwts": {
  "app_token":     { "token": "xxx.yyy.zzz", "keySetId": "ks1" },
  "gateway_token": { "token": "aaa.bbb.ccc", "keySetId": "ks2" }
} }
```

- `jwts` (multiple named tokens) requires Cerbos PDP 0.55.0 or later.
- `keySetId` is optional when the PDP has exactly one keyset configured, and **mandatory** as soon as it has more than one.
- In policy conditions the claims land at `request.auxData.jwt.<claim>` for the single form and `request.auxData.jwts.<name>.claims.<claim>` for the named form — the `claims` segment is not optional.

The PDP verifies the signature and the `exp`/`nbf` claims against the keysets configured under `auxData.jwt.keySets` ([auxdata configuration](https://docs.cerbos.dev/cerbos/latest/configuration/auxdata)) — JWKS URL, local `.jwks` file, inline base64, or PEM. Refresh honours `Cache-Control`/`Expiry` headers unless `refreshInterval` is set, defaulting to one hour.

Cerbos treats its own JWT verification as a convenience, not the authoritative check: verify the token at your gateway or in your application before calling the PDP. Sending a JWT saves you unpacking claims into `principal.attr` by hand; it does not move authentication into the PDP.

Passing the raw token also puts every claim in the PDP's reach. When a policy needs two claims out of forty, mapping those two into `principal.attr` yourself keeps the blast radius smaller.

## Talking to the PDP without an SDK

gRPC reflection is enabled, so `grpcurl` works against port 3593:

```bash
cat <<EOF | grpcurl -plaintext -d @ localhost:3593 cerbos.svc.v1.CerbosService/CheckResources
{ "principal": { "id": "alice", "roles": ["employee"] },
  "resources": [ { "resource": { "kind": "leave_request", "id": "XX125" }, "actions": ["view:public"] } ] }
EOF
```

For a language with no Cerbos SDK, generate a client from the OpenAPI document the PDP serves at `/schema/swagger.json`, or from the protobuf definitions in [`cerbos/cerbos/api/public`](https://github.com/cerbos/cerbos/tree/main/api/public). Full instructions: [the Cerbos API](https://docs.cerbos.dev/cerbos/latest/api/index).
