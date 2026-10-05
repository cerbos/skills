# cerbos-pep-python-checks

Add Cerbos permission checks to an existing FastAPI expenses service. The
[instruction](instruction.md) describes the API and the business request in
plain terms: every endpoint must enforce the policy decision for its action, a
denied request returns 403 and changes nothing, and a request the app cannot get
a decision for must never succeed. It does not name a skill, the attribute
mapping, or the verifier's users and reports.

The seed app (`environment/app/`) has three endpoints with `# TODO:
authorization` markers: `GET /expenses/{id}` (`view`), `POST
/expenses/{id}/approve` (`approve`) and `DELETE /expenses/{id}` (`delete`).
Users come from an in-app directory keyed by the `X-User-Id` header and carry
`roles`, `department`, `region` and, for managers, `approval_limit`. Reports
carry `employee_id`, `department`, `region`, `amount` and `status`. The policy
bundle (`environment/policies/`, correct and not to be changed) is written
against `R.attr.owner`, so the agent has to map `employee_id` onto `owner`,
pass the principal attributes the conditions read, and send `amount` and
`approval_limit` as numbers.

What the task exercises:

| Behaviour | Why it matters |
| --- | --- |
| Map the user store onto `Principal` attributes | `department_manager`, `finance-view-region` and the approval limit read `P.attr.*`; roles alone deny managers and finance. |
| Map the report onto `Resource` attributes under the policy's names | Sending the stored dict as-is leaves `R.attr.owner` unset, so owners lose access. |
| Typed attribute values | Strings for `amount`/`approval_limit` make `<=` compare lexically or error. |
| Check before acting | Approving or deleting before the check changes data on a denied request. |
| Deny on error | With the PDP stopped, an allowed request must not succeed (skill: "Deny on error ... let it surface as a 5xx"). |

## Environment

The image pins Cerbos 0.55.0 and Python 3.12 on Debian Bookworm by digest and
installs a fully pinned `requirements.txt` (Cerbos Python SDK `cerbos==0.16.0`,
FastAPI 0.142.2, uvicorn 0.54.0, PyYAML 6.0.2 and their transitive
dependencies). It copies the policies to `/workspace/policies` and the app to
`/workspace/app`. Cerbos runs natively. Limits: 2 CPUs, 2 GiB RAM, 4 GiB
storage, 600 seconds for the agent and 180 seconds for verification.

## Verification

`tests/verify.py` starts a PDP from the verifier's own copy of the bundle
(`tests/policies/`, identical to the seed), writes hidden users and reports from
`tests/cases.json` to a file, and starts the agent's app with `EXPENSE_DATA`,
`CERBOS_GRPC_ADDR` and `CERBOS_HTTP_ADDR` pointing at them.

| Stage | Requirement |
| --- | --- |
| `uses_sdk` | A module under `/workspace/app` imports from `cerbos.sdk` (gRPC or HTTP client). |
| `app_starts` | `uvicorn main:app` starts from `/workspace/app` and `/health` returns 200. |
| `preserved_contract` | No header and unknown users get 401; a missing report gets 404, on all three endpoints. |
| `decisions` | 1,080 requests (8 hidden users including a multi-role user and a role with no rules, × 45 report shapes covering 5 owners, 3 statuses and amounts on both sides of each approval limit, × 3 actions) each on a fresh copy of the report. Allowed: 200 (204 or 200 for delete). Denied: 403. 228 are allowed. |
| `denied_unchanged` | After the matrix, an admin view of every report targeted by a denied approve or delete returns 200 with the original status. |
| `fail_closed` | The PDP is stopped and three requests the policy allows (view, approve, delete) are sent; each must return an error status other than 401/404 within 15 seconds. After the PDP restarts, the approve and delete targets must be unchanged. |

Each stage reports a binary score; overall `reward` is 1 only when all pass.
`tests/contract.py` restates the policy in Python and generates `tests/cases.json`
(`python tests/contract.py`).

## Validated locally

Harbor 0.23.0 oracle and nop rewards are 1 and 0. Nop passes `app_starts` and
`preserved_contract` and fails the rest. Replaying the verifier in the built
image against these variants of the reference solution gives reward 0:

- resource attributes sent as stored (`employee_id`, no `owner`): `decisions`
  fails (987/1080);
- principal sent with roles only, no attributes: `decisions` fails (990/1080);
- PDP errors caught and treated as allowed: only `fail_closed` fails;
- approve applied before the check: `decisions`, `denied_unchanged` and
  `fail_closed` fail;
- `amount` and `approval_limit` sent as strings: `decisions` and
  `denied_unchanged` fail (1070/1080).

## Layout

```text
instruction.md            Agent-facing request
task.toml                 Identity, limits and artifacts
environment/Dockerfile    Pinned runtime, SDK and seed copy
environment/requirements.txt  Fully pinned Python dependencies
environment/app/          Seed FastAPI app without authorization
environment/policies/     Correct expense_report bundle with tests
solution/solve.sh         Installs the reference app files
solution/app/             Reference main.py and authz.py (gRPC SDK)
tests/test.sh             Verifier entrypoint
tests/verify.py           Stage execution and reward output
tests/harness.py          PDP and app process management, HTTP calls
tests/contract.py         Hidden data and expected decisions; generates cases.json
tests/cases.json          Hidden users, reports and cases
tests/policies/           Verifier copy of the bundle
```

## Running

From the repository root with Docker running:

```bash
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-pep-python-checks -a oracle
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-pep-python-checks -a nop
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-pep-python-checks \
  --skill ./cerbos/cerbos-pep-integration -a codex -m openai/gpt-5.6-luna --agent-kwarg version=0.154.0
```

The model run requires credentials.
