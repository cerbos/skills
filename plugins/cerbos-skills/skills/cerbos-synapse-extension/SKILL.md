---
name: cerbos-synapse-extension
description: Builds, scaffolds, tests, debugs, and troubleshoots Cerbos Synapse extensions — call mappers, data sources, proxy extensions, route extensions, Envoy ext_authz extensions — in declarative YAML/CEL, Starlark, or WASM (Go, TypeScript/extism-js, Python/extism-py). Covers principal enrichment, attribute lookup, AuthZEN, protocol adapters, custom /ext/ endpoints, system://sqldb and system://aperture, synapse test suites (*_test.star), the Starlark REPL, config.yaml extension wiring, and docker-compose local dev. Use when the user mentions Synapse extensions, "add custom logic to Synapse", enriching principals/resources, mapping HTTP or Envoy traffic to Cerbos checks, writing or running Synapse extension tests, or an extension not loading/firing.
license: Apache-2.0
compatibility: Cerbos Synapse, run from its licensed distribution image
metadata:
  author: cerbos
  version: "1.4"
  targetsSynapseVersion: "0.10.2"
---

# Cerbos Synapse Extension

Synapse extends the Cerbos authorization pipeline. Five extension **kinds** × multiple **runtimes**. Pick kind → runtime → load the matching reference.

## Scope

This skill owns Synapse extensions of every kind and runtime, their `*_test.star` suites, and the extension wiring in Synapse `config.yaml` and local compose files. Call mapper CEL lives here too.

Route adjacent work elsewhere:

- Policies the extension's requests are evaluated against, including their `*_test.yaml` suites and CEL conditions, belong to `cerbos-policy`. When an extension adds attributes that a rule reads, write the extension here and the rule there.
- Application code that calls Synapse or the PDP belongs to `cerbos-pep-integration`; use this skill for the extension code and configuration.
- Standing up Cerbos Hub and its deployments belongs to `cerbos-hub-setup`; pointing Synapse's in-process PDP at a deployment stays here (`references/shared/hub.md`).

## Extension Kinds

| Kind | Purpose | Entry points |
|------|---------|--------------|
| **Call mapper** | HTTP ↔ Cerbos mapping. CEL only, no code. | A `mapping:` block under any `routeExtensions.<name>` (name is arbitrary), or `envoyExternalAuthz`, in `config.yaml` |
| **Data source** | Attribute lookups for other extensions. | Export `lookup`; consumed via `cerbos.data_source_lookup()` (Starlark) / `dataSourceLookup` (WASM) |
| **Proxy extension** | Modify CheckResources / PlanResources / AuthZEN requests+responses. | `augment{Check,Plan,AuthzenEvaluation,AuthzenEvaluationBatch}{Request,Response}` (Starlark: `snake_case`) |
| **Route extension** | Custom HTTP endpoints under `/ext/`. | `handleHTTPRoute`, optional `handleCerbosResponse` callback (Starlark: `handle_http_route` / `handle_cerbos_response`) |
| **Envoy extension** | Envoy ext_authz → Cerbos. | `envoyCheck`, optional `envoyMapCerbosResponse` callback (Starlark: `envoy_check` / `map_cerbos_response` — **not** `envoy_map_cerbos_response`) |

Every coded kind may also export an optional `manifest` (0.10+), listed at `/_cerbos/meta` → `references/shared/patterns-and-gotchas.md`.

## Runtimes

| Runtime | Build | Perf | Libraries | Best for |
|---------|-------|------|-----------|----------|
| **Declarative (CEL in YAML)** | None | High | CEL stdlib | Call mapper only |
| **Starlark** | None — `.star` file | Lower (interpreter) | `load()`able modules (`http`, `json`, `base64`, `re`, `hashlib`, `csv`, `random`, `string`, `oauth`, `stats`); `time`, `math` predeclared | Prototyping, simple lookups, no build step |
| **WASM (Go / TS / Python)** | Compile to `.wasm` | High | npm, Go modules, pure-Python | Compiled perf, library deps, production adapters |

## Decision flow

