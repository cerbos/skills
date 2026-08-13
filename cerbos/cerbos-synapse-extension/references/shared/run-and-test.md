# Running and testing extensions

Start Synapse with your extension loaded; drive it from a test harness. Pattern identical across runtimes — only difference is what you mount and (WASM) the upstream build step.

Contents:

- [Project layout](#project-layout)
- [`config.yaml`](#configyaml)
- [`docker-compose.yaml`](#docker-composeyaml)
- [Running by hand](#running-by-hand)
- [Driving the extension manually](#driving-the-extension-manually) — curl examples per extension kind
- [Automated testing — the built-in framework](#automated-testing--the-built-in-framework) — pointer to `testing-framework.md`
- [HTTP harness patterns — Bash + curl / Hurl](#http-harness-patterns--bash--curl--hurl)
- [Iteration loop](#iteration-loop) — what needs a restart vs hot-reload
- [Debugging Starlark with the REPL](#debugging-starlark-with-the-repl)
- [Common failure modes](#common-failure-modes)

## Project layout

Typical self-contained extension demo:

```
my-extension/
├── config.yaml            # Synapse configuration: PDP + extensions
├── docker-compose.yaml    # Synapse container + bind mounts
├── policies/              # Cerbos policy YAMLs loaded by the embedded PDP
│   └── *.yaml
├── extensions/            # Extension source/binaries mounted into the container
│   ├── *.star             # Starlark — mounted directly, no build
│   ├── *_test.star        # Built-in test suites (synapse test) — see testing-framework.md
│   └── proxy/             # WASM — built before `docker compose up`
│       ├── Makefile       # `make build` produces proxy.wasm
│       └── proxy.wasm
└── test.sh                # Build (if needed), run `synapse test` (or curl/Hurl harness)
```

`extensions/` is the bind-mount the container sees as `/extensions`; `extensionURL` is the path *inside the container*.

## `config.yaml`

Local dev: embedded PDP, policies from disk. `watchForChanges: true` hot-reloads policies on file change:

```yaml
server:
  listenAddress: ":3594"

pdp:
  inProcess:
    storage:
      driver: "disk"
      disk:
        directory: /policies
        watchForChanges: true
    audit:
      enabled: true
      backend: file
      file:
        path: stdout

extensions:
  proxyExtensions:
    enrichPrincipal:
      extensionURL: /extensions/enrich_principal.star
      required: true
  # routeExtensions:
  #   myRoute:
  #     extension:
  #       extensionURL: /extensions/proxy.wasm
  #     routes:
  #       "/check": ["POST"]
  # dataSources:
  #   userProfile:
  #     extension:
  #       extensionURL: /extensions/userprofile.wasm
```

Production: replace `pdp.inProcess` with `pdp.external` to gateway an existing Cerbos PDP fleet, or use the `hub` storage driver to source policies from Cerbos Hub.

`extensionURL` is a local path for development, but also loads over HTTP(S), Git, S3 and GCS. Getter URLs need a runtime prefix — the artefact suffix that normally selects the runtime isn't visible to the loader: `wasm+s3::https://s3.amazonaws.com/bucket/ext.wasm`, `starlark+gcs::https://www.googleapis.com/storage/v1/bucket/ext.star`, `wasm+git::ssh://git@github.com/org/repo//ext.wasm?ref=v1.0.0`. S3 uses the AWS credential chain and GCS uses Application Default Credentials, but only through those getters — a plain HTTPS URL to the same object is fetched unauthenticated. Azure Blob has no getter. Append `?checksum=sha256:<hex>` to pin any URL, local paths included.

## `docker-compose.yaml`

```yaml
services:
  synapse:
    image: CERBOS_DISTRIBUTION_REPO/synapse/synapse:latest
    command:
      - server
      - --conf.path=/config.yaml
      - --log.level=debug
    volumes:
      - ./config.yaml:/config.yaml:ro
      - ./policies:/policies:ro
      - ./extensions/enrich_principal.star:/extensions/enrich_principal.star:ro
      # WASM example — mount the built artefact, not the source:
      # - ./extensions/proxy/proxy.wasm:/extensions/proxy.wasm:ro
    ports:
      - "3594:3594"
```

> **Prerequisite — distribution repository.** Pulling the Synapse image requires a valid Synapse licence. If the user does not already have one, point them to https://cerbos.dev/workshop to sign up. Licence credentials are issued together with the URL of the Cerbos distribution repository. **Before running any `docker`/`docker compose`/`synapse test` command, ask the user for their distribution repository URL** and substitute it wherever `CERBOS_DISTRIBUTION_REPO` appears. Then have them log in and pull:
>
> ```sh
> docker login CERBOS_DISTRIBUTION_REPO --username=YOUR_LICENCE_USER --password=YOUR_LICENCE_KEY
> docker pull CERBOS_DISTRIBUTION_REPO/synapse/synapse:latest
> ```
>
> Pin a specific version (e.g. `:0.9.3`) for stable deployments.

## Running by hand

```sh
docker compose up        # foreground; logs stream to terminal
# or
docker compose up -d     # background
docker compose logs -f synapse
docker compose down -v   # stop and remove volumes
```

Or `docker run` directly, no compose:

```sh
docker run --rm --name synapse -p 3594:3594 \
    -v $(pwd)/config.yaml:/config/config.yaml:ro \
    -v $(pwd)/policies:/policies:ro \
    -v $(pwd)/extensions:/extensions:ro \
    CERBOS_DISTRIBUTION_REPO/synapse/synapse:latest \
    server --conf.path=/config/config.yaml --log.level=debug
```

## Driving the extension manually

Wait for readiness first — `/_cerbos/ready` returns `503` until the PDP is up (`/_cerbos/health` is an alias of it; `/_cerbos/live` reports only that the process is running, `/_cerbos/metrics` is Prometheus). All four answer `GET`; `HEAD` returns `405`.

```sh
curl -sf http://localhost:3594/_cerbos/ready && echo ready
```

Then drive the extension:

```sh
# Proxy extension — calls go through the standard Cerbos API
curl -s -X POST http://localhost:3594/api/check/resources \
  -H 'Content-Type: application/json' \
  -d '{
    "principal": {"id": "alice", "roles": ["employee"]},
    "resources": [{"actions": ["view"],
                   "resource": {"kind": "invoice", "id": "inv-42",
                                "attr": {"company": "Acme"}}}]
  }' | jq .

# Route extension — under /ext/<your-route>
curl -s -X POST http://localhost:3594/ext/check \
  -H 'Content-Type: application/json' \
  -d '{"userId":"alice","action":"view","resourceId":"doc-1"}'

# Plan endpoint
curl -s -X POST http://localhost:3594/api/plan/resources \
  -H 'Content-Type: application/json' \
  -d '{"principal":{"id":"alice","roles":["employee"]},
       "resource":{"kind":"invoice"},"action":"view"}'

# Aperture system route extension
curl -s -X POST http://localhost:3594/ext/aperture \
  -H 'Content-Type: application/json' \
  -d @aperture-hook-payload.json
```

Synapse emits structured JSON logs. Each request: one `access` + one `decision` audit line. The decision entry shows the *inputs the PDP actually evaluated* — start there when an enrichment doesn't apply as expected.

## Automated testing — the built-in framework

Standard approach: built-in runner (`synapse test`) starts a fresh Synapse instance per suite and runs Starlark test functions against it — no compose file, no startup `sleep`, no curl. Tests **any** extension kind, Starlark or WASM (WASM still needs `make build` first — the suite's `synapse_config` references the built `.wasm`). Suite format, `testing` module, `context` helpers, test data files, parameterized tests: `testing-framework.md`.

```sh
docker run \
    --rm --name synapse-test \
    -v $(pwd)/config.yaml:/config/config.yaml:ro \
    -v $(pwd)/policies:/policies:ro \
    -v $(pwd)/extensions:/extensions:ro \
    CERBOS_DISTRIBUTION_REPO/synapse/synapse:latest \
    test /extensions
```

## HTTP harness patterns — Bash + curl / Hurl

For tests against a long-lived compose stack or deployed instance, or languages/CI setups built around HTTP fixtures (Testcontainers and CI "services" also work). A reusable Bash harness keeps individual demos terse. Two common flavours:

### `test.sh` — imperative Bash + `curl`

Good for one-off demos with custom assertions:

```sh
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

passed=0; failed=0
cleanup() { docker compose down -v 2>/dev/null || true; }
trap cleanup EXIT

docker compose up -d
sleep 5

check() {
  local desc=$1 principal_id=$2 roles=$3 kind=$4 id=$5 attr=$6 action=$7 expected=$8
  response=$(curl -sS http://localhost:3594/api/check/resources \
    -H "Content-Type: application/json" -d "{
      \"principal\": {\"id\": \"$principal_id\", \"roles\": $roles},
      \"resources\": [{
        \"resource\": {\"kind\": \"$kind\", \"id\": \"$id\", \"attr\": $attr},
        \"actions\": [\"$action\"]
      }]
    }")
  effect=$(echo "$response" | grep -o "\"$action\":\"[^\"]*\"" | head -1 | cut -d'"' -f4)
  if [[ "$effect" == "$expected" ]]; then
    echo "PASS: $desc"; passed=$((passed+1))
  else
    echo "FAIL: $desc — expected $expected, got $effect"
    echo "  Response: $response"; failed=$((failed+1))
  fi
}

check "alice can view"  alice '["user"]' document doc-1 '{"public":false}' view EFFECT_ALLOW
check "bob cannot edit" bob   '["user"]' document doc-1 '{"public":true}'  edit EFFECT_DENY

echo "Results: $passed passed, $failed failed"
[[ $failed -eq 0 ]] || exit 1
```

### Hurl files — declarative HTTP tests

Better for shared assertions across same-kind extensions. `.hurl` files describe each request + expected response inline:

```hurl
# CheckResources — alice can edit (enriched as admin via dataSourceLookup)
POST http://localhost:3594/api/check/resources
Content-Type: application/json
{"principal":{"id":"alice","roles":["user"]},
 "resources":[{"resource":{"kind":"document","id":"doc1","attr":{"public":false}},
               "actions":["edit"]}]}
HTTP 200
[Asserts]
jsonpath "$.results[0].actions.edit" == "EFFECT_ALLOW"

# Cached lookup — second call uses cache
POST http://localhost:3594/api/check/resources
Content-Type: application/json
{"principal":{"id":"alice","roles":["user"]},
 "resources":[{"resource":{"kind":"document","id":"doc1","attr":{"public":false}},
               "actions":["edit"]}]}
HTTP 200
[Asserts]
jsonpath "$.results[0].actions.edit" == "EFFECT_ALLOW"
```

Run: `hurl --test --retry 3 --retry-interval 2000 test-proxy.hurl`. Retries cover the brief startup window when Synapse isn't quite ready.

### Reusable harness

For multiple demos, share the boilerplate:

```sh
# _test-lib/harness.sh
HARNESS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cleanup() { docker compose down -v 2>/dev/null || true; }
trap cleanup EXIT

start_synapse() {
  docker compose up -d
  for _ in $(seq 30); do
    curl -sf http://localhost:3594/_cerbos/ready >/dev/null && return 0
    sleep 1
  done
  echo "Synapse did not become ready" >&2
  docker compose logs synapse >&2
  return 1
}

run_tests() {
  local test_type=$1
  hurl --test --retry 3 --retry-interval 2000 "$HARNESS_DIR/test-${test_type}.hurl"
}
```

Then each demo's `test.sh` becomes:

```sh
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
source "$SCRIPT_DIR/../_test-lib/harness.sh"

# WASM only — build before starting Synapse so the .wasm is on disk:
cd extensions/proxy && make build && cd "$SCRIPT_DIR"

start_synapse
run_tests proxy        # uses _test-lib/test-proxy.hurl
```

## Iteration loop

| You changed... | What happens |
|----------------|--------------|
| A Cerbos policy YAML | Hot-reloaded if `watchForChanges: true` is set on the disk driver. No restart. |
| A Starlark `.star` file | Synapse loads a fresh script instance per request — restart of the container is required to pick up the new file because the extension URL is cached on startup. Use `docker compose restart synapse`. |
| `config.yaml` | Restart Synapse. |
| A WASM source file | Rebuild the `.wasm` (`make build`), then restart Synapse so the new module is loaded. |
| Adding a new extension | Update `config.yaml`, restart. |

`synapse test` sidesteps the restart cycle entirely — every run provisions a fresh instance per suite from the suite's `synapse_config`, so edited `.star` files, rebuilt `.wasm` modules, and config changes are always picked up on the next `test` invocation.

## Debugging Starlark with the REPL

Built-in REPL runs Starlark logic outside the request flow — fastest way to test helper functions or experiment with stdlib calls:

```sh
docker compose exec synapse synapse starlark repl
# Inside the REPL:
>>> load("my_extension.star", "my_extension")
>>> my_extension.helper("test-input")
```

`synapse starlark repl --exec script.star` executes and exits — handy for scripted smoke tests. REPL inherits the same modules (`json`, `http`, `oauth`, `stats`, etc.) as the request path.

## Common failure modes

- **Synapse container exits immediately**: check `docker compose logs synapse` for a config schema error. Common causes: invalid `extensionURL` path (must match the bind mount), missing PDP licence, malformed YAML.
- **Extension not invoked**: routing only fires on the configured kind. Proxy extensions only see `CheckResources` / `PlanResources` / AuthZEN traffic — never `/ext/...` calls. Route extensions only fire on paths listed under `routes:`.
- **WASM module imports unresolved**: check `docker compose logs synapse | grep -i 'unreachable\|extension\|wasm'`. TypeScript/Python WASM: all `.d.ts`-declared exports must have implementations — declaring `cerbosInit` without implementing it crashes the module on load.
- **Decision is wrong, extension isn't logging**: enable `--log.level=debug` (on in examples above), grep for the extension name. The `decision` audit line shows the *enriched* request the PDP evaluated — confirm the attributes the extension added are present there.
- **Tests are flaky on startup** (curl/Hurl harness only): poll `GET /_cerbos/ready` instead of sleeping (see `start_synapse` above); `hurl --retry 3 --retry-interval 2000` covers the rest. `synapse test` waits for readiness itself — no such problem.
- **`synapse test` passes but the extension never ran**: suite has no `synapse_config` (default config loads no extensions) or the config doesn't register the extension. Add `synapse_config = testing.load_synapse_config(...)` pointing at a config that loads it; use `--verbose` to confirm the extension fires.
