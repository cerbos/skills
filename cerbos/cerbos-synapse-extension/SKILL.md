---
name: cerbos-synapse-extension
description: Builds, scaffolds, tests, debugs, and troubleshoots Cerbos Synapse extensions — call mappers, data sources, proxy extensions, route extensions, Envoy ext_authz extensions — in declarative YAML/CEL, Starlark, or WASM (Go, TypeScript/extism-js, Python/extism-py). Covers principal enrichment, attribute lookup, AuthZEN, protocol adapters, custom /ext/ endpoints, system://sqldb and system://aperture, synapse test suites (*_test.star), the Starlark REPL, config.yaml extension wiring, and docker-compose local dev. Use when the user mentions Synapse extensions, "add custom logic to Synapse", enriching principals/resources, mapping HTTP or Envoy traffic to Cerbos checks, writing or running Synapse extension tests, or an extension not loading/firing.
metadata:
  author: cerbos
  version: "1.1"
  compatibility: Cerbos Synapse
  targetsSynapseVersion: "0.9.3"
---

# Cerbos Synapse Extension

Synapse extends the Cerbos authorization pipeline. Five extension **kinds** × multiple **runtimes**. Pick kind → runtime → load the matching reference.

## Extension Kinds

| Kind | Purpose | Entry points |
|------|---------|--------------|
| **Call mapper** | HTTP ↔ Cerbos mapping. CEL only, no code. | `routeExtensions.builtinRouteExtension` routes or `envoyExternalAuthz` in `config.yaml` |
| **Data source** | Attribute lookups for other extensions. | Export `lookup`; consumed via `cerbos.data_source_lookup()` (Starlark) / `dataSourceLookup` (WASM) |
| **Proxy extension** | Modify CheckResources / PlanResources / AuthZEN requests+responses. | `augment{Check,Plan,AuthzenEvaluation,AuthzenEvaluationBatch}{Request,Response}` (Starlark: `snake_case`) |
| **Route extension** | Custom HTTP endpoints under `/ext/`. | `handleHTTPRoute`, optional `handleCerbosResponse` callback (Starlark: `handle_http_route` / `handle_cerbos_response`) |
| **Envoy extension** | Envoy ext_authz → Cerbos. | `envoyCheck`, optional `envoyMapCerbosResponse` callback (Starlark: `envoy_check` / `map_cerbos_response` — **not** `envoy_map_cerbos_response`) |

## Runtimes

| Runtime | Build | Perf | Libraries | Best for |
|---------|-------|------|-----------|----------|
| **Declarative (CEL in YAML)** | None | High | CEL stdlib | Call mapper only |
| **Starlark** | None — `.star` file | Lower (interpreter) | Built-in modules (`http`, `json`, `base64`, `time`, `re`, `hashlib`, `csv`, `random`, `string`) | Prototyping, simple lookups, no build step |
| **WASM (Go / TS / Python)** | Compile to `.wasm` | High | npm, Go modules, pure-Python | Compiled perf, library deps, production adapters |

## Decision flow

1. **Static HTTP → Cerbos mapping, CEL enough** (headers, JWT claims, JSON body, ternaries)? → call mapper, no code. → `references/call-mapper.md`
2. Else pick kind: data source / proxy / route / envoy.
3. Pick runtime:
   - **Starlark** — built-in modules suffice; iteration speed > peak perf
   - **WASM** — compiled perf, third-party libs, existing codebase. Language: **Go** (`tidwall/gjson`/`sjson`, typing) · **TS** (`@extism/js-pdk` + esbuild; no `btoa`/`atob` — `Host.arrayBufferToBase64()`) · **Python** (`extism-py`; pure-Python only; `wasm-merge` shim step)

