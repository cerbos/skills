# Local skill evals

These native [Harbor tasks](https://www.harborframework.com/docs/tasks) evaluate
the `cerbos-policy` skill against distinct policy authoring workflows, smoke
test the `cerbos-synapse-extension` skill, and cover the rest of the skill set
across the authorization lifecycle.

| Task | Coverage |
| --- | --- |
| [`cerbos-policy-files`](tasks/cerbos-policy-files/README.md) | Generate document/invoice policies from business requirements, including schemas, fixtures and tests. |
| [`cerbos-policy-evolution`](tasks/cerbos-policy-evolution/README.md) | Change existing permissions while preserving unaffected behavior and regression tests. |
| [`cerbos-policy-derived-roles`](tasks/cerbos-policy-derived-roles/README.md) | Share conditional derived roles across resources, with parent-role and tenant boundaries. |
| [`cerbos-policy-variables`](tasks/cerbos-policy-variables/README.md) | Manage shared exported variables and policy-local variables while preserving authorization behavior. |
| [`cerbos-policy-hierarchy`](tasks/cerbos-policy-hierarchy/README.md) | Build a scoped policy hierarchy with narrowing-only and overriding scopes, multi-level chains, and multi-role principals. |
| [`cerbos-policy-tests-schemas`](tasks/cerbos-policy-tests-schemas/README.md) | Add attribute schemas with reject-mode enforcement and `create` exemptions, plus native test suites using shared fixture files and inline fixtures. |
| [`cerbos-policy-role-policies`](tasks/cerbos-policy-role-policies/README.md) | Define scoped custom roles with role policies, parent roles, and a narrowed IdP role over unchanged base resource policies. |
| [`cerbos-policy-outputs`](tasks/cerbos-policy-outputs/README.md) | Add `ruleActivated` and `conditionNotMet` outputs for audit events and denial reasons, and assert them in native tests. |
| [`cerbos-policy-repair`](tasks/cerbos-policy-repair/README.md) | Repair a bundle with a compile error, a boundary bug caught by a seed test, and an explicit DENY that silently no-ops on an absent attribute, keeping the seed tests. |
| [`cerbos-policy-principal-exceptions`](tasks/cerbos-policy-principal-exceptions/README.md) | Add a principal policy with a time-limited grant and a per-user DENY, plus a JWT claim condition, tested with `options.now` and `auxData` fixtures. |
| [`cerbos-policy-files-no-python`](tasks/cerbos-policy-files-no-python/README.md) | `cerbos-policy-files` in a sandbox where the agent cannot run Python, exercising the coverage audit's manual fallback. |

Synapse smoke tasks cover the `cerbos-synapse-extension` skill across extension kinds
and runtimes. Each task writes one extension, wires it into `config.yaml`, proves it
with a `synapse test` suite, and is checked against real Synapse decisions:

| Kind | Starlark | Go WASM | JS/TS WASM | Python WASM |
| --- | --- | --- | --- | --- |
| Proxy: enrich principals before CheckResources | [`cerbos-synapse-proxy-starlark`](tasks/cerbos-synapse-proxy-starlark/README.md) | [`cerbos-synapse-proxy-wasm-go`](tasks/cerbos-synapse-proxy-wasm-go/README.md) | [`cerbos-synapse-proxy-wasm-js`](tasks/cerbos-synapse-proxy-wasm-js/README.md) | [`cerbos-synapse-proxy-wasm-python`](tasks/cerbos-synapse-proxy-wasm-python/README.md) |
| Route: `GET /ext/documents` answered by the PDP | [`cerbos-synapse-route-starlark`](tasks/cerbos-synapse-route-starlark/README.md) | [`cerbos-synapse-route-wasm-go`](tasks/cerbos-synapse-route-wasm-go/README.md) | [`cerbos-synapse-route-wasm-js`](tasks/cerbos-synapse-route-wasm-js/README.md) | [`cerbos-synapse-route-wasm-python`](tasks/cerbos-synapse-route-wasm-python/README.md) |
| Envoy: ext_authz for `GET /documents/<id>` | [`cerbos-synapse-envoy-starlark`](tasks/cerbos-synapse-envoy-starlark/README.md) | | | |

The task folders are generated: edit the sources in [`synapse/`](synapse/generate.py)
and run `python3 evals/synapse/generate.py`; CI fails when they drift. Before running a
Synapse task, run any task's `prepare-image.sh` once to tag the licensed Synapse image
locally, and pass `--skill ./plugins/cerbos-skills/skills/cerbos-synapse-extension`. Run all of them with
`-p evals/tasks -i '*cerbos-synapse-*'`. The Python WASM tasks build linux/amd64
images because `extism-py` ships for x86_64 only; they run emulated on arm64 hosts.

## Lifecycle tasks

These tasks cover the other six skills. Their instructions never name a skill, so
run them with every skill installed (one `--skill` per directory under `plugins/cerbos-skills/skills/`)
and routing between skills is part of what they test.

| Task | Skill | Coverage |
| --- | --- | --- |
| [`cerbos-pep-python-checks`](tasks/cerbos-pep-python-checks/README.md) | `cerbos-pep-integration` | Add PDP checks to a FastAPI service's endpoints with the Python SDK, mapping stored fields onto the attributes the policy reads, and fail closed when the PDP is down. |
| [`cerbos-pep-python-list-filter`](tasks/cerbos-pep-python-list-filter/README.md) | `cerbos-pep-integration` | Filter a paged SQLAlchemy list endpoint with `planResources` and the query-plan adapter, including always-allowed and always-denied plans. |
| [`cerbos-migrate-inline-checks`](tasks/cerbos-migrate-inline-checks/README.md) | `cerbos-authz-migration` | Move a Flask app's scattered role checks, `can()` helper, ownership, plan-gated feature and suspended-account guard to Cerbos with identical status codes. |
| [`cerbos-migrate-rego`](tasks/cerbos-migrate-rego/README.md) | `cerbos-authz-migration` | Translate an ordered OPA/Rego `else` chain with data-driven grants into Cerbos policies and tests, matching OPA's decisions. |
| [`cerbos-audit-masking`](tasks/cerbos-audit-masking/README.md) | `cerbos-audit-insights` | Enable decision and access logs to a local file with PII, tokens and secret headers masked and noisy plan decisions filtered. |
| [`cerbos-audit-debug`](tasks/cerbos-audit-debug/README.md) | `cerbos-audit-insights` | Use a seeded audit log to find why managers cannot approve invoices and fix the PEP without loosening the policy. |
| [`cerbos-hub-pdp-config`](tasks/cerbos-hub-pdp-config/README.md) | `cerbos-hub-setup` | Switch a compose PDP from disk policies to a Hub deployment without writing the client secret to any file; checked against a fake Hub. |
| [`cerbos-hub-ci-upload`](tasks/cerbos-hub-ci-upload/README.md) | `cerbos-hub-setup` | Add CI that validates policies on pull requests and uploads them to a Hub store on merge to main; run through a GitHub Actions emulator and a fake Hub. |
| [`cerbos-epdp-react`](tasks/cerbos-epdp-react/README.md) | `cerbos-embedded-pdp` | Gate a Vite/React app's buttons with the embedded PDP while the API keeps enforcing; build checks plus an LLM judge. |
| [`cerbos-router-react-multitenant`](tasks/cerbos-router-react-multitenant/README.md) | `cerbos` | Design note for per-tenant rules, API enforcement and UI hints; LLM judge. |
| [`cerbos-router-envoy-hr-attributes`](tasks/cerbos-router-envoy-hr-attributes/README.md) | `cerbos` | Design note for gateway authorization with attributes held in an HR database; LLM judge. |
| [`cerbos-router-mcp-agent-tools`](tasks/cerbos-router-mcp-agent-tools/README.md) | `cerbos` | Design note for authorizing an AI agent's MCP tool calls on behalf of users; LLM judge. |

The judged tasks run a Codex judge through Reward Kit in the verifier and authenticate
with a ChatGPT login: export `CODEX_AUTH_JSON="$(cat ~/.codex/auth.json)"` before
`harbor run`. Every judged task also has deterministic checks, and its README records
the judge's results on the oracle, nop and hand-written wrong answers kept in
`tests/judge-validation/`.

## Task layout

```text
evals/tasks/cerbos-policy-files/
  instruction.md          Request given to the agent
  task.toml               Task identity, limits and output artifacts
  environment/Dockerfile  Cerbos and Python runtime
  solution/solve.sh       Copies the reference bundle into the workspace
  solution/policies/      Static YAML/JSON reference bundle used by oracle
  tests/                  Independent verifier and decision fixtures
```

Harbor builds the Docker environment, runs the selected agent, then uploads and
runs `tests/test.sh`, which launches `tests/verify.py`. The tests assess the generated files; they are not part of
the agent's instructions. Everything needed to run each task is inside its
folder. Tasks that modify existing policies also include a starting bundle in
`environment/`. Cerbos runs directly in the container; Docker-in-Docker is unnecessary.

## Run

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and start
Docker. Run commands from the repository root, using a fresh job name each time.

Check the reference solution (expected reward 1):

```bash
uvx --from harbor==0.23.0 harbor run \
  -p evals/tasks/cerbos-policy-files -a oracle \
  --jobs-dir evals/jobs --job-name policy-oracle
```

Check an unfinished attempt (expected overall reward 0):

```bash
uvx --from harbor==0.23.0 harbor run \
  -p evals/tasks/cerbos-policy-files -a nop \
  --jobs-dir evals/jobs --job-name policy-nop
```

Evaluate the skill with model credentials configured:

```bash
uvx --from harbor==0.23.0 harbor run \
  -p evals/tasks/cerbos-policy-files \
  --skill ./plugins/cerbos-skills/skills/cerbos-policy \
  -a codex --agent-kwarg version=0.154.0 -m openai/gpt-5.6-luna \
  --jobs-dir evals/jobs --job-name policy-live
```

Replace `cerbos-policy-files` in these commands with any task in the table above
and choose a distinct job name. Oracle and nop check the task itself. For tasks
with a starting bundle, nop leaves it unchanged; individual checks may pass,
but overall reward must be 0. The real-agent run measures how well the skill
helps complete the task. No model is called until that command is run.

Codex authenticates with `OPENAI_API_KEY`; set `CODEX_FORCE_AUTH_JSON=1` to use
`~/.codex/auth.json` instead. To run every policy task in one job, pass `-p evals/tasks -i '*cerbos-policy-*'`.
Harbor installs the agent in each container, which can exceed the 360-second
setup limit when several trials start together; add
`--agent-setup-timeout-multiplier 4` rather than raising the agent timeout.

Each concurrent trial needs about 1 GB of free disk while Harbor installs the
agent. When the disk fills, setup fails with `No space left on device` or Codex
exits with `Missing optional dependency @openai/codex-linux-x64`, and the trial
reports `NonZeroAgentExitCodeError` instead of a score. Check `df -h` before a
long run (`docker builder prune` reclaims unused build cache), and add
`-r 2 --retry-include NonZeroAgentExitCodeError` so these setup crashes are
retried. Agent timeouts and verifier failures raise other exceptions and are not
retried.

To try a different skill checkout, change `--skill` and use a fresh job name.
Use `--n-attempts 3` to repeat the same task three times. When comparing skill
versions locally, keep the task, model, agent version and attempt count the same.

## New Cerbos releases

When a new PDP version ships, run from the repository root with Docker running:

```bash
uv run --no-project --with PyYAML==6.0.2 python evals/update_cerbos_version.py [VERSION]
```

VERSION defaults to the latest GitHub release. The script:
- repins every task image by digest;
- updates the version named in instructions, READMEs and the skill's `targetsCerbosVersion`;
- bumps the patch version of each changed task;
- runs the verifier regression tests, then oracle (expected reward 1) and nop (expected reward 0) on every task.

The oracle run replays each task's contract-derived decisions against the new PDP. A failure there usually means the release changed behaviour that a task encodes: inspect the named stage's logs, confirm the change in the release notes, and update that task's `contract.py`, `cases.json` and reference solution. Use `--dry-run` to preview the edits, and `--live` to also run the skill once per task. Review the release notes for skill guidance that needs updating too.

## Verifier regression tests

Run the local coverage-classification regressions without Docker or model calls:

```bash
uv run --no-project --with PyYAML==6.0.2 python -m unittest discover -s evals -p 'test_*verifier.py'
```

These checks accept equivalent fixture designs while rejecting missing or
confounded coverage. They complement the oracle, nop, and live task runs.

## Inspect results

```bash
uvx --from harbor==0.23.0 harbor view evals/jobs --jobs
```

The generation task receives nine scores: `files`, `folder_structure`,
`resource_policies`, `schemas`, `generated_tests`, `fixtures`, `compile_normal`,
`compile_strict`, and `pdp_decisions`. Overall `reward` is 1 only when every check
passes. A successful Harbor process exit alone does not establish reward 1.

The generation task's PDP check sends 16 real CheckResources requests covering
64 action decisions in normal and strict mode. The other tasks have their own
named checks and decision matrices, described in their READMEs. All tasks check
independent decisions against normal and strict PDPs; passing generated tests
alone is insufficient.

In the trial viewer, **Artifacts** contains generated workspace files, including
policies, schemas, fixtures, tests and helper scripts. Agent bootstrap files,
dependencies and caches are excluded. **Verifier** contains stage scores,
one log per check and PDP requests/responses. Results remain locally in
ignored `evals/jobs/`.
