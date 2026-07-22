# Python integration recipe

**SDK packages**: [cerbos](https://pypi.org/project/cerbos/) (gRPC + HTTP clients, each in sync and async variants; `cerbos[testcontainers]` extra for tests), [cerbos-sqlalchemy](https://pypi.org/project/cerbos-sqlalchemy/) (query-plan adapter)
**Live sources — fetch these before writing any integration code:**
- SDK repo README: https://raw.githubusercontent.com/cerbos/cerbos-sdk-python/main/README.md
- SDK source (authoritative for signatures): https://github.com/cerbos/cerbos-sdk-python — clients under `src/cerbos/sdk/`
- Query-plan adapters: https://github.com/cerbos/query-plan-adapters — Python adapter in `sqlalchemy/`, read its README
- Docs index: https://docs.cerbos.dev/llms.txt

This is a pointer-tier recipe: it names the verified entry points and where checks belong. Fetch the live sources above for the full API surface before writing code. The SDK requires Python >= 3.10.

## 1. Client setup

`pip install cerbos`. Two transports, each with sync and async clients:

- **gRPC** (recommended, PDP port 3593): `from cerbos.sdk.grpc.client import CerbosClient, AsyncCerbosClient`. Principals/resources are protobuf messages from `cerbos.engine.v1.engine_pb2`; attribute values are `google.protobuf.struct_pb2.Value`.
- **HTTP** (kept for backwards compatibility, PDP port 3592): `from cerbos.sdk.client import CerbosClient, AsyncCerbosClient` with plain-dict dataclass models from `cerbos.sdk.model` (`Principal`, `Resource`, `ResourceDesc`).

Prefer gRPC for new integrations. One client per process, created at startup — never per request.

```python
# app/authz/client.py
import os
from cerbos.sdk.grpc.client import AsyncCerbosClient

def make_client() -> AsyncCerbosClient:
    return AsyncCerbosClient(
        os.environ.get("CERBOS_ADDRESS", "localhost:3593"),
        tls_verify=os.environ.get("CERBOS_TLS_CA_CERT") or False,  # bool or path to CA cert
    )
```

The constructor also accepts `timeout_secs`, `request_retries`, `wait_for_ready`, and `channel_options`; clients are context managers and expose `close()`. See the README for TLS and Unix-socket (`unix:/path.sock`) addressing.

## 2. Principal construction

One canonical helper maps your auth context (JWT claims, session user) to a principal; every check and plan call goes through it.

```python
from cerbos.engine.v1 import engine_pb2
from google.protobuf.struct_pb2 import Value

def to_principal(user) -> engine_pb2.Principal:
    return engine_pb2.Principal(
        id=user.id,
        roles=set(user.roles),  # must be non-empty
        attr={  # only attributes referenced by policy conditions
            "department": Value(string_value=user.department or ""),
            "tenant_id": Value(string_value=user.tenant_id or ""),
        },
    )
```

Write a matching `to_resource(kind, obj)` helper per resource kind. `client.with_principal(principal)` returns a bound context whose methods omit the principal argument — useful for per-request wiring.

## 3. Framework integration points

Placement follows [ARCHITECTURE.md](../ARCHITECTURE.md): middleware only builds the principal and request-time attributes; any decision that depends on resource attributes happens in the service layer, after the resource is loaded.

### FastAPI

Create the async client in the lifespan handler, inject it as a dependency, check in the route/service after loading the resource.

```python
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, Request

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with make_client() as client:
        app.state.cerbos = client
        yield

def get_cerbos(request: Request) -> AsyncCerbosClient:
    return request.app.state.cerbos

@app.get("/documents/{doc_id}")
async def get_document(doc_id: str, user=Depends(current_user), cerbos=Depends(get_cerbos)):
    doc = await repo.find(doc_id)  # 404 if missing
    if not await cerbos.is_allowed("view", to_principal(user), to_resource("document", doc)):
        raise HTTPException(status_code=403)
    return doc
```

### Flask

Sync client as a module-level singleton (or an app extension storing it on `app.extensions`); principal built once per request from `g.user`.

```python
cerbos = CerbosClient(os.environ.get("CERBOS_ADDRESS", "localhost:3593"))  # sync gRPC client

@app.get("/documents/<doc_id>")
def get_document(doc_id):
    doc = repo.find_or_404(doc_id)
    if not cerbos.is_allowed("view", to_principal(g.user), to_resource("document", doc)):
        abort(403)
    return jsonify(doc)
```

### Django / DRF

- Coarse, pre-load gates: a DRF permission class calling `is_allowed` with a kind-only resource (`engine_pb2.Resource(kind="document", id="new")`) — appropriate only when the decision needs nothing from the database (e.g. gating create).
- Resource-aware checks: service layer, after the ORM load, same `is_allowed` shape as above.
- List endpoints: `plan_resources`, then filter via the SQLAlchemy adapter if you use SQLAlchemy, or hand-walk the plan into `Q` objects for the Django ORM (section 5).

## 4. Single-resource checks

`is_allowed(action, principal, resource) -> bool` for one action. To batch actions (or resources) in one round trip, use `check_resources` with `ResourceEntry` items, and the response helpers from `cerbos.sdk.grpc.utils`:

```python
from cerbos.request.v1 import request_pb2
from cerbos.sdk.grpc import utils

resp = await cerbos.check_resources(
    principal=to_principal(user),
    resources=[request_pb2.CheckResourcesRequest.ResourceEntry(
        resource=to_resource("document", doc), actions=["view", "edit", "delete"],
    )],
)
entry = utils.get_resource(resp, doc.id)
can_view = entry is not None and utils.is_allowed(entry, "view")
```

A missing entry or a raised error is a deny — let errors propagate to a 5xx or catch-and-deny, never catch-and-allow.

## 5. List filtering

Never fetch-then-filter. Ask for a query plan, then compile it with `cerbos-sqlalchemy`:

```python
from cerbos_sqlalchemy import get_query

plan = await cerbos.plan_resources(
    action="view",
    principal=to_principal(user),
    resource=engine_pb2.PlanResourcesInput.Resource(kind="document"),
)
query = get_query(plan, Document, {
    "request.resource.attr.owner_id": Document.owner_id,
    "request.resource.attr.status": Document.status,
})
query = query.where(Document.deleted_at.is_(None))  # AND with existing app filters
```

`get_query(query_plan, table, attr_map, table_mapping=None, operator_override_fns=None)` returns a SQLAlchemy `Select` and accepts both the gRPC and HTTP plan response types. It resolves the three plan outcomes internally: `ALWAYS_ALLOWED` → unfiltered `select(table)`; `ALWAYS_DENIED` → `select(table).where(False)` (guaranteed-empty query); `CONDITIONAL` → WHERE clause built from the plan's condition AST. `table_mapping` supplies join tuples when mapped attributes span tables — see the adapter README.

No adapter exists for the Django ORM: branch on `plan.filter.kind` yourself — `KIND_ALWAYS_DENIED` → `queryset.none()`, `KIND_ALWAYS_ALLOWED` → no extra filter, `KIND_CONDITIONAL` → translate the condition AST into `Q` objects, keeping the attribute-to-field mapper next to the model.

## 6. The authorization helper (real check + enforcement flag)

One helper, used at every callsite, that **always runs the real Cerbos check**; a per-callsite mode flag decides whether a Cerbos deny blocks (`enforce`) or is only logged while the legacy decision stands (`shadow`). There is no separate shadow helper — shadow is a value of the flag, so the callsite is identical in every mode and cutover is a config change. Full contract and rollout sequencing in [ARCHITECTURE.md](../ARCHITECTURE.md) §4: in `shadow` the Cerbos check must never block or fail the response and mismatches emit one structured log line; in `enforce` Cerbos decides and errors deny. Mode is per callsite via env (`AUTHZ_MODE_<CALLSITE>` overriding `AUTHZ_MODE`, default `shadow`). Greenfield integrations pin the mode to `enforce` and pass `legacy_decision=None`.

```python
def authz_mode(callsite: str) -> str:
    key = "AUTHZ_MODE_" + re.sub(r"[^A-Z0-9]+", "_", callsite.upper())
    return os.environ.get(key) or os.environ.get("AUTHZ_MODE", "shadow")

# Always issues the real Cerbos check; the mode flag decides what to do with the result.
async def authorize(endpoint, request_id, principal, resource, action, legacy_decision=None) -> bool:
    if authz_mode(endpoint) == "enforce":
        try:
            return await cerbos.is_allowed(action, principal, resource)
        except Exception:
            return False  # fail closed
    legacy = bool(legacy_decision()) if legacy_decision else True

    async def compare():  # fire-and-forget: never blocks the response
        try:
            allowed = await asyncio.wait_for(cerbos.is_allowed(action, principal, resource), 1.0)
        except Exception:
            return
        if allowed != legacy:
            logger.info(json.dumps({
                "event": "cerbos_shadow_mismatch", "endpoint": endpoint,
                "principalId": principal.id, "resourceKind": resource.kind,
                "resourceId": resource.id, "action": action,
                "legacy": legacy, "cerbos": allowed, "requestId": request_id,
            }))

    asyncio.create_task(compare())
    return legacy
```

In sync frameworks (Flask, Django) run `compare` on a `ThreadPoolExecutor` with the sync client and a short `timeout_secs` instead of an asyncio task. Cut a callsite over to `enforce` once its mismatch rate holds at zero over a representative window, then delete the legacy check.

## 7. Testing

If the app already runs a PDP via docker-compose for local dev, reuse it in tests (point the client at it) rather than adding a new dependency. Otherwise the SDK ships testcontainers support: `pip install cerbos[testcontainers]`, `from cerbos.sdk.container import CerbosContainer` (defaults to `ghcr.io/cerbos/cerbos:latest`, exposes 3592/3593). Either way, test decisions against real policies, not mocks.

```python
from cerbos.sdk.container import CerbosContainer
from cerbos.sdk.grpc.client import CerbosClient

container = CerbosContainer()
container.with_volume_mapping(str(POLICIES_DIR), "/policies")
with container:
    container.wait_until_ready()
    with CerbosClient(container.grpc_host(), tls_verify=False) as client:
        assert client.is_allowed("edit", owner_principal, owned_resource)
```

`http_host()` serves the HTTP client. Point the app under test at the container via `CERBOS_ADDRESS` or your DI seam (FastAPI `dependency_overrides`). For pure policy logic prefer Cerbos's YAML test suites (`cerbos compile --tests`); keep app-level tests on wiring — principal construction, attr_map correctness, deny paths returning 403/empty lists.

## 8. Local dev PDP

```yaml
# docker-compose.yml
services:
  cerbos:
    image: ghcr.io/cerbos/cerbos:latest
    command: ["server"]
    ports:
      - "3592:3592" # HTTP
      - "3593:3593" # gRPC
    volumes:
      - ./policies:/policies:ro
```

The disk driver watches `/policies`, so policy edits apply without a restart. Point the app at it with `CERBOS_ADDRESS=localhost:3593` (gRPC) or `https://localhost:3592`-style URLs for the HTTP client.