| Kind | CEL | Starlark | WASM Go | WASM JS | WASM Py |
|------|:---:|:---:|:---:|:---:|:---:|
| Call mapper | ✓ | — | — | — | — |
| Data source | — | ✓ | ✓ | ✓ | ✓ |
| Proxy | — | ✓ | ✓ | ✓ | ✓ |
| Route | — | ✓ | ✓ | ✓ | ✓ |
| Envoy | ✓ (`envoyExternalAuthz`) | ✓ | ✓ | ✓ | — |

Before writing custom: `system://sqldb` (SQL data source), `system://aperture` (Tailscale Aperture → Cerbos) and `system://claude` (Claude Code hooks → Cerbos) may already fit → `references/shared/system-extensions.md`.

## References

Per-implementation (pick one):

| Reference | When |
|-----------|------|
| `references/call-mapper.md` | Declarative call mapper |
| `references/starlark-{data-source,proxy-extension,route-extension,envoy-extension}.md` | Starlark, by kind |
| `references/wasm-data-source-{go,javascript,python}.md` | WASM data source |
| `references/wasm-proxy-extension-{go,javascript,python}.md` | WASM proxy |
| `references/wasm-route-extension-{go,javascript,python}.md` | WASM route |
| `references/wasm-envoy-extension-{go,javascript}.md` | WASM Envoy (no Python) |

Shared (load alongside):

| Reference | When |
|-----------|------|
| `references/shared/run-and-test.md` | **Always, before authoring a demo.** Layout, `config.yaml`, compose, curl, iteration loop, REPL, failure modes. |
| `references/shared/testing-framework.md` | **When writing tests.** `synapse test`, `*_test.star` suites, `test_suite` struct, `testing` module, `context` helpers, test data. |
| `references/shared/patterns-and-gotchas.md` | **Always, before writing extension code.** Caching, data source lookup, enrichment, proxy chain + route match ordering, callback mode, lifecycle, runtime gotchas, runtime context facts. |
| `references/shared/starlark-environment.md` | All Starlark — host functions, modules, proto-map gotchas. |
| `references/shared/go-wasm-common.md` | All Go WASM — `extism/go-pdk` host imports. |
| `references/shared/typescript-wasm-common.md` | All TS WASM — d.ts rules, base64 workaround. |
| `references/shared/python-wasm-common.md` | All Python WASM — build pipeline, PDK shim, memory helpers. |
| `references/shared/system-extensions.md` | Using `system://sqldb` / `system://aperture`. |
| `references/shared/call-mapper-cel-reference.md` | Call mapper CEL functions/variables. |
| `references/shared/call-mapper-examples.md` | Call mapper examples (REST, Envoy). |

## Running and testing (quick facts)

- **Distribution repo — ask first.** The Synapse image lives in a licensed Cerbos distribution repository. **Before running any `docker` / `docker compose` / `synapse test` command, ask the user for their distribution repository URL** and substitute it for `CERBOS_DISTRIBUTION_REPO` everywhere. No licence yet → sign up at https://cerbos.dev/workshop; credentials are issued with the repo URL. Log in (`docker login CERBOS_DISTRIBUTION_REPO --username=YOUR_LICENCE_USER --password=YOUR_LICENCE_KEY`) before pulling.
- Image `CERBOS_DISTRIBUTION_REPO/synapse/synapse:<version>`, port `3594`, distroless. Subcommands: `server`, `test`, `starlark repl`.
- Local dev: embedded PDP (`pdp.inProcess`, `disk` storage, `watchForChanges: true` hot-reloads policies); extensions under `extensions.{proxyExtensions,routeExtensions,dataSources}.<name>` in `config.yaml`; bind-mount `config.yaml`, `policies/`, `extensions/`.
- WASM: `make build` before start — mount the built `.wasm`, not source. `.star`/`.wasm`/config edits need container restart.
- Drive: `/api/check/resources`, `/api/plan/resources`, `/ext/<path>`, Envoy ext_authz gRPC. Wait on `GET /_cerbos/ready` before driving.
- Tests: `synapse test <paths>` runs `*_test.star` suites — fresh instance per suite, no restart cycle. Details: `references/shared/testing-framework.md`.
