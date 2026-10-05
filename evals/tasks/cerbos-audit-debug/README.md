# cerbos-audit-debug

Debug "managers can't approve invoices" in a Python invoice service that
authorizes through the Cerbos Python SDK, using the PDP's audit log, and fix the
application without touching the policy. The [instruction](instruction.md)
describes the symptom as users report it and asks for a short
`/workspace/FINDINGS.md`.

| Piece | State |
| --- | --- |
| `policies/invoice.yaml` | Correct. `approve-managed` requires `status == "submitted"`, `R.attr.cost_center in P.attr.managed_cost_centers`, `amount <= approval_limit` and `owner != P.id`. Its seed test suite passes. |
| `app/app.py` | The defect. `invoice_resource()` builds resource attributes from `Invoice.to_api()`, the UI's JSON shape, so the PDP receives `costCenter` and never `cost_center`. The approval condition can never hold; views are unaffected because no view rule reads the cost centre. |
| `/var/log/cerbos/audit.log` | 28 entries written by the real 0.55.0 PDP while the seeded app served 14 requests: employee and manager views allowed, every manager approval denied, each decision entry showing `resource.attr.costCenter`. |

The reference fix maps `owner`, `cost_center`, `amount` and `status`
explicitly. Equivalent fixes (adding `cost_center` alongside the API fields,
renaming in `invoice_resource()` only) pass. Changing the policy to read
`costCenter`, or renaming the field in the UI's JSON, does not.

## Environment

The image pins Cerbos 0.55.0 and Python 3.12 on Debian Bookworm by digest, and
installs `environment/requirements.txt`: the Cerbos Python SDK 0.16.0, PyJWT
2.10.1 and every transitive dependency at a pinned version. `/workspace` holds
`app/` (service, README, data), `policies/` and `cerbos/config.yaml` (disk
storage, `file` audit backend at `/var/log/cerbos/audit.log`); the seeded log is
copied into place. Nothing is running at start. Limits: 2 CPUs, 2 GiB RAM,
4 GiB storage, 600 seconds for the agent and 300 seconds for verification.

`environment/generate_audit_log.py` regenerates the seeded log from the real
PDP and the seeded app (instructions in the script); it is not copied into the
image.

## Verification

`tests/replay.py` kills any PDP or app the agent left running, starts a fresh
PDP on 3592/3593 from `/workspace/policies` with its own `file` audit log,
starts `/workspace/app/app.py` on 8000 with `CERBOS_URL`, a hidden
`INVOICES_FILE` and a random `APP_JWT_SECRET`, and replays 16 hidden requests
with tokens it signs itself. `tests/contract.py` models the policy and defines
the hidden principals (two managers with different cost centres and limits, an
employee, a finance admin) and one fresh invoice per case. `tests/check.py`
grades the capture.

| Stage | Requirement |
| --- | --- |
| `policies_unchanged` | Every file under `/workspace/policies` matches its seed hash; none added. |
| `app_starts` | The PDP and the agent's app start and serve the replay. |
| `approvals` | 12 approve cases return the contract's 200/403: within and exactly at the limit, over the limit, unmanaged centre, draft, already approved, own invoice, another manager's invoice, employee and finance admin. |
| `views` | 4 view cases: employee own/other, manager outside their centres, finance admin. |
| `api_shape` | Every 200 response keeps exactly `id`, `owner`, `costCenter`, `amount`, `status`, `description`, describes the right invoice, and approvals report `status: approved`. |
| `pdp_consulted` | The verifier's PDP audit log has a `CheckResources` decision for every replayed request's invoice and action, carrying `resource.attr.cost_center` with the invoice's centre. |
| `findings` | `/workspace/FINDINGS.md` exists and names the attribute (`cost_center` or `costCenter`, case-insensitive). |

Each stage reports a binary score; overall `reward` is 1 only when all seven pass.

## Validated locally

Harbor 0.23.0 oracle reward 1 and nop reward 0 (nop fails `approvals`,
`pdp_consulted` and `findings`). Replaying the verifier in the built image
against these mutations gives reward 0:

- policy changed to read `R.attr.costCenter`: `policies_unchanged` and
  `pdp_consulted` fail;
- `to_api()` renamed to `cost_center` so the PDP sees it: `api_shape` fails;
- app approves for any manager on a submitted invoice without asking the PDP:
  `approvals` and `pdp_consulted` fail;
- correct mapping but `owner` dropped: `approvals` and `views` fail;
- correct fix with no `FINDINGS.md`: `findings` fails.

## Layout

```text
instruction.md                      Agent-facing request
task.toml                           Identity, limits, and artifacts
environment/Dockerfile              Pinned runtime, SDK, seed copy
environment/requirements.txt        Pinned Python dependencies
environment/workspace/              app/, policies/, cerbos/config.yaml
environment/audit.log               Seeded PDP audit log
environment/generate_audit_log.py   Regenerates audit.log (not in the image)
solution/solve.sh                   Installs the fixed app and findings
solution/app/app.py                 Reference fix
solution/FINDINGS.md                Reference findings
tests/test.sh                       Verifier entrypoint
tests/verify.py                     Stage execution and reward output
tests/contract.py                   Hidden principals, invoices, expected statuses
tests/replay.py                     Starts PDP and app, replays hidden requests
tests/check.py                      Grades the replay
tests/seed_hashes.json              Policy hashes
```

## Running

From the repository root with Docker running:

```bash
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-audit-debug -a oracle
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-audit-debug -a nop
```
