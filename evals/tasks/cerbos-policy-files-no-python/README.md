# cerbos-policy-files-no-python

This task is a variant of [cerbos-policy-files](../cerbos-policy-files/README.md).
It checks that the `cerbos-policy` skill still succeeds when the agent cannot run
Python. The skill's coverage audit (`scripts/coverage_audit.py`) tells the agent
to use `python3`, then Docker, then perform the checks by hand. Neither Python nor
Docker is available to the agent here, so the agent must follow the manual path.

The instruction, reference solution and verifier checks are identical to
cerbos-policy-files 2.1.1. Only the environment and the verifier launcher differ.
Rewards are therefore directly comparable: a skill that passes cerbos-policy-files
but fails here depends on Python. The verifier does not read the coverage plan
or the audit output. It scores only the generated bundle, so the task checks that
the fallback does not break the bundle. It does not check how faithfully the agent
performed the manual audit; inspect the agent trajectory for that.

Generate one complete policy bundle for document access in `content` and invoice
access in `billing`. The [instruction](instruction.md) supplies the business
permissions and asks for a complete bundle. The skill supplies the expected
layout, schemas, fixtures and test conventions; the prompt does not reveal that
output recipe. The instruction does not mention Python.

## Environment

The Docker image pins Python 3.12 on Debian Bookworm and Cerbos 0.55.0 by digest,
the same base as the other policy tasks. PyYAML 6.0.2 is installed for the verifier.
Git, curl, CA certificates and ripgrep are installed. Cerbos runs directly in the
task container; Docker-in-Docker is not required. The task has 2 CPUs, 2 GiB RAM,
4 GiB storage, a 600-second agent timeout and a 120-second verifier timeout.

Python is hidden from the agent in the last build step:

- The interpreter moves from `/usr/local/bin/python3.12` to
  `/usr/local/libexec/verifier-python`, outside `PATH`. It still locates its
  standard library and site-packages through `/usr/local/lib/python3.12`.
- `python`, `python3`, `pip`, `pip3`, `pydoc`, `idle`, `2to3` and the `*-config`
  entry points are deleted, so `command -v python3 python pip pip3` finds nothing.
- An apt preference (`/etc/apt/preferences.d/no-python`) gives every `python*`,
  `libpython*` and `pypy*` package priority -1. As a result, `apt-get install
  python3`, or any package that depends on it, fails.
- The build fails if the relocated interpreter cannot import `json` and `yaml`,
  or if any Python entry point remains on `PATH`.

Node.js 22 (official tarball with npm, checksum-pinned) and ripgrep are
preinstalled. Harbor's Codex setup runs `apt-get install nodejs npm` whenever
`node`, `npm` or `rg` is missing. Debian's `npm` depends on `python3`, so that
step would reinstall Python, and the apt pin would make it fail. With these tools
present, Harbor skips the apt step and installs Codex through nvm and npm, which
do not need Python.

`tests/test.sh` runs `/usr/local/libexec/verifier-python /tests/verify.py` with
`exec`. `verify.py` launches every sub-check with `sys.executable`, so all checks
use the same hidden interpreter.

The relocated interpreter is hidden, not removed. An agent that searches the
filesystem can find and run it, or it can download a Python build. Check the
trajectory if a run passes unexpectedly.

## Verification

One agent generation is scored in nine independent stages:

| Stage | Requirement |
| --- | --- |
| `files` | All eleven files required by the skill layout exist and contain text. |
| `folder_structure` | Required schema/domain/testdata directories exist; files are not external symlinks. |
| `resource_policies` | Exactly two resource policies, in the requested domains, with the correct kinds, default versions and nonempty rules. YAML and JSON policy definitions are inspected. |
| `schemas` | JSON attribute-object schemas exist, define no attributes, and the policies reference the correct bundled schemas. |
| `generated_tests` | Active suites resolve their fixtures and include correct ALLOW and DENY expectations for each resource, as required by the skill. |
| `fixtures` | Each domain supplies nonempty principal/resource fixtures with IDs, roles, the correct resource kind and empty attributes. |
| `compile_normal` | Native Cerbos validates schemas, compiles policies and executes generated tests. |
| `compile_strict` | The same checks pass with strict evaluation enabled. |
| `pdp_decisions` | Independent requests to fresh normal and strict PDPs exercise both resources, all four roles, and view/edit/approve/delete. |

The definitive result remains binary: every stage must pass. Named scores and
one log per check explain failures. Every check runs even if an earlier check fails.
Cerbos validates policy syntax, schemas and test suites. Its JSON compilation
report resolves fixtures, groups, selectors, skips and default expectations.
The generated-tests check reads that report and requires executed ALLOW and DENY
coverage for each resource, with decisions matching the business requirements.
The independent PDP stage checks the full permission matrix.

The independent decision matrix sends 16 real CheckResources requests containing
64 action decisions. It uses verifier-owned inputs, not the generated fixture
expectations. Evidence is retained in `/logs/verifier`; Harbor also collects the
generated `/workspace` tree as a trial artifact, including policy bundles and
ad hoc helper files. Agent bootstrap directories, Git metadata, dependency
directories and caches are excluded.

Verification runs in the shared task container after the agent. This permits
inspection of generated files and native compilation; it is not hardened against
deliberate runtime tampering. Decision coverage is finite and scoped to this
specification, not a proof over arbitrary policies or action names.

## Layout

```text
instruction.md          Agent-facing goals and output contract
task.toml               Identity, version, limits and generated-bundle artifact
environment/Dockerfile  Pinned runtime and dependencies; hides Python from the agent
solution/solve.sh       Copies the reference bundle into the workspace
solution/policies/      Static reference policies, schemas, fixtures and tests
tests/test.sh           Runs verify.py with the relocated verifier interpreter
tests/verify.py         Runs all nine checks and writes scores
tests/check_outputs.py  Structural and semantic generation checks
tests/cases.json        Independent PDP decision matrix
tests/check_resources.py  Bundled real PDP verifier
```

Everything except `task.toml`, `README.md`, `environment/Dockerfile` and
`tests/test.sh` is a byte-for-byte copy of cerbos-policy-files 2.1.1. Keep the two
tasks in sync when either changes.

All verifier code lives in this task’s `tests/` directory.

## Running

From the repository root with Docker running:

```bash
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-policy-files-no-python -a oracle
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-policy-files-no-python -a nop
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-policy-files-no-python \
  --skill ./skills/cerbos-policy -a codex -m openai/gpt-5.6-luna --agent-kwarg version=0.154.0
```

The real agent requires model credentials. Replace `./skills/cerbos-policy` to evaluate another
skill checkout. The task is self-contained; no repository runner or shared helper setup is required.
