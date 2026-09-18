# Local policy skill evals

These native [Harbor tasks](https://www.harborframework.com/docs/tasks) evaluate
the `cerbos-policy` skill against distinct policy authoring workflows.

| Task | Coverage |
| --- | --- |
| [`cerbos-policy-files`](tasks/cerbos-policy-files/README.md) | Generate document/invoice policies from business requirements, including schemas, fixtures and tests. |
| [`cerbos-policy-evolution`](tasks/cerbos-policy-evolution/README.md) | Change existing permissions while preserving unaffected behavior and regression tests. |
| [`cerbos-policy-derived-roles`](tasks/cerbos-policy-derived-roles/README.md) | Share conditional derived roles across resources, with parent-role and tenant boundaries. |
| [`cerbos-policy-variables`](tasks/cerbos-policy-variables/README.md) | Manage shared exported variables and policy-local variables while preserving authorization behavior. |

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
  --skill ./cerbos/cerbos-policy \
  -a codex --agent-kwarg version=0.154.0 -m openai/gpt-5.6-luna \
  --jobs-dir evals/jobs --job-name policy-live
```

Replace `cerbos-policy-files` in these commands with any task in the table above
and choose a distinct job name. Oracle and nop check the task itself. For tasks
with a starting bundle, nop leaves it unchanged; individual checks may pass,
but overall reward must be 0. The real-agent run measures how well the skill
helps complete the task. No model is called until that command is run.

To try a different skill checkout, change `--skill` and use a fresh job name.
Use `--n-attempts 3` to repeat the same task three times. When comparing skill
versions locally, keep the task, model, agent version and attempt count the same.

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
