# cerbos-policy-role-policies

Define Acme's custom roles with scoped role policies while leaving the seeded base
resource policies for `document` and `invoice` unchanged. The
[instruction](instruction.md) asks for three role policies in scope `acme`:
- a `contractor` based on `editor`, with a flag-gated edit;
- an `auditor` based on both `viewer` and `accountant`;
- a narrowing policy for the IdP `editor` role.

The agent must also write a suite with shared fixture files.

The semantics follow the Cerbos
[role policy docs](https://docs.cerbos.dev/cerbos/latest/policies/role_policies.html)
and were checked against the real 0.55.0 PDP:

- A role policy is an allowlist; an action also needs a grant from the
  resource-policy chain. A custom role with no `parentRoles` mapping to
  resource-policy roles gets nothing.
- Parent roles resolve recursively through other role policies in the scope.
  Contractors, based on `editor`, therefore inherit Acme's department rule for
  editors. The instruction states this, and the tests must expect it.
- A role policy for an IdP role (`editor`) narrows that role within its scope
  only. Outside Acme, editors keep the base permissions.
- Role policies attach to the resource's scope; the principal's scope is ignored.
  No scoped resource policy is needed, because the chain falls through to the base
  policy.
- A matched rule whose condition fails is an implicit DENY, even when another
  rule grants the same action unconditionally.
- A child role that lists an action its parent lacks still compiles, but the
  action is denied.

With several roles, role policies do not simply union permissions. For example,
an `editor` + `contractor` gets no edit on another department's contractor-editable
document. This behaviour is undocumented, so the task, fixtures and verifier use
single-role principals only, and coverage grading ignores multi-role fixtures.

## Environment

The image pins Cerbos 0.55.0 and Python 3.12 on Debian Bookworm by digest, with
PyYAML 6.0.2, Git, curl, and CA certificates, and copies the seed base policies
from `environment/policies/` to `/workspace/policies`. Cerbos runs natively inside
the container. Limits: 2 CPUs, 2 GiB RAM, 4 GiB storage, 600 seconds for the agent
and 120 seconds for verification.

## Verification

| Stage | Requirement |
| --- | --- |
| `architecture` | The base resource policies are byte-for-byte unchanged (`tests/preserved.json`). The only other policies are the three role policies at the instructed paths, each with its role, scope `acme`, version `default`, and rules. |
| `compile_normal` | Native compilation and generated tests pass. |
| `generated_tests` | Every executed single-role assertion matches the contract, and assertions cover the 17 behaviours the instruction lists. |
| `compile_strict` | Compilation and generated tests also pass with strict evaluation. |
| `pdp_decisions` | 224 verifier-owned requests (7 single-role principals × 2 departments × 16 resources across both scopes, with every flag state) check each resource kind's actions, including an unknown action, against normal and strict PDPs: 2576 decisions. |

Each stage reports a binary score; overall `reward` is 1 only when all five pass.
`tests/contract.py` models the base grants, the Acme allowlists and recursive
parent resolution. It drives both coverage grading and `cases.json`.

Coverage labels only credit isolated evidence. Contractor flag labels need a
document in the contractor's department. The other-department contractor denial
needs a document that is contractor-editable. Editor department labels must be
allowed if only the document's department changed. Parent roles are graded by
behaviour, not by static inspection, so any `parentRoles` that produce the
specified decisions are accepted. Replacing the editor role policy with an
equivalent scoped resource policy fails `architecture`, because the instruction
requires role policies.

Validated locally before release: Harbor 0.23.0 oracle and nop rewards are 1 and
0. Mutations removing the contractor's parent, dropping the auditor's
`accountant` parent, removing the editor policy, unscoping the role policies,
making contractor edits unconditional, or changing a base policy each fail
`pdp_decisions` or `architecture`. Removing required test cases fails
`generated_tests`.

## Layout

```text
instruction.md            Agent-facing requirements
task.toml                 Identity, limits, and artifacts
environment/Dockerfile    Pinned runtime and seed copy
environment/policies/     Seeded base document and invoice policies
solution/solve.sh         Installs the reference bundle
solution/policies/        Base policies, Acme role policies, suite, and fixtures
tests/test.sh             Verifier entrypoint
tests/verify.py           Stage execution and reward output
tests/contract.py         Base grants, Acme allowlists, parent resolution
tests/check_outputs.py    Preservation, layout, and native test coverage
tests/check_resources.py  Starts PDPs and checks independent decisions
tests/preserved.json      Seed policy digests
tests/cases.json          Independent inputs and expected decisions
```

`evals/test_role_policy_verifier.py` holds regression tests for the coverage labels.

## Running

From the repository root with Docker running:

```bash
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-policy-role-policies -a oracle
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-policy-role-policies -a nop
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-policy-role-policies \
  --skill ./skills/cerbos-policy -a codex -m openai/gpt-5.6-luna --agent-kwarg version=0.154.0
```

The model run requires credentials.
