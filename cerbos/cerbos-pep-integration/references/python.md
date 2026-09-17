# Python PEP

Source of truth: [`cerbos/cerbos-sdk-python`](https://github.com/cerbos/cerbos-sdk-python). Published on PyPI as `cerbos`. Requires Python 3.10+.

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

Attribute values are `google.protobuf.Value`, not bare Python objects — `Value(string_value=...)`, `Value(bool_value=...)`, `Value(number_value=...)`, and `Struct`/`ListValue` for nested data. Write one small helper that converts your dicts and use it everywhere; hand-wrapping at each call site is where this SDK gets tedious and wrong.

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

`get_query(plan, table_or_entity, attr_map, joins=None)` returns a SQLAlchemy `Select` you can keep building on with `.where(...)` and `.with_only_columns(...)`. The fourth argument is required as soon as `attr_map` spans more than one table. Supported operators are `and or not eq ne lt gt le ge in`; `operator_override_fns` swaps an operator's implementation for a dialect-specific one (`{"in": lambda c, v: c == any_(v)}`). Full detail: [SQLAlchemy adapter](https://docs.cerbos.dev/cerbos/latest/recipes/query-plan-adapters/sqlalchemy.md?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=skill&utm_content=cerbos-pep-integration).

## JWT auxiliary data

Every call takes `aux_data` (a `request_pb2.AuxData`), and `with_principal(principal, aux_data=...)` pins it for a series of checks. Semantics in [api-shapes.md](api-shapes.md).

## Framework wiring

There is no Cerbos middleware for Django, FastAPI or Flask. Wire it yourself: one dependency or helper that maps your authenticated user onto a `Principal`, another that loads the resource, and an explicit check in the handler. The [FastAPI + SQLAlchemy walkthrough](https://docs.cerbos.dev/cerbos/latest/recipes/query-plan-adapters/sqlalchemy.md?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=skill&utm_content=cerbos-pep-integration) shows the dependency-injection shape end to end.
