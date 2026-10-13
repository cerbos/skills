# cerbos-policy-principal-exceptions

Add per-user exceptions and a token-based condition to a seeded `ticket` resource
policy, then prove them with pinned-clock and JWT fixture tests. The
[instruction](instruction.md) asks for:
- a principal policy for `ext-auditor-7` that grants `view` on every ticket only
  before the principal's `engagement_ends` timestamp;
- a principal-level DENY on `export` that overrides the auditor's `reporter` role;
- an MFA requirement on closing, read from the JWT's `amr` claim
  (`request.auxData.jwt`).

The seeded rules must stay unchanged apart from the close rule's condition.

Behaviour checked against the real 0.55.0 PDP, following the Cerbos
[principal policy](https://docs.cerbos.dev/cerbos/latest/policies/principal_policies.html),
[conditions](https://docs.cerbos.dev/cerbos/latest/policies/conditions.html),
[compile and test](https://docs.cerbos.dev/cerbos/latest/policies/compile.html) and
[auxData configuration](https://docs.cerbos.dev/cerbos/latest/configuration/auxdata.html)
docs:

- The principal policy is evaluated before the resource policy. Its `export`
  DENY wins over the `reporter` grant. When its `view` condition is false, the
  request falls through to the resource policy: an expired auditor who also held
  a team role would still see that team's tickets. The instruction does not ask
  about that case, so the matrix gives auditors the `reporter` role only.
- In native tests, `options.now` pins `now()`. Without it, every action
  asserted for a principal whose policies call `now()` is an ERROR ("a policy
  used a time-based condition, but `now` was not provided in the test
  options"), not a wall-clock evaluation. Unpinned auditor tests therefore fail
  `compile_normal`.
- A test's `options` replace the suite's, so `generated_tests` reads `now` from
  the test when it has `options`, otherwise from the suite.
- Test `auxData` fixtures supply claims directly (`jwt: {amr: [...]}`); no token
  or keyset is involved. A request without auxData sees an empty
  `request.auxData.jwt`, so an unguarded `request.auxData.jwt.amr` is a
  `no such key` error. On an ALLOW condition that is harmless in either mode. A
  DENY rule written as `!("mfa" in request.auxData.jwt.amr)` silently no-ops
  without a token in normal mode, so the close is allowed. The strict pass
  passes, but the no-token cases fail in normal mode.
- The PDP rejects a JWT (`400 invalid auxData`, "cannot determine keyset") unless
  `auxData.jwt` is configured. The verifier's PDPs set
  `auxData.jwt.disableVerification: true`. With that setting both `alg: none`
  and HS256 tokens signed with an unknown key are accepted, but `exp` is still
  enforced: an expired token is `400 invalid auxData`. `check_resources.py`
  therefore sends HS256 tokens with a throwaway key and `exp` in 2099.
- PDP `now()` is the wall clock, so the matrix uses engagement ends in 2001 and
  2099. The exact boundary (view denied at `engagement_ends`) can only be checked
  by pinned native tests: `generated_tests` rejects any executed assertion that
  contradicts the contract, including one at the boundary.

## Environment

The image pins Cerbos 0.55.0 and Python 3.12 on Debian Bookworm by digest, with
PyYAML 6.0.2, Git, curl, and CA certificates, and copies the seed policy from
`environment/policies/` to `/workspace/policies`. Cerbos runs natively inside the
container. Limits: 2 CPUs, 2 GiB RAM, 4 GiB storage, 600 seconds for the agent and
120 seconds for verification.

## Verification

| Stage | Requirement |
| --- | --- |
| `structure` | The only policies are `resource_policies/ticket.yaml` and `principal_policies/ext-auditor-7.yaml`. Seed rules equal `tests/seed_policy.json` except the condition of `managers-close-tickets`; the only rules that may be added are `EFFECT_DENY` rules for `close`, and the header may gain `schemas`. The principal policy names `ext-auditor-7`, uses version `default` without a scope, and has a `ticket` rule allowing `view` and one denying `export`. |
| `compile_normal` | Native compilation and generated tests pass. |
| `generated_tests` | Every executed passing assertion on a `ticket` matches the contract, evaluated at the test's pinned `now` and with its `auxData` JWT claims. Assertions cover six behaviours: auditor view before `engagement_ends` and denied at or after it (both with `options.now` pinned, and not granted by a team role), the auditor's export denied while holding `reporter`, another reporter's export allowed, and a manager closing an own-team ticket with an MFA token and denied with a token lacking MFA. |
| `compile_strict` | Compilation and generated tests also pass with strict evaluation. |
| `pdp_decisions` | 64 verifier-owned requests (8 principals × 2 teams × 4 token states: none, MFA, password-only, no `amr` claim), each checking `view`, `update`, `close`, `export` and an unknown `delete`, against normal and strict PDPs: 640 decisions. The principals include an active and an expired auditor and a lookalike `ext-auditor-8` with identical attributes, which must get no view and keep export. |

Each stage reports a binary score; overall `reward` is 1 only when all five pass.
`tests/contract.py` models the resource rules, the principal policy and the MFA
check, and drives coverage grading and `cases.json` (run it as a script to
regenerate). Coverage comes from executed, passing assertions whose effect agrees
with the contract, so a test that states the wrong effect fails
`generated_tests` even if the policy makes it pass. A no-token close denial is
recorded but not required from the suite; `pdp_decisions` checks it.

Validated locally before release: Harbor 0.23.0 oracle and nop rewards are 1 and
0. These mutations each fail at least one stage:
- dropping the time condition, inverting or dropping the MFA check
  (`compile_normal`, `compile_strict`, `pdp_decisions`);
- dropping the export DENY or moving the principal policy to version `v2`
  (also `structure`);
- making the boundary inclusive (`compile_normal`, through the reference suite's
  test pinned at `engagement_ends`; the PDP matrix cannot see the boundary);
- moving the auditor's view grant and export deny into the resource policy
  with `P.id` conditions (`structure`);
- deleting the pinned auditor tests or the MFA tests (`generated_tests`);
- removing `options.now` from the auditor tests, even with fixtures moved to
  2001 and 2099 so that the wall clock would give the same effects
  (`compile_normal`, see above);
- replacing the close condition with an unguarded DENY rule on the missing
  `mfa` claim (`compile_normal` and `pdp_decisions`; strict passes).

Accepted equivalents: an unguarded `"mfa" in request.auxData.jwt.amr` on the
close rule, and a separate guarded DENY rule for closing without MFA.

## Layout

```text
instruction.md            Agent-facing requirements
task.toml                 Identity, limits, and artifacts
environment/Dockerfile    Pinned runtime and seed copy
environment/policies/     Seeded ticket policy
solution/solve.sh         Installs the reference bundle
solution/policies/        Updated ticket policy, principal policy, suite, fixtures
tests/test.sh             Verifier entrypoint
tests/verify.py           Stage execution and reward output
tests/contract.py         Expected decisions; regenerates cases.json
tests/check_outputs.py    Structure and pinned-clock/JWT coverage
tests/check_resources.py  Starts PDPs with auxData.jwt and compares decisions
tests/seed_policy.json    Parsed seed policy for structure
tests/cases.json          Independent principals, resources, JWT claims, and effects
```

`evals/test_principal_exceptions_verifier.py` holds regression tests for the
coverage labels.

## Running

From the repository root with Docker running:

```bash
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-policy-principal-exceptions -a oracle
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-policy-principal-exceptions -a nop
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-policy-principal-exceptions \
  --skill ./skills/cerbos-policy -a codex -m openai/gpt-5.6-luna --agent-kwarg version=0.154.0
```

The model run requires credentials.
