# cerbos-policy-files

Generate one complete policy bundle for document access in `content` and invoice
access in `billing`. The [instruction](instruction.md) supplies the business
permissions and asks for a complete bundle. The skill supplies the expected
layout, schemas, fixtures and test conventions; the prompt does not reveal that
output recipe. Task version 2.0.0 expands the
original single-resource task; its scores are not comparable with version 1.x.

## Environment

The Docker image pins Python 3.12 on Debian Bookworm and Cerbos 0.55.0 by digest.
PyYAML 6.0.2 supports semantic YAML checks. Git, curl and CA certificates are
installed. Cerbos runs directly in the task container; Docker-in-Docker is not
required. The task has 2 CPUs, 2 GiB RAM, 4 GiB storage, a 600-second agent timeout
and a 120-second verifier timeout.

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
environment/Dockerfile  Pinned runtime and dependencies
solution/solve.sh       Copies the reference bundle into the workspace
solution/policies/      Static reference policies, schemas, fixtures and tests
tests/test.sh           Shell launcher for verify.py
tests/verify.py         Runs all nine checks and writes scores
tests/check_outputs.py  Structural and semantic generation checks
tests/cases.json        Independent PDP decision matrix
tests/check_resources.py  Bundled real PDP verifier
```

Version 2.1.1 stores the reference bundle as YAML/JSON files copied by solve.sh.
Verification uses native Cerbos test reports instead of a custom test-suite
interpreter. The prompt and nine requirements are unchanged.

All verifier code lives in this task’s `tests/` directory.

## Running

From the repository root with Docker running:

```bash
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-policy-files -a oracle
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-policy-files -a nop
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-policy-files \
  --skill ./cerbos/cerbos-policy -a codex -m openai/gpt-5.6-luna --agent-kwarg version=0.154.0
```

The real agent requires model credentials. Replace `./cerbos/cerbos-policy` to evaluate another
skill checkout. The task is self-contained; no repository runner or shared helper setup is required.
