# cerbos-epdp-react

Hide the Edit and Delete buttons a user cannot use in a Vite + React +
TypeScript app, deciding in the browser with an embedded PDP, while the Express
API keeps enforcing with its service PDP. The [instruction](instruction.md)
states the need in business terms and gives the Hub deployment ID and the ePDP
rule ID; it does not name a skill or the packages to wire. Exercises
`cerbos-embedded-pdp` (rule ID, Vite `?init` WASM recipe, one module-scope
client, `@cerbos/react` hooks, no credentials in the browser) and its boundary
with server-side enforcement.

What a correct change looks like:

- one `Embedded` client from `@cerbos/embedded-client`, constructed at module
  scope with `policies: { ruleId: "B7XK2M9QPL4R" }` and
  `wasm` from `@cerbos/embedded-server/server.wasm?init`;
- `CerbosProvider` with the signed-in principal and a per-row
  `useCheckResource`/`useIsAllowed` check on kind `document` with the row's
  `owner` and `status`, rendering nothing while loading or on error;
- the Express routes unchanged, still calling the service PDP;
- no Hub client credential (from `cerbos/.env`) anywhere the browser can reach;
- the SDK packages declared in `package.json`.

The Hub rule ID is fictional and the sandbox cannot load a real bundle, so the
browser decisions themselves cannot be observed offline. Deterministic checks
cover everything observable (build, emitted WASM, bundle contents, live API
behaviour against a real PDP); a Codex judge covers the wiring.

## Environment

The image pins Cerbos 0.55.0, Python 3.12 (Debian Bookworm) and Node 22.23.3
(binaries copied from `node:22-bookworm-slim`), all by digest. `/workspace/app`
holds the app with `npm ci` from the committed lockfile (React 19.3.0, Vite
8.3.2, TypeScript 5.9.3, Express 5.2.1, `@cerbos/http` 0.30.1), plus
`@cerbos/embedded-client` 0.8.1, `@cerbos/embedded-server` 0.7.2 and
`@cerbos/react` 0.5.1 installed with `--no-save` (present in `node_modules` and
the npm cache, not declared). `/workspace/cerbos` holds the `document` policy,
a local PDP config, a Hub PDP config and `.env` with a fake Hub client
credential. Judge tooling is installed off the agent's `PATH`: Reward Kit
(`harbor-rewardkit` 0.2.1 and its pinned dependencies in
`environment/judge-requirements.txt`) in `/opt/rewardkit`, and Codex CLI 0.157.0
in `/opt/judge`. Limits: 2 CPUs, 2 GiB RAM, 4 GiB storage, 600 seconds for the
agent, 300 for verification.

## Verification

`tests/test.sh` runs `tests/verify.py` (deterministic), then Reward Kit with
`tests/judge/judge.toml` (Codex judge, `openai/gpt-5.6-luna`, working directory
`/workspace`), then `tests/merge.py`, which writes one key per check and
`reward` = all pass. A criterion the judge fails to score counts as 0.

| Stage | Kind | Requirement |
| --- | --- | --- |
| `typecheck` | deterministic | `tsc -b --force` passes on a fresh copy of the app (no `dist`, image `node_modules`). |
| `build` | deterministic | The `build` script still runs `tsc`, and `npm run build` produces `dist/index.html`. |
| `wasm_bundled` | deterministic | `dist/` holds a byte-identical copy of the installed `@cerbos/embedded-server/server.wasm`, and a bundled script references it by file name (the Vite `?init` recipe emits exactly this). |
| `epdp_rule` | deterministic | The bundled scripts contain the rule ID `B7XK2M9QPL4R` and not the deployment ID; `src/` imports `@cerbos/embedded-client`. |
| `no_secrets_in_bundle` | deterministic | Neither the Hub client ID nor secret appears in `dist/`, `src/`, `index.html`, `vite.config.*` or `app/.env*`, and no `VITE_*SECRET*`/`*CLIENT_ID*`/`*CREDENTIAL*` variable is defined or read there. |
| `dependencies_declared` | deterministic | Every `@cerbos/*` package imported from `src/` is declared in `package.json`. |
| `api_enforcement` | deterministic | Starts `npm run server` against a real PDP twice, each time with a verifier-owned policy set, and calls the API over HTTP. Shipped policy: 6 cases (members edit own, delete own drafts; admins edit/delete all) plus an unauthenticated call. A hidden changed policy (members edit any document in their department; only admins delete): 4 cases that flip relative to the shipped one, proving the API follows the PDP rather than hard-coded rules. Documents are found by owner and status through the API. |
| `epdp_client` | judged | One module-scope `Embedded` client with the rule ID and the `?init` WASM import. |
| `buttons_gated` | judged | Edit/Delete render only when an ePDP check for that row's `edit`/`delete` allows, with kind `document`, the row's `id`, `owner`, `status`, and the user's `id`/`roles`; nothing while loading or on error. |
| `api_enforcement_kept` | judged | PUT and DELETE still call the service PDP before mutating; no browser-supplied decision is trusted; the API is not moved to the ePDP. |
| `no_client_secrets` | judged | No Hub credential or other secret in browser-reachable code or config; the browser client passes no `credentials`. |

## Validated locally

Image built from `environment/`; the verifier (deterministic checks and the
live Codex judge, `CODEX_AUTH_JSON` from `~/.codex/auth.json`) was replayed in
the image with `docker run`, and the oracle and nop also through Harbor 0.23.0.
Every row was run twice, with identical results both times.

| Run | Result | Failing checks |
| --- | --- | --- |
| oracle (`solution/solve.sh`) | 1 | — |
| nop | 0 | `wasm_bundled`, `epdp_rule`, `epdp_client`, `buttons_gated` |
| `hardcoded`: role/ownership comparisons in React, no ePDP | 0 | `wasm_bundled`, `epdp_rule`, `epdp_client`, `buttons_gated` |
| `no-api`: oracle UI, API `allowed()` returns `true` ("the UI hides the buttons now") | 0 | `api_enforcement`, `api_enforcement_kept` |
| `creds`: oracle plus `credentials` from `VITE_CERBOS_HUB_CLIENT_ID`/`SECRET` in `app/.env` | 0 | `no_secrets_in_bundle`, `no_client_secrets` |
| `ungated`: ePDP wired, but both buttons always render (the result only sets a tooltip) | 0 | `buttons_gated` (judge only) |
| `per-render`: `new Embedded(...)` inside the `App` component body | 0 | `epdp_client` (judge only) |

The wrong solutions are kept in `tests/judge-validation/<name>/` with an
`apply.sh`; replay one with the task's `tests/` and `solution/` mounted at
`/tests` and `/solution`:

```bash
docker run --rm -e CODEX_AUTH_JSON="$(cat ~/.codex/auth.json)" -e REWARDKIT_FORCE_SUBSCRIPTION=1 \
  -v "$PWD/evals/tasks/cerbos-epdp-react/tests:/tests:ro" \
  -v "$PWD/evals/tasks/cerbos-epdp-react/solution:/solution:ro" \
  -v /tmp/logs:/logs/verifier <image> \
  bash -c 'bash /tests/judge-validation/ungated/apply.sh && bash /tests/test.sh'
```

## Running

From the repository root with Docker running and a ChatGPT-authenticated Codex
login for the judge:

```bash
export CODEX_AUTH_JSON="$(cat ~/.codex/auth.json)"
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-epdp-react -a oracle
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-epdp-react -a nop
```

The judge calls a model on every verifier run, including oracle and nop.
