# Cerbos policy variables eval

The agent uses `cerbos-policy` to refactor seeded invoice and expense policies, extracting shared tenant and suspension logic while keeping approval limits local. The [instruction](instruction.md) also specifies optional attribute defaults, strict evaluation, and regression tests. The seed compiles but has duplicated conditions and lacks suspension, blocking, and limit overrides.

## Environment

Digest-pinned Python 3.12 Bookworm with the digest-pinned Cerbos 0.55.0 binary, PyYAML 6.0.2, curl, and git. Docker runs the task; the agent uses native Cerbos inside the container. It has 2 CPUs, 2 GiB RAM, and 600 seconds. No model or network judge is required.

## Verifier

| Dimension | Deterministic check |
| --- | --- |
| `variables` | Shared definitions depend on `V.*`, both policies import and use them, local variables are referenced, names do not collide, and shared expressions are extracted. |
| `compile_normal` | Native compilation and all generated tests pass. |
| `generated_tests` | Native execution report proves active ALLOW/DENY tests and isolated coverage of tenants, ownership, exact/over limits, effective overrides, blocking, suspension, and absent optional attributes for both resources. |
| `compile_strict` | Compilation and generated tests also pass in strict mode. |
| `pdp_decisions` | 32 independent CheckResources requests per mode cover defaults, explicit booleans, boundary amounts, zero/high/low overrides, role denial, ownership, status, and tenant isolation. |
| `variable_effects` | In temporary policy copies, disabling shared eligibility removes every grant; replacing an individual local numeric limit with -1 removes approval grants while preserving view. Checks both runtime modes. |

`reward` is 1 only when every dimension passes. Per-dimension scores and logs remain available in `/logs/verifier`. The variable perturbations prevent unused definitions and imports from earning full credit. Static `V.*` reference checks follow the syntax explicitly requested by the task. Generated-test grading resolves inline fixtures and conventional sibling `testdata` fixtures from the native report.

Version 1.0.1 credits each absent optional attribute independently on successful
approval requests. Every resource still needs coverage of all three defaults,
but the attributes need not all be absent in the same request. This corrects a
false negative for suites that distribute default coverage across cases.

## Layout

```text
instruction.md                  Agent contract
task.toml                      Harbor resources, timeout, and artifacts
environment/Dockerfile         Pinned runtime and seed copy
environment/policies/          Existing duplicated policies
solution/solve.sh              Oracle installation and compile commands
solution/policies/             Reference refactor and regression suites
tests/test.sh                  Verifier entry point
tests/verify.py                Score aggregation and command logs
tests/check_outputs.py         Structure and executed test coverage
tests/check_resources.py       Isolated normal/strict PDP lifecycle
tests/check_variable_effects.py Variable-use perturbations
tests/cases.json               Independent behavior matrix
```

## Running

From the repository root:

```sh
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-policy-variables -a oracle
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-policy-variables -a nop
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-policy-variables --skill ./cerbos/cerbos-policy -a codex -m openai/gpt-5.6-luna --agent-kwarg version=0.154.0
```

The model command installs the selected local skill revision. Oracle and nop validate the task independently of model quality.
