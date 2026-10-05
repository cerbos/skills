# cerbos-pep-python-list-filter

Filter a paginated list endpoint by Cerbos permissions. The
[instruction](instruction.md) asks for `GET /expenses` in an existing FastAPI +
SQLAlchemy + SQLite app to return only the reports the caller may view, with
the `status` filter, `limit`/`offset` paging and `total` still correct, filtering
that scales with the table, and no reports when the PDP cannot answer. It does
not name a skill, `PlanResources`, the adapter, or the verifier's data.

The seed `list_expenses` selects every row (`# TODO` marker). Users live in a
`users` table (`roles` comma-separated, `department`, `region`,
`review_threshold`) and reports in `expenses` (`owner_id`, `department`,
`region`, `amount`, `status`, `archived`). The policy bundle (correct, not to be
changed) uses `R.attr.owner`, so the mapper must send `owner` to `owner_id`, and
it reads `P.attr.department`, `P.attr.region` and `P.attr.review_threshold`,
which the planner resolves from the principal.

| Policy rule | Plan it produces |
| --- | --- |
| `view-own` (derived role `report_owner`) | `owner == <id>` |
| `manager-view-team` | `department == <dept> && status != "draft"` |
| `finance-review-region` | `region == <region> && status in [...] && amount >= <threshold>` |
| `hide-archived` (DENY for employee/manager/finance) | `not(archived == true)` |
| `auditor-view-all` | `KIND_ALWAYS_ALLOWED` for auditors, including an `employee,auditor` user |
| no rule for `contractor` | `KIND_ALWAYS_DENIED` |

The reference solution plans with the gRPC SDK and translates with
`cerbos-sqlalchemy` 0.4.0 (`get_query`, which handles all three kinds), then
ANDs the status filter and paginates and counts in SQL. A hand-written
translator, or fetching every row and filtering in Python with paging applied
afterwards, passes the behavioural checks as long as it plans per caller.

## Environment

The image pins Cerbos 0.55.0 and Python 3.12 on Debian Bookworm by digest and
installs a fully pinned `requirements.txt` (Cerbos Python SDK `cerbos==0.16.0`,
`cerbos-sqlalchemy==0.4.0`, SQLAlchemy 2.0.54, FastAPI 0.142.2, uvicorn 0.54.0,
PyYAML 6.0.2 and transitive dependencies) plus the `sqlite3` CLI. It copies the
policies to `/workspace/policies` and the app to `/workspace/app`, and seeds a
sample database. Cerbos runs natively. Limits: 2 CPUs, 2 GiB RAM, 4 GiB storage,
600 seconds for the agent and 180 seconds for verification.

## Verification

`tests/verify.py` builds a hidden SQLite database (schema copied from the seed
`db.py`) with 10 users and 160 reports (5 owners × 4 statuses × 4 amounts ×
archived or not, IDs shuffled), starts a PDP with decision audit logging from
the verifier's own copy of the bundle (`tests/policies/`), and starts the
agent's app with `DATABASE_URL`, `CERBOS_GRPC_ADDR` and `CERBOS_HTTP_ADDR`.
Expected ID sets come from `tests/contract.py`.

| Stage | Requirement |
| --- | --- |
| `uses_sdk` | A module under `/workspace/app` imports from `cerbos.sdk`. |
| `app_starts` | `uvicorn main:app` starts from `/workspace/app` and `/health` returns 200. |
| `preserved_contract` | No header and an unknown user get 401. |
| `list_visibility` | For each hidden user, `?limit=1000` returns exactly the contract's IDs in ID order and `total` equals their count. Covers conditional plans (owner, team, finance threshold 0 and 1000, manager+finance), an employee who can see nothing, ALWAYS_ALLOWED (auditor, employee+auditor) and ALWAYS_DENIED (contractor). |
| `filters_and_paging` | For each user, each `status` value returns the matching subset and its `total`; paging with `limit=7` reassembles the full list with a constant, correct `total`. |
| `uses_query_plan` | After the calls above, the PDP's decision audit log holds a `planResources` entry for every hidden user. |
| `fail_closed` | With the PDP stopped, listing as an auditor, a manager and a contractor returns an error status (not 2xx, 401, 404 or 422) within 15 seconds. |

Each stage reports a binary score; overall `reward` is 1 only when all pass.
Regenerate `tests/cases.json` with `python tests/contract.py`.

## Validated locally

Harbor 0.23.0 oracle and nop rewards are 1 and 0. Nop passes `app_starts` and
`preserved_contract` and fails the rest. Replaying the verifier in the built
image against these variants of the reference solution gives reward 0:

- ALWAYS_DENIED treated as "no condition, no filter": `list_visibility` and
  `filters_and_paging` fail (the contractor sees all 160 reports);
- ALWAYS_ALLOWED treated as "no condition, nothing matches": `list_visibility`
  and `filters_and_paging` fail (both auditors see nothing);
- principal sent without attributes: `list_visibility` and `filters_and_paging`
  fail (managers and finance lose their team/region rows);
- page from the database first, then `check_resources` on the page:
  `filters_and_paging` (short pages, wrong `total`) and `uses_query_plan` fail;
- plan errors caught and the unfiltered query used: only `fail_closed` fails.

## Layout

```text
instruction.md            Agent-facing request
task.toml                 Identity, limits and artifacts
environment/Dockerfile    Pinned runtime, SDK, adapter and seed database
environment/requirements.txt  Fully pinned Python dependencies
environment/app/          Seed FastAPI + SQLAlchemy app (db.py, main.py, seed.py)
environment/policies/     Correct expense_report view bundle with tests
solution/solve.sh         Installs the reference app files
solution/app/             Reference main.py and authz.py (gRPC SDK + cerbos-sqlalchemy)
tests/test.sh             Verifier entrypoint
tests/verify.py           Stage execution and reward output
tests/harness.py          PDP and app process management, HTTP calls
tests/contract.py         Hidden data and expected IDs; generates cases.json
tests/cases.json          Hidden users, reports and expected IDs
tests/policies/           Verifier copy of the bundle
```

## Running

From the repository root with Docker running:

```bash
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-pep-python-list-filter -a oracle
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-pep-python-list-filter -a nop
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-pep-python-list-filter \
  --skill ./cerbos/cerbos-pep-integration -a codex -m openai/gpt-5.6-luna --agent-kwarg version=0.154.0
```

The model run requires credentials.
