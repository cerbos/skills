# Cross-cutting patterns and gotchas

Patterns recurring across runtimes. Per-implementation references show exact code; this explains the shape.

## Patterns

**Caching.** All runtimes: `cacheGet` / `cacheSet` / `cacheDelete` (+ `cacheSetIfNotExists` in WASM). Durations: `time.minute` (Starlark), **milliseconds** (WASM). Starlark values must be JSON-encoded strings; WASM stores raw bytes.

**Data source lookup.** Proxy/route/envoy call a configured data source by name: `cerbos.data_source_lookup(datasource, query)` (Starlark), `dataSourceLookup(json)` (WASM host import). Response: `{ result: <any> }`. Starlark: JSON round-trip `json.decode(json.encode(resp.result))` to safely extract proto struct fields.

**Principal enrichment (proxy).** Read request → extract `principal.id` → cache lookup → on miss, data source → merge into `principal.attr` → return modified request.

**Proxy pipeline ordering.** Onion order — same for Check, Plan and AuthZEN: requests run in descending `priority`, responses back in reverse, so the highest priority sees the request first and the response last. Equal priorities tie-break on FQN (`proxy.<name>.<hash>`, descending) — **give each extension a distinct `priority` when order matters**. `required: true` → failure terminates chain; else skipped. **PDP calls from extension code (`cerbos.check_resources()` etc.) bypass the proxy pipeline** — prevents re-entry loops; enrichment for those calls must happen in the extension itself (or shared data source).

**Route matching order.** Path patterns are global across every route extension and match in the order written in `config.yaml` — **first match wins** — so declare specific patterns before overlapping wildcards (`"/docs/latest"` before `"/docs/{id}"`). That order holds within one extension's `routes:` map; across extensions an identical pattern is a startup error, while overlapping-but-different patterns have no reliable precedence. Keep patterns that can overlap inside a single extension.

**OAuth upstreams (Starlark).** Use `oauth.client_credentials_client(...)`, not hand-rolled `http.post` to token endpoint. Pass `persist_key` to reuse the client across requests — else re-auth per invocation. See `starlark-environment.md`.

**Callback mode (route/envoy).** Return `cerbosCheckRequest` from `handleHTTPRoute` / `envoyCheck`. Synapse calls the PDP, then `handleCerbosResponse` / `envoyMapCerbosResponse` with original request + decision. Extension shapes final response after seeing verdict. Starlark names differ: `handle_cerbos_response` (route) and `map_cerbos_response` (envoy — not `envoy_map_cerbos_response`).

**Lifecycle.** WASM may export `cerbosInit` (module load) / `cerbosDeinit` (unload). One-time setup. JS/Python: **declaring without implementing crashes the module** (extism generates broken stub). Only declare what you implement.

## Gotchas (real-world breakage)

- **Starlark proto maps: no `.get()` / `hasattr()`.** `req.query_params`, `req.headers`, `res.actions`. Use `"key" in map`, `map["key"]`.
- **Starlark headers: canonical case.** `Idempotency-Key`, `X-Approver-Id` — not lowercase. Case-insensitive lookup if client may vary.
- **Starlark `cerbos.cache_set`: string values only.** JSON-encode dicts/structs.
- **TS WASM: no `btoa`/`atob`.** `Host.arrayBufferToBase64()` / `Host.base64ToArrayBuffer()` + `TextEncoder`/`TextDecoder`.
- **TS/JS WASM: every `.d.ts` export needs an implementation.** extism-js stubs unimplemented exports with `unreachable`.
- **TS/JS WASM: camelCase export names** (`cerbosInit`, not `cerbos_init`).
- **Python WASM: pure-Python deps only** — no native C extensions.
- **CEL ternary `A && B ? X : Y`** silently drops attrs in `envoyExternalAuthz.mapping`. Nest ternaries.

## Synapse runtime context

- Default port **`:3594`** (multiplexes gRPC + HTTP + `/ext/`).
- Route extensions get the full path (`/ext/health`), not stripped. Routes may include `{wildcard}` params (`/team-b/{baz}`).
- Extensions configured in `config.yaml` under `extensions:`.
- Distroless image — no shell-based healthcheck.
- Binary subcommands: `server`, `test`, `starlark repl`.
- `system://sqldb` supports DML on SQLite.
- Proxy extensions: `dataMount` = virtual filesystem path per extension; with global `extensions.dataDir`, files persist across restarts.
- Starlark REPL: `synapse starlark repl [--exec] [SCRIPT_FILE]`.
