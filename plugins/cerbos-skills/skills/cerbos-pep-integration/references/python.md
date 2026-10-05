# Python PEP

Source of truth: [`cerbos/cerbos-sdk-python`](https://github.com/cerbos/cerbos-sdk-python). Published on PyPI as `cerbos`. Requires Python 3.10+.

Checked against `cerbos` 0.16.0 and `cerbos-sqlalchemy` 0.4.0. The adapter requires `cerbos>=0.10.4` and documents SQLAlchemy 1.4 and 2.0; 2.1 is outside that list, so pin `sqlalchemy<2.1` when using it.

## Install

```bash
pip install cerbos
```

`pip install "cerbos[testcontainers]"` adds the helper for starting a real PDP in tests.

## Two clients — pick gRPC

| Import | Transport | Status |
|---|---|---|
| `from cerbos.sdk.grpc.client import CerbosClient, AsyncCerbosClient` | gRPC, port 3593 | The one to use. Available from SDK v0.8.0. |
| `from cerbos.sdk.client import CerbosClient, AsyncCerbosClient` | HTTP, port 3592 | Kept for backwards compatibility. |

They share method names but not request types, so the two are not drop-in swappable. New code uses the gRPC client.

## Connecting

```python
from cerbos.sdk.grpc.client import CerbosClient

with CerbosClient("localhost:3593", tls_verify=False) as c:
    ...
```

```python
from cerbos.sdk.grpc.client import AsyncCerbosClient

async with AsyncCerbosClient("localhost:3593", tls_verify=False) as c:
    ...
```

```python
CerbosClient(host, tls_verify=False, playground_instance="", timeout_secs=None,
             request_retries=0, wait_for_ready=False, channel_options=None)
```

`tls_verify` defaults to `False` — the opposite of most Cerbos SDKs, so a production client must set it explicitly. It takes `True` (the OS trust store, or the file at `SSL_CERT_FILE`), or a path to a certificate. Unix sockets: `CerbosClient("unix:/var/cerbos.sock", tls_verify=False)`.

The client is a context manager holding a channel. In a web app, open it once at startup and inject it, rather than per request.

### Deadlines and failure

There is no deadline by default (`timeout_secs=None`), so a PDP that accepts the connection and then stalls blocks the request indefinitely. Set one. In 0.16.0, `timeout_secs`, `request_retries` and `wait_for_ready` are silently ignored: the SDK's gRPC service config names the service `svc.CerbosService`, which never matches the real `cerbos.svc.v1.CerbosService`. Pass a working service config through `channel_options` instead, which overrides the SDK's:

```python
import json

SERVICE_CONFIG = json.dumps({"methodConfig": [{
    "name": [{"service": "cerbos.svc.v1.CerbosService"}],
    "timeout": "0.5s",
}]})

client = CerbosClient("cerbos:3593", tls_verify=True,
                      channel_options={"grpc.service_config": SERVICE_CONFIG})
```

Leave `waitForReady` off on a request path: with it on, a call made while the PDP is down queues until the PDP returns or the deadline expires, instead of failing fast.

Transport failures raise `grpc.RpcError` (`UNAVAILABLE` when the PDP is down, `DEADLINE_EXCEEDED` past the deadline). Catch it at the check and fail closed — answer 503, never fall through to allowed:

```python
import grpc

try:
    allowed = client.is_allowed("view", principal, resource)
except grpc.RpcError:
    log.exception("cerbos check failed")
    raise ServiceUnavailable()
```

## Building requests

The gRPC client takes protobuf messages directly:

```python
from cerbos.engine.v1 import engine_pb2
from google.protobuf.struct_pb2 import Value

principal = engine_pb2.Principal(
    id="john",
    roles={"employee"},
    attr={"department": Value(string_value="marketing")},
)

resource = engine_pb2.Resource(
    id="XX125",
    kind="leave_request",
    attr={"owner": Value(string_value="john")},
)
```

Attribute values are `google.protobuf.Value`, not bare Python objects. Convert dicts with one helper and use it everywhere; hand-wrapping `Value(string_value=...)` at each call site is where this SDK gets tedious and wrong:

```python
from google.protobuf.json_format import ParseDict
from google.protobuf.struct_pb2 import Value

def to_attr(d: dict) -> dict[str, Value]:
    return {k: ParseDict(v, Value()) for k, v in d.items()}

resource = engine_pb2.Resource(id=str(doc.id), kind="document", attr=to_attr({"owner": doc.owner_id, "tags": doc.tags}))
```

`ParseDict` handles nested dicts, lists, `None` and booleans; numbers arrive as doubles, as they would over JSON.

For query plans the resource is a different message: `engine_pb2.PlanResourcesInput.Resource(kind="leave_request")` — no `id`.

The legacy HTTP client instead uses the model classes `Principal`, `Resource` and `ResourceDesc` from `cerbos.sdk.model`, which take plain Python values.

## Checking

```python
if c.is_allowed("view", principal, resource):
    ...

response = c.check_resources(principal, [
    request_pb2.CheckResourcesRequest.ResourceEntry(actions=["view", "edit"], resource=resource),
])
```

- `is_allowed(action, principal, resource, request_id=None, aux_data=None) -> bool`
- `check_resources(principal, resources, request_id=None, aux_data=None)`
- `plan_resources(action, principal, resource, request_id=None, aux_data=None)` — `action` accepts a `str` or a `list[str]`
- `server_info()`
- `with_principal(principal, aux_data=None)` returns a `PrincipalContext` so repeated checks for one user stop repeating the principal

Note the argument order: **action first**, then principal, then resource. There is no `check_resource`; `is_allowed` is a one-entry `check_resources` underneath, so several actions on one resource means calling `check_resources` with one entry and several actions rather than looping `is_allowed`.

`AsyncCerbosClient` has the same method names, awaited.

## Query plan

```python
plan = c.plan_resources(action="view", principal=principal, resource=plan_resource)
```

Branch on the plan kind before reading the condition — see [query-plan.md](query-plan.md).

### SQLAlchemy adapter

```bash
pip install cerbos-sqlalchemy
```

```python
from cerbos_sqlalchemy import get_query

query = get_query(plan, Contact, {
    "request.resource.attr.owner_id": User.id,
    "request.resource.attr.is_active": Contact.is_active,
}, [(User, Contact.owner_id == User.id)])
```

`get_query(plan, table_or_entity, attr_map, table_mapping=None, operator_override_fns=None)` returns a SQLAlchemy `Select` you can keep building on with `.where(...)` and `.with_only_columns(...)`. It branches on the plan kind itself — `select(t).where(False)` for `ALWAYS_DENIED`, plain `select(t)` for `ALWAYS_ALLOWED` — and the package exports nothing but `get_query`, so there is no `PlanKind` to import. The fourth argument is required as soon as `attr_map` spans more than one table. Logic, comparison, arithmetic, `in`, `size`, string helpers, timestamps and hierarchy functions translate out of the box; collection operators need an `operator_override_fns` entry, and `matches()` and any other unsupported shape raise rather than widen the query. `operator_override_fns` also swaps an operator for a dialect-specific one (`{"in": lambda c, v: c == any_(v)}`). Full detail: [SQLAlchemy adapter](https://docs.cerbos.dev/cerbos/latest/recipes/query-plan-adapters/sqlalchemy?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-pep-integration_pdp-recipes-query-plan-adapters-sqlalchemy).

## JWT auxiliary data

Every call takes `aux_data` (a `request_pb2.AuxData`), and `with_principal(principal, aux_data=...)` pins it for a series of checks. Semantics in [api-shapes.md](api-shapes.md).

## Framework wiring

There is no Cerbos middleware for Django, FastAPI or Flask. Wire it yourself: one dependency or helper that maps your authenticated user onto a `Principal`, another that loads the resource, and an explicit check in the handler. The [FastAPI + SQLAlchemy walkthrough](https://docs.cerbos.dev/cerbos/latest/recipes/query-plan-adapters/sqlalchemy?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-pep-integration_pdp-recipes-query-plan-adapters-sqlalchemy) shows the dependency-injection shape end to end.
