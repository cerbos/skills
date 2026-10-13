# cerbos-migrate-rego

Translate an OPA/Rego expense policy into Cerbos policies with a native test
suite, matching the Rego decision for every user, expense and action. The
[instruction](instruction.md) fixes how the Rego `input` maps onto a
CheckResources request (principal `id`, `roles`, `attr.department`; resource
kind `expense` with the remaining `input.resource` fields as attributes), and
asks for tests covering multi-role users and legal hold. It does not say where
the translation goes wrong.

The seed in `environment/opa/` is `expenses.rego` (Rego v1), `data.json` (role
grants and approval limits) and `expenses_test.rego`. `allow` is a single
ordered `else` chain, so the translation has to restate evaluation order as
conditions, because Cerbos resolves conflicts in a fixed way (deny wins within a
role, any role's allow wins across roles):

| Rego branch | Trap in a direct translation |
| --- | --- |
| 1. `legal_hold == true` and action is not `view` → false | Applies to admins too. `legal_hold` is optional: an unguarded `R.attr.legal_hold == true` DENY is skipped under default evaluation but is a terminal error under strict evaluation, which denies every action on expenses without the attribute. |
| 2. `admin` → true | Beats branch 3 for a user who is both admin and contractor. |
| 3. `contractor` and departments differ → false | In Rego this overrides grants from the user's other roles. A `roles: ["contractor"]` DENY only denies the contractor role, so a contractor+finance user still views and exports other departments' expenses. It needs `roles: ["*"]` with `"contractor" in P.roles`, and must exclude admins. |
| 4. Role grants from `data.json` | Data becomes rules (the instruction allows it). |
| 5. Owner may view, and edit/submit/delete drafts | Any role, including roles with no grants (`intern`); an owner who is a contractor outside the expense's department is still refused (branch 3). |
| 6. Approve submitted, not own, `amount <= data.approval_limits[role]` for some role | `manager` 5000, `director` 50000, any of the user's roles may satisfy it. |

## Environment

The image pins Cerbos 0.55.0 and Python 3.12 on Debian Bookworm by digest, with
PyYAML 6.0.2, Git, curl and CA certificates, and copies the Rego seed to
`/workspace/opa`. OPA is not installed in the image. Cerbos runs natively.
Limits: 2 CPUs, 2 GiB RAM, 4 GiB storage, 600 seconds for the agent and 180
seconds for verification (about 20 seconds in practice).

## Verification

| Stage | Requirement |
| --- | --- |
| `compile_normal` | Native compilation and tests pass. |
| `generated_tests` | Every executed, passing `expense` assertion agrees with `contract.py`'s Rego model. Tests run without a `strictEvaluation` option include a contractor holding another role denied an action outside their department that the other role alone would be allowed, and an admin denied a non-`view` action on an expense under legal hold. |
| `compile_strict` | Compilation and tests also pass with strict evaluation. |
| `pdp_decisions` | 3264 verifier-owned requests (12 principals, including admin+contractor, contractor+finance, contractor+manager, manager+director and an unknown role, × 272 expenses: 5 owners × 2 departments × amounts 5000/5001/50001 × 3 statuses × `legal_hold` absent/false/true, plus two at exactly 50000), 7 actions each, against normal and strict PDPs: 22848 decisions per mode. |

Each stage reports a binary score; overall `reward` is 1 only when all four
pass. `tests/contract.py` models the Rego (undefined references make a body
fail rather than error); `check_resources.py` builds the matrix from it at run
time rather than reading a checked-in `cases.json`, which would be over 1 MB
(`python tests/contract.py` prints a summary).

The model was checked against real OPA at build time, not in the task image:
`python tests/contract.py --rego-inputs` emits every decision as an OPA input
with its expected result, and evaluating them with
`openpolicyagent/opa:1.10.1-static@sha256:e1f196b5316301785d5251543c9d0f3f6c83ce6ac23263b494730427fa80e248`
gave 0 mismatches over all 22848 decisions (6301 allows). The seed
`expenses_test.rego` passes under the same image (`opa test`, 4/4).

```bash
python3 tests/contract.py --rego-inputs \
  | python3 -c 'import sys,json; print(json.dumps({"regocases": [json.loads(l) for l in sys.stdin]}))' > /tmp/rego/cases.json
cat > /tmp/rego/check.rego <<'REGO'
package check

import rego.v1

result(c) := r if r := data.expenses.authz.allow with input as c.input

mismatches contains c if {
	some c in data.regocases
	result(c) != c.expected
}
REGO
docker run --rm -v "$PWD/environment/opa:/src:ro" -v /tmp/rego:/cases:ro \
  openpolicyagent/opa@sha256:e1f196b5316301785d5251543c9d0f3f6c83ce6ac23263b494730427fa80e248 \
  eval -d /src/expenses.rego -d /src/data.json -d /cases/cases.json -d /cases/check.rego \
  'count(data.check.mismatches)'
```

Use a helper function as above: the same `with input as` written directly
inside a comprehension returned every expected `true` as a mismatch under OPA
1.10.1.

## Validated locally

Harbor 0.23.0 oracle and nop rewards are 1 and 0. Nop fails every stage: there
is no `/workspace/policies`. Replaying the verifier inside the built image
against these hand-made mutations of the reference, each with its own suite
adjusted so that it still passes, gives reward 0:

- contractor DENY scoped to `roles: ["contractor"]`: `generated_tests` (no
  multi-role override coverage left) and `pdp_decisions` fail;
- contractor DENY without the admin exclusion: `pdp_decisions` fails for
  admin+contractor;
- legal-hold DENY without `has()`: every normal-mode decision matches, but
  `compile_strict` (the suite fails under strict evaluation) and 785
  strict-mode requests in `pdp_decisions` fail;
- legal-hold DENY that exempts admins: `generated_tests` (the suite now
  contradicts the Rego) and `pdp_decisions` fail;
- approval without the owner exclusion: `pdp_decisions` fails;
- owner derived role with named `parentRoles`: `pdp_decisions` fails for
  contractor and `intern` owners.

## Layout

```text
instruction.md            Agent-facing request
task.toml                 Identity, limits and artifacts
environment/Dockerfile    Pinned runtime; copies the Rego seed
environment/opa/          expenses.rego, data.json, expenses_test.rego
solution/solve.sh         Installs the reference bundle
solution/policies/        expense resource policy, derived role, suite, fixtures
tests/test.sh             Verifier entrypoint
tests/verify.py           Stage execution and reward output
tests/contract.py         Rego model; builds the decision matrix and OPA replay inputs
tests/check_outputs.py    Native test agreement and coverage
tests/check_resources.py  Starts PDPs and compares decisions
```

## Running

From the repository root with Docker running:

```bash
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-migrate-rego -a oracle
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-migrate-rego -a nop
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-migrate-rego \
  --skill ./cerbos/cerbos-authz-migration --skill ./cerbos/cerbos-policy \
  -a codex -m openai/gpt-5.6-luna --agent-kwarg version=0.154.0
```

The model run requires credentials.
