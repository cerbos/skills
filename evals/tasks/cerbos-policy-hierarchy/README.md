# cerbos-policy-hierarchy

Build a scoped policy hierarchy for one `report` resource: a base policy, a
narrowing-only `acme` → `acme.eu` chain, and an overriding `globex` sibling. The
[instruction](instruction.md) describes the permissions in business terms. The
agent must map "may only narrow its parent" to
`SCOPE_PERMISSIONS_REQUIRE_PARENTAL_CONSENT_FOR_ALLOWS` and "may grant or revoke
independently" to `SCOPE_PERMISSIONS_OVERRIDE_PARENT`, and must supply every
ancestor policy in the chain. This task complements file-generation, evolution,
derived-role and variable evals.

The semantics follow the Cerbos docs on
[scoped policies](https://docs.cerbos.dev/cerbos/latest/policies/scoped_policies.html)
and [scope permissions](https://docs.cerbos.dev/cerbos/latest/policies/scope_permissions.html).
The traps are checked against the real 0.55.0 PDP:

- In consent mode, an ALLOW rule whose condition fails is an implicit DENY. In
  override mode, the same rule falls through to the parent, so an override-mode
  `acme` policy lets editors edit published reports.
- A consent-mode ALLOW needs parent consent, so contractors stay denied in `acme.eu`
  even though its residency rule matches every role.
- Roles are evaluated separately and unioned, so an `editor` + `admin` may still
  edit published Acme reports.

## Environment

The image pins Cerbos 0.55.0 and Python 3.12 on Debian Bookworm by digest, with
PyYAML 6.0.2, Git, curl, and CA certificates. Cerbos runs natively inside the
container. Limits: 2 CPUs, 2 GiB RAM, 4 GiB storage, 600 seconds for the agent and
120 seconds for verification.

## Verification

| Stage | Requirement |
| --- | --- |
| `architecture` | Exactly four `report` policies at the instructed paths, version `default`, with scopes base, `acme`, `acme.eu`, `globex`. Both Acme levels use consent mode; `globex` uses override mode, explicitly or by default. |
| `compile_normal` | Native compilation and generated tests pass. |
| `generated_tests` | Every executed assertion in the native report matches the contract, and assertions cover the 15 behaviours the instruction lists, per scope where it says so. |
| `compile_strict` | Compilation and generated tests also pass with strict evaluation. |
| `pdp_decisions` | 504 verifier-owned requests (7 role sets × 2 regions × 4 scopes × 3 statuses × 3 flag states) check four actions each, including an unknown action, against normal and strict PDPs: 4032 decisions. |

Each stage reports a binary score; overall `reward` is 1 only when all five pass.
Logs and request/response evidence go to `/logs/verifier`, and all stages run even
after earlier failures. `tests/contract.py` holds the expected decisions used by
both coverage grading and `cases.json`.

Coverage labels mirror the instruction's list and credit only isolated evidence.
Any allowed base grant counts as inherited coverage for its scope. An `acme.eu`
denial for a non-EU principal counts as region coverage only if the same request
would be allowed for an EU principal; it never counts toward the draft or
contractor rules. The draft restriction needs an editor-only principal. The
contractor denial may come from any non-Globex scope but needs a
contractor-visible report. The multi-role case needs a principal with several
roles for which at least one role alone would be denied. The Globex visibility
check distinguishes an absent flag from `false`. Scope comes from the resource
fixture, then the test's `options.defaultScope`, then the suite's.

The `architecture` stage enforces the instruction's guarantee that no Acme-level
ALLOW can exceed its parent. An `acme.eu` policy in override mode with a
`region != "eu"` DENY rule gives identical decisions today, but it fails this
stage because a later ALLOW rule there could broaden access. The shared-container
verifier follows the existing eval convention; it is not hardened against
deliberate runtime tampering.

Validated locally before release: Harbor 0.23.0 oracle and nop rewards are 1 and
0. Mutations switching either Acme level to override mode, dropping the Globex
delete ban, ignoring the contractor flag, or narrowing the base policy each fail
`pdp_decisions`. Removing multi-role, non-EU, or unflagged-report tests fails
`generated_tests`.

## Layout

```text
instruction.md            Agent-facing requirements
task.toml                 Identity, limits, and artifacts
environment/Dockerfile    Pinned runtime
solution/solve.sh         Installs the reference bundle
solution/policies/        Base and scoped policies, tests, and fixtures
tests/test.sh             Verifier entrypoint
tests/verify.py           Stage execution and reward output
tests/contract.py         Expected decisions for the confirmed hierarchy
tests/check_outputs.py    Architecture and native test coverage checks
tests/check_resources.py  Starts PDPs and checks independent decisions
tests/cases.json          Independent inputs and expected decisions
```

`evals/test_hierarchy_verifier.py` holds regression tests for the coverage labels.

## Running

From the repository root with Docker running:

```bash
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-policy-hierarchy -a oracle
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-policy-hierarchy -a nop
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-policy-hierarchy \
  --skill ./skills/cerbos-policy -a codex -m openai/gpt-5.6-luna --agent-kwarg version=0.154.0
```

The model run requires credentials.
