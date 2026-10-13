# Cross-cutting patterns and gotchas

Patterns recurring across runtimes. Per-implementation references show exact code; this explains the shape.

## Patterns

**Caching.** All runtimes: `cacheGet` / `cacheSet` / `cacheDelete` (+ `cacheSetIfNotExists` in WASM). Durations: `time.minute` (Starlark), **milliseconds** (WASM). Starlark values must be JSON-encoded strings; WASM stores raw bytes. The store is the top-level `cache` config: `backend: inmem` (default; `inmem.maxSize`) is **per Synapse instance**, so replicas don't share entries; `backend: redis` (`redis.connectionURL`) is shared. With Redis unreachable, cache writes raise an error, and a `required: true` extension then aborts the request — treat the cache as fallible.

**Data source lookup.** Proxy/route/envoy call a configured data source by name: `cerbos.data_source_lookup(datasource, query)` (Starlark), `dataSourceLookup(json)` (WASM host import). Response: `{ result: <any> }`. Starlark: JSON round-trip `json.decode(json.encode(resp.result))` to safely extract proto struct fields.

**Principal enrichment (proxy).** Read request → extract `principal.id` → cache lookup → on miss, data source → merge into `principal.attr` → return modified request.

**Proxy pipeline ordering.** Onion order — same for Check, Plan and AuthZEN: requests run in descending `priority`, responses back in reverse, so the highest priority sees the request first and the response last. Equal priorities tie-break on FQN (`proxy.<name>.<hash>`, descending) — **give each extension a distinct `priority` when order matters**. `required: true` → failure terminates chain; else skipped. **PDP calls made through the host functions (`cerbos.check_resources()`, WASM `checkResources` etc.) bypass the proxy pipeline** — prevents re-entry loops; enrichment for those calls must happen in the extension itself (or shared data source). A check request a route or Envoy extension *returns* (mapping or callback mode) is different: it goes through the configured proxy extensions like any API call.

