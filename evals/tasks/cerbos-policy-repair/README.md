# cerbos-policy-repair

Repair a seeded `document` policy bundle that no longer compiles and whose tests
fail. The [instruction](instruction.md) states the confirmed requirements in
business terms and asks for a regression test for unclassified documents, but
does not say where the defects are. The bundle has three independent defects:

| Defect | Seed | Found by |
| --- | --- | --- |
| Compile error | `edit-own-documents` references derived role `owner`; `derived_roles/document_roles.yaml` defines `document_owner`. | `cerbos compile` fails before any test runs. |
| Boundary bug | `download-within-limit` uses `R.attr.size_mb < 25`; the requirement is "up to and including 25 MB". | The seed test `employee download size limit` fails once the bundle compiles. |
| Silent DENY no-op | `deny-contractor-non-public` uses `R.attr.classification != "public"`. With no `classification` the condition errors, so under default evaluation the DENY does not fire and `view-documents` or `edit-own-documents` allows the contractor. | No seed test uses an unclassified document, so the seed suite passes in both modes once the first two defects are fixed. The requested regression test fails in normal mode and passes in strict mode, which is the skill's documented signal. |

The reference fix guards the DENY with
`!has(R.attr.classification) || R.attr.classification != "public"`. Renaming the
definition instead of the reference, or an equivalent guard, is accepted.

Behaviour checked against the real 0.55.0 PDP:

- Under default evaluation, the unguarded DENY lets a contractor view and edit an
  unclassified document. Under strict evaluation, the error is terminal and every
  action is denied. So a bundle that only passes in strict mode still fails
  `pdp_decisions` in normal mode.
- Roles are evaluated separately and any role's ALLOW wins. A principal with both
  `employee` and `contractor` can view an internal document despite the
  contractor DENY. The instruction therefore gives each principal one role, the
  PDP matrix uses single-role principals only, and `contract.py` combines roles
  the way Cerbos does when it grades multi-role test fixtures.

## Environment

The image pins Cerbos 0.55.0 and Python 3.12 on Debian Bookworm by digest, with
PyYAML 6.0.2, Git, curl, and CA certificates, and copies the seed bundle from
`environment/policies/` to `/workspace/policies`. Cerbos runs natively inside the
container. Limits: 2 CPUs, 2 GiB RAM, 4 GiB storage, 600 seconds for the agent and
120 seconds for verification.

## Verification

| Stage | Requirement |
| --- | --- |
| `preservation` | Resource kind and version are unchanged and no scope is added. Every seed rule still exists by name. The three defective rules keep their actions and effect; the other rules are unchanged. Extra rules are allowed. Every seed test in `tests/seed-test-names.json` still exists, is not skipped, and still asserts each seed decision. Decisions are compared by fixture contents (roles, attributes, and whether the principal owns the document), not fixture names or IDs, and unlisted pairs count as implicit DENY. The bundle has no symlinks. |
| `compile_normal` | Native compilation and tests pass. |
| `generated_tests` | Every executed, passing document assertion matches `contract.py`. Each seed decision executed and passed under its original test name. Tests run without a `strictEvaluation` option cover a contractor denied `view` on a document with no `classification`, and an employee allowed to download at exactly 25 MB and denied above it. |
| `compile_strict` | Compilation and tests also pass with strict evaluation. |
| `pdp_decisions` | 108 verifier-owned requests (4 principals × sizes 10/25/26 MB × absent/`public`/`internal` classification × 3 owners, 5 actions each) against normal and strict PDPs: 540 decisions per mode. |

Each stage reports a binary score; overall `reward` is 1 only when all five pass.
`tests/contract.py` models the requirements and generates `tests/cases.json`
(`python tests/contract.py`). `tests/seed_policy.json` and
`tests/seed-test-names.json` are snapshots of the seed bundle, regenerated with
`python tests/check_outputs.py snapshot evals/tasks/cerbos-policy-repair/environment/policies`
(requires PyYAML).

Validated locally before release: Harbor 0.23.0 oracle and nop rewards are 1 and
0. Nop fails every stage except `preservation`. Replaying the verifier against
these mutations gives reward 0:

- only the compile error fixed: `compile_normal`, `generated_tests`,
  `compile_strict` and `pdp_decisions` fail (25 MB downloads);
- compile error and boundary fixed, no-op left, seed tests only:
  `generated_tests` and normal-mode `pdp_decisions` fail (strict mode passes);
- the same with the reference regression test: `compile_normal` and
  `generated_tests` fail as well;
- DENY guarded as `has(R.attr.classification) && ...`, which lets unclassified
  documents through: `compile_normal`, `compile_strict` and `pdp_decisions`
  fail in both modes;
- no-op left, with `options.strictEvaluation: true` on the suite so it passes:
  `generated_tests` and normal-mode `pdp_decisions` fail;
- test suite deleted, a seed boundary assertion removed, or the 25 MB seed
  fixture changed: `preservation` and `generated_tests` fail.

An equivalent repair (defining `owner` in the derived roles file, and
`!(has(R.attr.classification) && R.attr.classification == "public")`) passes.

## Layout

```text
instruction.md            Agent-facing requirements
task.toml                 Identity, limits, and artifacts
environment/Dockerfile    Pinned runtime and seed copy
environment/policies/     Seed bundle with the three defects
solution/solve.sh         Installs the reference bundle
solution/policies/        Repaired policy, suite, and fixtures
tests/test.sh             Verifier entrypoint
tests/verify.py           Stage execution and reward output
tests/contract.py         Expected decisions; generates cases.json
tests/check_outputs.py    Preservation and executed coverage
tests/check_resources.py  Starts PDPs and compares decisions
tests/seed_policy.json    Parsed seed policy for preservation
tests/seed-test-names.json Seed test decisions for preservation
tests/cases.json          Independent inputs and effects
```

`evals/test_repair_verifier.py` holds regression tests for preservation and
coverage.

## Running

From the repository root with Docker running:

```bash
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-policy-repair -a oracle
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-policy-repair -a nop
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-policy-repair \
  --skill ./cerbos/cerbos-policy -a codex -m openai/gpt-5.6-luna --agent-kwarg version=0.154.0
```

The model run requires credentials.