1. **Static HTTP → Cerbos mapping, CEL enough** (headers, JWT claims, JSON body, ternaries)? → call mapper, no code. → `references/call-mapper.md`
2. Else pick kind: data source / proxy / route / envoy.
3. Pick runtime:
   - **Starlark** — built-in modules suffice; iteration speed > peak perf
   - **WASM** — compiled perf, third-party libs, existing codebase. Language: **Go** (`tidwall/gjson`/`sjson`, typing) · **TS** (`@extism/js-pdk` + esbuild; js-pdk < 1.6 has no `btoa`/`atob` — `Host.arrayBufferToBase64()`) · **Python** (`extism-py`; pure-Python only; `wasm-merge` shim step)

| Kind | CEL | Starlark | WASM Go | WASM JS | WASM Py |
|------|:---:|:---:|:---:|:---:|:---:|
| Call mapper | ✓ | — | — | — | — |
| Data source | — | ✓ | ✓ | ✓ | ✓ |
| Proxy | — | ✓ | ✓ | ✓ | ✓ |
| Route | — | ✓ | ✓ | ✓ | ✓ |
| Envoy | ✓ (`envoyExternalAuthz`) | ✓ | ✓ | ✓ | no reference* |

\*The docs don't limit Envoy extensions by language, but this skill has no Python Envoy reference and it is untested; adapt the Go/JS Envoy reference with the Python build pipeline.

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
| `references/wasm-envoy-extension-{go,javascript}.md` | WASM Envoy (no Python reference) |

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
| `references/shared/system-extensions.md` | Using `system://sqldb` / `system://aperture` / `system://claude`. |
| `references/shared/call-mapper-cel-reference.md` | Call mapper CEL functions/variables. |
| `references/shared/call-mapper-examples.md` | Call mapper examples (REST, Envoy). |
| `references/sources.md` | Updating this skill for a new Synapse release: the docs and tools it is checked against. |

## Running and testing (quick facts)

- **Distribution repo — ask first.** The Synapse image lives in a licensed Cerbos distribution repository. **Before running any `docker` / `docker compose` / `synapse test` command, ask the user for their distribution repository URL** and substitute it for `CERBOS_DISTRIBUTION_REPO` everywhere. Licence keys are issued per organization from **Distribution licence** in Cerbos Hub organization settings, together with the repository URL — see [Distribution licence](https://docs.cerbos.dev/cerbos-hub/distribution-licence?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-synapse-extension_hub-distribution-licence) and [managing licence keys](https://docs.cerbos.dev/synapse/latest/install/licence-keys?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-synapse-extension_synapse-install-licence-keys). No Cerbos Hub organization yet → https://cerbos.dev/workshop?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-synapse-extension_workshop. Log in (`docker login CERBOS_DISTRIBUTION_REPO --username=YOUR_LICENCE_USER --password=YOUR_LICENCE_KEY`) before pulling.
- Image `CERBOS_DISTRIBUTION_REPO/synapse/synapse:<version>`, port `3594`, distroless; binary `/synapse`. Subcommands: `server`, `test`, `starlark repl`, `healthcheck` (0.10+), `helm migrate`. Pass the config via `SYNAPSE_CONFIG`, not `--conf.path`, so the image's built-in healthcheck reads it too.
- Local dev: embedded PDP (`pdp.inProcess`, `disk` storage, `watchForChanges: true` hot-reloads policies); extensions under `extensions.{proxyExtensions,routeExtensions,dataSources}.<name>` in `config.yaml`; bind-mount `config.yaml`, `policies/`, `extensions/`.
- WASM: build the `.wasm` before start (steps per language in the matching `shared/*-wasm-common.md`) and point `extensionURL` at the artefact, not source. `.star`/`.wasm`/config edits need container restart.
- Drive: `/api/check/resources`, `/api/plan/resources`, `/ext/<path>`, Envoy ext_authz gRPC. Wait on `GET /_cerbos/ready` before driving — a `healthy` Docker status is not readiness.
- Tests: `synapse test <paths>` runs `*_test.star` suites — fresh instance per suite, no restart cycle. Details: `references/shared/testing-framework.md`.
- **Production policies and audit come from Cerbos Hub.** Disk storage suits local dev; in production point the in-process PDP at a Hub deployment and send its audit trail back. The enrichment story is the reason it matters here: the decision entry records the request *after* proxy extensions ran, so attributes an extension fetched are in the audit record and searchable in Hub, annotated with the Synapse version and the extensions that ran. Config and the gotchas: `references/shared/hub.md`.
