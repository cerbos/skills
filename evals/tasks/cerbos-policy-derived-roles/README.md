# cerbos-policy-derived-roles

Implement two resource policies that reuse conditional derived roles for tenant
isolation, ownership, and department review. The [instruction](instruction.md)
requires parent-role gating and checks that overlapping derived roles combine
permissions. This task complements file-generation and policy-evolution evals.

## Environment

The image pins Cerbos 0.55.0 and Python 3.12 on Debian Bookworm by digest, with
PyYAML 6.0.2, Git, curl, and CA certificates. Cerbos runs natively inside the
container. Limits: 2 CPUs, 2 GiB RAM, 4 GiB storage, 600 seconds for the agent and
120 seconds for verification.

## Verification

| Stage | Requirement |
| --- | --- |
| `architecture` | One shared `tenant_roles` policy with the specified conditional definitions and parent roles; both resource policies import and grant through those derived roles. Equivalent inline grants fail this stage. |
| `compile_normal` | Native compilation and generated tests pass. |
| `generated_tests` | Native test reports contain executed, contract-correct owner/reviewer grants, overlap, parent-role denials, tenant and relationship boundaries, and default denial for both resources. |
| `compile_strict` | Compilation and generated tests also pass with strict evaluation. |
| `pdp_decisions` | Verifier-owned inputs exercise 72 principal/resource combinations against both normal and strict PDPs, checking five actions each. |

Each programmatic stage reports a binary score; overall `reward` is 1 only when
all five pass. Runtime checks include supplied derived-role names masquerading
as principal roles. The 144 independent requests check 720 action decisions.
Logs and request/response evidence go to `/logs/verifier`; Harbor collects the
workspace as an artifact. All stages run even after earlier failures.

The shared-container verifier follows the existing eval convention; it is not
hardened against deliberate runtime tampering. Finite decision coverage checks
this contract rather than proving arbitrary policy equivalence.

## Layout

```text
instruction.md           Agent-facing requirements
task.toml               Identity, limits, and artifacts
environment/Dockerfile  Pinned runtime
solution/solve.sh       Installs the reference bundle
solution/policies/      Shared roles, resource policies, tests, and fixtures
tests/test.sh           Verifier entrypoint
tests/verify.py         Stage execution and reward output
tests/check_outputs.py  Architecture and native test coverage checks
tests/check_resources.py  Starts PDPs and checks independent decisions
tests/cases.json        Independent inputs and expected decisions
```

## Running

From the repository root with Docker running:

```bash
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-policy-derived-roles -a oracle
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-policy-derived-roles -a nop
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-policy-derived-roles \
  --skill ./cerbos/cerbos-policy -a codex -m openai/gpt-5.6-luna --agent-kwarg version=0.154.0
```

The model run requires credentials. The task has no shared verifier dependencies.
Oracle and nop were validated with Harbor 0.23.0: rewards 1 and 0, respectively.
Mutations removing tenant isolation, changing a parent role, and replacing derived
roles with behaviorally equivalent inline grants each received reward 0; the
inline mutation still passed runtime decisions, confirming architecture is graded.
