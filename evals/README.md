# Local policy skill eval

This is one native [Harbor task](https://www.harborframework.com/docs/tasks):
[`cerbos-policy-files`](tasks/cerbos-policy-files/README.md). Each attempt asks an
agent to generate a document/invoice policy bundle from business requirements.
The prompt supplies the destination and permissions; the `cerbos-policy` skill
supplies the folder layout, schemas, fixtures and test conventions.

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
the agent's instructions. Everything needed to run this task is inside its
folder. Cerbos runs directly in the container; Docker-in-Docker is unnecessary.

## Run

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and start
Docker. Run commands from the repository root, using a fresh job name each time.

Check the reference solution (expected reward 1):

```bash
uvx --from harbor==0.23.0 harbor run \
  -p evals/tasks/cerbos-policy-files -a oracle \
  --jobs-dir evals/jobs --job-name policy-oracle
```

Check an empty attempt (expected reward 0):

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

Oracle and nop check the task itself. The real-agent run measures how well the
skill helps generate the bundle. No model is called until that command is run.

To try a different skill checkout, change `--skill` and use a fresh job name.
Use `--n-attempts 3` to repeat the same task three times. When comparing skill
versions locally, keep the task, model, agent version and attempt count the same.

## Inspect results

```bash
uvx --from harbor==0.23.0 harbor view evals/jobs --jobs
```

Each generation receives nine scores: `files`, `folder_structure`,
`resource_policies`, `schemas`, `generated_tests`, `fixtures`, `compile_normal`,
`compile_strict`, and `pdp_decisions`. Overall `reward` is 1 only when every check
passes. A successful Harbor process exit alone does not establish reward 1.

The PDP check sends 16 real CheckResources requests covering 64 action decisions
in normal and strict mode. Its independent inputs establish whether the generated
policies work; passing generated tests alone is insufficient.

In the trial viewer, **Artifacts** contains generated workspace files, including
policies, schemas, fixtures, tests and helper scripts. Agent bootstrap files,
dependencies and caches are excluded. **Verifier** contains stage scores,
one log per check and PDP requests/responses. Results remain locally in
ignored `evals/jobs/`.
