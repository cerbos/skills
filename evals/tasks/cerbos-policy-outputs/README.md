# cerbos-policy-outputs

Add rule outputs to a seeded `payout` resource policy so a payments service can
write audit events and explain denials, then assert them in native tests. The
[instruction](instruction.md) specifies the exact values:
- `ruleActivated` and `conditionNotMet` outputs on the approval rule;
- a `ruleActivated` output on an explicit DENY rule;
- a new `flag-payouts` rule whose output computes a priority with a boundary at
  10000.

Existing rules must stay unchanged apart from their new outputs.

Behaviour checked against the real 0.55.0 PDP, following the Cerbos
[outputs docs](https://docs.cerbos.dev/cerbos/latest/policies/outputs.html):

- Outputs are per action: `{src: "resource.payout.vdefault#<rule name>", action, val}`.
- `conditionNotMet` fires when a rule matches the role and action but its
  condition is false. A rule for another role emits nothing.
- Overlapping rules can each emit, but **rule order matters**. Only rules evaluated
  before the matching DENY rule emit for that action. With `approve-within-limit`
  above `block-frozen-accounts`, an approvable frozen payout returns both
  `payout_approved` and `account_frozen`, with effect DENY. With the rules
  reversed, only `account_frozen` is returned. This is undocumented, so for
  frozen payouts the approve and flag outputs are optional in `pdp_decisions`,
  and only `account_frozen` is required.
- A failing output expression yields an `error` entry instead of `val`.
- Test-suite `outputs` assertions are subset checks: listed outputs must match,
  and extra outputs are ignored. The JSON report includes actual outputs.

With several roles, outputs can be emitted once per matching role. This happens
for frozen payouts, but not consistently elsewhere, and it is undocumented. The
PDP matrix therefore uses single-role principals only.

## Environment

The image pins Cerbos 0.55.0 and Python 3.12 on Debian Bookworm by digest, with
PyYAML 6.0.2, Git, curl, and CA certificates, and copies the seed policy from
`environment/policies/` to `/workspace/policies`. Cerbos runs natively inside the
container. Limits: 2 CPUs, 2 GiB RAM, 4 GiB storage, 600 seconds for the agent and
120 seconds for verification.

## Verification

| Stage | Requirement |
| --- | --- |
| `preservation` | Seed rules equal `tests/seed_policy.json` apart from an added `output`; the header may gain a `schemas` block, which the skill recommends. `flag-payouts` allows `flag` for `clerk` and `manager`. It may carry a condition (such as "not frozen"), and `pdp_decisions` checks that behaviour is unchanged. There are no other rules. |
| `compile_normal` | Native compilation and generated tests pass. |
| `generated_tests` | Every executed assertion's effect matches the contract. Output assertions in passing tests must match the contract and cover eight behaviours: approval at the limit (which satisfies "within the limit, including an amount equal to the limit"), over-limit, frozen on an otherwise approvable payout, flag priority at 10000 and above for each role, and frozen flagging. |
| `compile_strict` | Compilation and generated tests also pass with strict evaluation. |
| `pdp_decisions` | 105 verifier-owned requests (5 principals × 7 amounts × 3 frozen states, 4 actions each) against normal and strict PDPs. Each must match its effects and exact output set: 420 decisions and 287 outputs per mode. |

Each stage reports a binary score; overall `reward` is 1 only when all five pass.
`tests/contract.py` models effects and outputs and drives coverage grading and
`cases.json`. Coverage comes from outputs the suite asserts, not from the actual
outputs in the report, so a test must state the expected output. Because suite
assertions are subsets, only `pdp_decisions` detects extra outputs, such as one
added to `view-payouts`.

Validated locally before release: Harbor 0.23.0 oracle and nop rewards are 1 and
0. The following mutations each fail `pdp_decisions` or `preservation`:
- dropping `conditionNotMet`;
- renaming an output key;
- making the priority boundary inclusive;
- moving the frozen output to `conditionNotMet`;
- adding a `view` output;
- changing a seed condition;
- narrowing `flag-payouts` with a behaviour-changing condition.

Adding a `schemas` block is accepted.

Dropping required output assertions fails `generated_tests`.

## Layout

```text
instruction.md            Agent-facing requirements
task.toml                 Identity, limits, and artifacts
environment/Dockerfile    Pinned runtime and seed copy
environment/policies/     Seeded payout policy without outputs
solution/solve.sh         Installs the reference bundle
solution/policies/        Policy with outputs, suite, and fixtures
tests/test.sh             Verifier entrypoint
tests/verify.py           Stage execution and reward output
tests/contract.py         Expected effects and outputs
tests/check_outputs.py    Preservation and asserted-output coverage
tests/check_resources.py  Starts PDPs and compares effects and outputs
tests/seed_policy.json    Parsed seed policy for preservation
tests/cases.json          Independent inputs, effects, and outputs
```

`evals/test_outputs_verifier.py` holds regression tests for the coverage labels.

## Running

From the repository root with Docker running:

```bash
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-policy-outputs -a oracle
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-policy-outputs -a nop
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-policy-outputs \
  --skill ./skills/cerbos-policy -a codex -m openai/gpt-5.6-luna --agent-kwarg version=0.154.0
```

The model run requires credentials.
