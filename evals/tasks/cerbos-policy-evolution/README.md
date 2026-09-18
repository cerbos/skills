# Cerbos policy evolution eval

The agent [updates an existing invoice policy](instruction.md): raise accountant approval limits, introduce unlimited finance admin approval, and enforce holds and self-approval restrictions. Existing read/delete and tenant boundaries must survive, as must an unrelated audit policy and its tests. This tests focused policy maintenance rather than generating a bundle from scratch.

## Environment

The environment uses digest-pinned Python 3.12 Bookworm and Cerbos 0.55.0 images, with PyYAML 6.0.2, curl and git installed. It seeds a working policy bundle in `/workspace/policies`. CPU: 2; RAM: 2 GiB; disk: 4 GiB; agent timeout: 600 seconds. No external service or GPU is required.

## Verifier

A custom deterministic verifier records five binary dimensions. `reward` is 1 only when all pass.

| Dimension | What it checks |
| --- | --- |
| `preservation` | Unrelated audit policy/test hashes, invoice identity/version, no bundle symlinks |
| `compile_normal` | Native Cerbos compilation and submitted tests |
| `generated_tests` | Executed regression scenarios/effects and specific approval edge-case coverage, using compiler results and resolved fixtures |
| `compile_strict` | Compilation and submitted tests under strict evaluation |
| `pdp_decisions` | 65 independent principal/resource scenarios in each evaluation mode; read, approve, delete and an unknown action |

The decision cases cover five principal role combinations, threshold boundaries, large amounts, absent/false/true holds, ownership, invoice state and foreign tenants. Cases do not use agent-authored test expectations. Compiler output, PDP logs, decision requests/responses and per-check results are saved under `/logs/verifier`.

## Layout

```text
instruction.md              Agent request and confirmed requirements
task.toml                   Harbor limits, metadata and artifact collection
environment/Dockerfile      Pinned native Cerbos/Python runtime
environment/policies/       Existing invoice and unrelated audit policies/tests
solution/solve.sh           Apply only the changed invoice files
solution/policies/          Reference invoice policy and expanded tests
tests/test.sh               Verifier entry point
tests/verify.py             Run checks and aggregate reward
tests/check_outputs.py      Preservation and active test coverage checks
tests/check_resources.py    Start PDPs and check independent decisions
tests/cases.json            Independent authorization contract
tests/preserved.json        Unrelated-file hashes
tests/seed-test-names.json   Existing regression scenario predicates and expected effects
```

## Running

From the repository root with Docker running:

```sh
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-policy-evolution -a oracle
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-policy-evolution -a nop
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-policy-evolution \
  --skill ./cerbos/cerbos-policy -a codex -m openai/gpt-5.6-luna --agent-kwarg version=0.154.0
```

The oracle should receive `reward: 1`; nop retains a compilable bundle but fails changed decisions and expanded test coverage. The model run requires credentials. To compare skill and no-skill attempts, repeat the same Harbor command without `--skill`, keeping the model, agent version and attempt count fixed.