**Route matching: keep patterns non-overlapping.** Path patterns are global across every route extension, and registration order is not guaranteed: when `"/docs/latest"` and `"/docs/{id}"` both match, which extension handles the request varies from run to run. Give every route a pattern no other route can match (e.g. `"/docs/latest"` and `"/docs/by-id/{id}"`). An identical pattern in two extensions is a startup error (`multiple extensions registered for route`). Pattern syntax: [call-mapper.md](../call-mapper.md#route-patterns).

**OAuth upstreams (Starlark).** Use `oauth.client_credentials_client(...)`, not hand-rolled `http.post` to token endpoint. Pass `persist_key` to reuse the client across requests — else re-auth per invocation. See `starlark-environment.md`.

**Callback mode (route/envoy).** Return only the check request: a top-level `checkRequest` from a route's `handleHTTPRoute` (not inside `cerbosMapping`), or `cerbosCheckRequest` from `envoyCheck` (Envoy only — a route returning it fails with HTTP 500). Synapse calls the PDP (through the proxy pipeline), then `handleCerbosResponse` / `envoyMapCerbosResponse` with the original request, the check request and the PDP response. The callback returns the final response itself: a bare HTTP response `{status, headers, body}` (route; base64 body, no `httpResponse` wrapper) or an Envoy CheckResponse (envoy). Echoing the input back fails the request with HTTP 500. Starlark names differ: `handle_cerbos_response` (route; returns `struct(status=..., headers=..., body=...)` unwrapped) and `map_cerbos_response` (envoy — not `envoy_map_cerbos_response`).

**Lifecycle.** WASM may export `cerbosInit` / `cerbosDeinit`. Synapse pools several instances of each module, so `cerbosInit` runs **once per pooled instance** — many times, not once — and suits per-instance resources such as a DB connection; `cerbosDeinit` runs on every instance at graceful shutdown. Keep shared side effects (seeding or clearing cache keys) out of both. JS/Python: **declaring without implementing crashes the module** (extism generates broken stub). Only declare what you implement.

**Manifest (0.10+).** Any extension may export `manifest`, which Synapse lists at `/_cerbos/meta` (JSON) and `/_cerbos/about` (HTML). Optional but recommended. Required fields: API version `1`, `name`, `version`; optional `owner`, `description`, `fieldMappings`.

```python
def manifest():   # Starlark
    return struct(api_version = 1, name = "enrich-principal", version = "1.0.0", owner = "team-authz")
```

WASM exports a `manifest` function that outputs the same fields as JSON, camelCase (`apiVersion`, `fieldMappings`).

**Field mappings.** `fieldMappings` documents what the extension changes in PDP traffic; it is metadata for `/_cerbos/meta` and `/_cerbos/about` only, and Synapse does not enforce it. Each entry has:

| Field | Shape |
|-------|-------|
| `targets` | Map of field path (`principal.attr.department`, `resource.kind`) → target: `TARGET_{CHECK,PLAN}_RESOURCES_{REQUEST,RESPONSE}`, `TARGET_AUTHZEN_EVALUATION[_BATCH]_{REQUEST,RESPONSE}`, or `TARGET_ALL`. One mapping may name several paths. |
| `operation` | `OPERATION_ADD`, `OPERATION_REMOVE`, `OPERATION_OVERWRITE`, `OPERATION_APPEND` |
| `value` | Exactly one of `staticValue` (any JSON value) or `computedValue` (`sources`: list of where the value comes from, e.g. `"metadata.request_id"`; optional `description`) |
| `description` | Optional free text |
| `jsonSchema` | Optional JSON Schema object for the field |
| `metadata` | Optional string → string map |

WASM, JSON output:

```json
{
  "targets": {"principal.attr.department": "TARGET_CHECK_RESOURCES_REQUEST"},
  "description": "Department from the HR data source",
  "operation": "OPERATION_ADD",
  "value": {"computedValue": {"sources": ["hr.department"]}},
  "jsonSchema": {"type": "string"}
}
```

Starlark spells every key in snake_case (`field_mappings`, `static_value`, `computed_value`, `json_schema`); camelCase is rejected (`attribute apiVersion not found in cerbos.tainaron.metadata.v1.Manifest`). Build each mapping and `value` with `struct(...)`, and wrap `json_schema` in `struct(fields = {...})`, since it is a `google.protobuf.Struct`. A plain dict there fails (`attribute type not found in google.protobuf.Struct`), and a dict-built manifest fails on its `field_mappings` list:

```python
def manifest():
    return struct(
        api_version = 1, name = "enrich-principal", version = "1.0.0",
        field_mappings = [
            struct(
                targets = {"principal.attr.department": "TARGET_CHECK_RESOURCES_REQUEST"},
                description = "Department from the HR data source",
                operation = "OPERATION_ADD",
                value = struct(computed_value = struct(sources = ["hr.department"])),
                json_schema = struct(fields = {"type": "string"}),
            ),
            struct(
                targets = {"resource.attr.tenant": "TARGET_CHECK_RESOURCES_REQUEST"},
                operation = "OPERATION_OVERWRITE",
                value = struct(static_value = "acme"),
                metadata = {"team": "authz"},
            ),
        ],
    )
```

**A broken manifest fails silently.** Synapse builds the manifest when `/_cerbos/meta` or `/_cerbos/about` is requested, not when the extension loads. If the conversion fails, the extension stays listed with no `manifest` field, and the error appears only as a `WARN` log line (`Failed to get manifest`). After adding or changing a manifest, check that `curl -s localhost:3594/_cerbos/meta` includes it.

## Gotchas (real-world breakage)

- **Starlark proto maps: no `.get()` / `hasattr()`.** `req.query_params`, `req.headers`, `res.actions`. Use `"key" in map`, `map["key"]`.
- **Starlark headers: canonical case.** `Idempotency-Key`, `X-Approver-Id` — not lowercase. Case-insensitive lookup if client may vary.
- **Starlark `cerbos.cache_set`: string values only.** JSON-encode dicts/structs.
- **TS WASM on js-pdk < 1.6: no `btoa`/`atob`.** Use `Host.arrayBufferToBase64()` / `Host.base64ToArrayBuffer()` + `TextEncoder`/`TextDecoder`; this also works on 1.6+, which added `atob`/`btoa`, `fetch`, `Buffer` and `crypto`. Check `extism-js --version`.
- **TS/JS WASM: every `.d.ts` export needs an implementation.** extism-js stubs unimplemented exports with `unreachable`.
- **TS/JS WASM: camelCase export names** (`cerbosInit`, not `cerbos_init`).
- **Python WASM: pure-Python deps only** — no native C extensions.
- **CEL ternary `A && B ? X : Y`** silently drops attrs in `envoyExternalAuthz.mapping`. Nest ternaries.

## Synapse runtime context

- Default port **`:3594`** (multiplexes gRPC + HTTP + `/ext/`).
- Route extensions get the full path (`/ext/health`), not stripped. Routes may include `{wildcard}` params (`/team-b/{baz}`).
- Extensions configured in `config.yaml` under `extensions:`.
- Distroless image; the binary is `/synapse` (not on `PATH`). Since 0.10 the image's `HEALTHCHECK` runs `/synapse healthcheck`, configured from `SYNAPSE_CONFIG` — see `run-and-test.md` for why that isn't readiness.
- Binary subcommands: `server`, `test`, `starlark repl`, `healthcheck` (0.10+), `helm migrate`.
- `system://sqldb` supports DML on SQLite.
- Proxy extensions: `dataMount` = virtual filesystem path per extension; with global `extensions.dataDir`, files persist across restarts.
- Starlark REPL: `synapse starlark repl [--exec] [SCRIPT_FILE]`.
