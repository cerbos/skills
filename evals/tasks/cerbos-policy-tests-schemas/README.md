# cerbos-policy-tests-schemas

Add attribute schemas and native tests around two seeded resource policies,
`finance/expense` and `hr/leave_request`, without changing their rules. The
[instruction](instruction.md) specifies the schemas and requires `create` to skip
resource validation. It also asks for two test styles: the finance suite takes
every fixture from `testdata/` files, and the HR suite defines its fixtures inline
with no `testdata/` directory. Each suite must show schema validation denying
requests the policy would otherwise allow.

Behaviour checked against the real 0.55.0 binary, following the Cerbos docs on
[schemas](https://docs.cerbos.dev/cerbos/latest/policies/schemas.html) and
[policy tests](https://docs.cerbos.dev/cerbos/latest/policies/compile.html):

- `cerbos compile` runs tests with schema enforcement in reject mode: invalid
  attributes deny every action.
- `ignoreWhen` skips resource validation only when every action in the check is
  listed. A `create`-only check on an incomplete resource is allowed; `create`
  with `view` is denied.
- The PDP returns `validationErrors` exactly when validation runs and fails.
- Inline suite fixtures override same-named `testdata/` fixtures.

## Environment

The image pins Cerbos 0.55.0 and Python 3.12 on Debian Bookworm by digest, with
PyYAML 6.0.2, Git, curl, and CA certificates, and copies the seed bundle from
`environment/policies/` to `/workspace/policies`. Cerbos runs natively inside the
container. Limits: 2 CPUs, 2 GiB RAM, 4 GiB storage, 600 seconds for the agent and
120 seconds for verification.

## Verification

| Stage | Requirement |
| --- | --- |
| `preservation` | Both policies equal the seed (`tests/seed_policies.json`) apart from an added `schemas` block. |
| `schemas` | The three schema files exist, and each policy references `cerbos:///principal.json` and `cerbos:///resources/<kind>.json`, with resource `ignoreWhen` exactly `create`. |
| `fixtures` | Finance: shared `testdata/principals.yaml` and `resources.yaml`, with no inline fixtures in the suite. HR: inline principals and resources, with no `testdata/` directory. |
| `compile_normal` | Native compilation and generated tests pass. |
| `generated_tests` | Every executed assertion matches the contract. Each suite covers owner view, other-owner denial, manager approval, other-department denial, create, invalid principal, missing attribute, invalid value, unknown attribute, and incomplete `create`. |
| `compile_strict` | Compilation and generated tests also pass with strict evaluation. |
| `pdp_decisions` | 1512 verifier-owned requests against PDPs with `schema.enforcement: reject`, in normal and strict mode. They combine 14 principals (6 invalid) with 36 resources (22 invalid), each under a full action list, `create` alone, and `create` with `view`. Effects and the presence of `validationErrors` must match. |

Each stage reports a binary score; overall `reward` is 1 only when all seven pass.
`tests/contract.py` models the specified schemas, the seeded rules and reject-mode
enforcement. It drives both coverage grading and `cases.json`.

Coverage labels only credit denials that schema validation explains. A schema
denial counts only when the policy alone would allow that action, and the resource
has exactly one kind of violation (missing, invalid value, or unknown attribute).
Incomplete `create` coverage needs a `create`-only check. An employee `create`
counts as create coverage whether or not the record is complete. The
other-department denial must be allowed if only the resource's department
changed.

Validated locally before release: Harbor 0.23.0 oracle and nop rewards are 1 and
0. Mutations dropping `additionalProperties: false`, the department enum, the
integer type for `days`, a required attribute, or `ignoreWhen` each fail
`pdp_decisions`. So does widening `ignoreWhen` or changing a rule. Moving finance
fixtures inline or HR fixtures into `testdata/` fails `fixtures`, and dropping a
required test case fails `generated_tests`.

## Layout

```text
instruction.md            Agent-facing requirements
task.toml                 Identity, limits, and artifacts
environment/Dockerfile    Pinned runtime and seed copy
environment/policies/     Seeded expense and leave-request policies
solution/solve.sh         Installs the reference bundle
solution/policies/        Schemas, policies, both suites, and finance fixtures
tests/test.sh             Verifier entrypoint
tests/verify.py           Stage execution and reward output
tests/contract.py         Schema, rule and enforcement model
tests/check_outputs.py    Preservation, schema wiring, fixture style, coverage
tests/check_resources.py  Starts reject-mode PDPs and checks decisions
tests/seed_policies.json  Parsed seed policies for preservation
tests/cases.json          Independent inputs and expected decisions
```

`evals/test_tests_schemas_verifier.py` holds regression tests for the coverage labels.

## Running

From the repository root with Docker running:

```bash
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-policy-tests-schemas -a oracle
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-policy-tests-schemas -a nop
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-policy-tests-schemas \
  --skill ./skills/cerbos-policy -a codex -m openai/gpt-5.6-luna --agent-kwarg version=0.154.0
```

The model run requires credentials.
