# cerbos-migrate-inline-checks

Migrate a small Flask invoice service from hand-rolled authorization to Cerbos,
cutting over directly: write the policies and tests, replace every guard with a
PDP call, delete the old logic, and keep every HTTP status code the same. The
[instruction](instruction.md) asks for this in business terms and does not list
the guards; finding them is the task. A full run uses both the migration skill
(guard inventory, mapping, cutover) and the policy skill (policies and tests).

The seed app in `environment/app/` spreads its guards the way real code does:

| Guard | Where | What the migration must preserve |
| --- | --- | --- |
| Inline role check | `handlers.create_invoice`, `handlers.approve_invoice` | `role not in (...)` allowlists. |
| `can()` helper | `permissions.py` | Admin short-circuit, role allowlist for `view`, manager-edits-drafts, and a deny-by-default tail. |
| Ownership | `permissions.py` edit/delete | `owner_id == user.id` with no role test, so owners with an unknown role (`auditor`) may edit and delete their own drafts while being refused `view`. A derived role with named `parentRoles` breaks this. |
| Self-approval deny | `handlers.approve_invoice` | Nobody, admins included, approves their own invoice, but admins skip the 10000 limit. |
| Entitlement flag | `flags.csv_export` + `handlers.export_invoice` | A "feature flag" evaluated on the tenant's plan, so it is authorization; admins on the free plan are refused, and the viewer check is negative, so unknown roles may export. `pdf_layout_v2` is a real rollout flag and stays. |
| Tenant isolation | `handlers._load_invoice` | Other tenants' invoices answer 404, not 403 (a PEP behaviour). |
| Suspended accounts | `auth.load_current_user` middleware | Writes by suspended users are refused with 403 before the invoice is loaded, so a suspended user deleting a missing or cross-tenant invoice gets 403, not 404, and an invalid create body gets 403, not 400. One sample user (`billing-bot`) has no `status` at all, which a strict-mode PDP turns into an error unless the condition guards with `has()`. |
| Validation, not authorization | `_amount_from_body`, approve's `status != "submitted"` | Must stay in the app after the authorization decision: 400 and 409 responses only reach users who were allowed. Moving `status` into the policy turns 409 into 403. |

The reference solution keeps the `can()` signature as the PEP boundary,
adds `app/authz.py` (gRPC SDK client, fail closed), gates writes in the
middleware with a principal-only check against an `api` resource policy, keeps
the 404 tenant pre-check, and moves everything else into an `invoice` resource
policy with an `invoice_owner` derived role (`parentRoles: ["*"]`).

## Environment

The image pins Cerbos 0.55.0 and Python 3.12 on Debian Bookworm by digest, and
installs Flask 3.1.3, the Cerbos Python SDK 0.16.0 and PyYAML 6.0.2 with every
transitive dependency pinned in `environment/requirements.txt` (installed with
`--no-deps` and checked with `pip check`). The seed app is copied to
`/workspace/app`. Cerbos runs natively; Docker is not used. Limits: 2 CPUs,
2 GiB RAM, 4 GiB storage, 900 seconds for the agent (the agent edits an app as
well as writing a policy bundle) and 300 seconds for verification (70 to 150
seconds in practice, depending on host load).

## Verification

| Stage | Requirement |
| --- | --- |
| `compile_normal` | `cerbos compile --output=json /workspace/policies` compiles and every test passes. |
| `generated_tests` | At least one suite ran, with at least 12 passing assertions over at least 5 distinct actions, asserting both `EFFECT_ALLOW` and `EFFECT_DENY`. |
| `compile_strict` | Compilation and tests also pass with `--strict-evaluation`. |
| `app_parity_normal` | The verifier starts a PDP on the agent's policies and the agent's app (`python /workspace/app/server.py`, with `PORT`, `APP_DATA`, `CERBOS_GRPC_ADDR`, `CERBOS_HTTP_ADDR`), loads verifier-owned data (`tests/hidden-data.json`: 3 tenants on pro/free/enterprise plans, 21 users including suspended, `pending` and status-less users and an unknown role, 543 invoices), and replays 742 requests. Every status code must equal the original app's. |
| `app_parity_strict` | The same 742 requests with `engine.strictEvaluation: true`. |
| `pdp_enforced` | The 108 requests the original app answered with 2xx (other than `/health`), replayed against a PDP with no policies, must all be refused, which proves every guard asks the PDP rather than deciding locally. |
| `inline_roles_removed` | AST scan of non-test `.py` files under `/workspace/app`: no role-name literal (`admin`, `manager`, `accountant`, `viewer`) in a comparison, `match` case, or list/tuple/set/dict literal. Building the principal from `user["role"]` is fine. Deliberately lenient: the tenant pre-check and status/body validation may stay. |

Each stage reports a binary score; overall `reward` is 1 only when all seven
pass. `tests/contract.py` models the original service's status codes and
generates `tests/hidden-data.json` and `tests/cases.json`
(`python tests/contract.py`). The hidden matrix covers every requesting user
against view and export on own-tenant, other-tenant and missing invoices; a view
of their own invoice; valid and invalid creates; and edit, delete and approve on
own and other invoices in each status (and at 10000 and 10001 for approve),
cross-tenant and missing, plus invalid edit bodies. Each mutating request
targets its own invoice, so replay order does not matter. The model was checked
against the real seed app: `python tests/contract.py --check-original
http://127.0.0.1:PORT` with the seed app started on `APP_DATA=tests/hidden-data.json`
reports 742/742 matches.

## Validated locally

Harbor 0.23.0 oracle and nop rewards are 1 and 0. Nop fails every stage:
there is no `/workspace/policies`, so neither compile runs and no PDP starts.
Replaying the verifier inside the built image against these hand-made mutations
of the reference gives reward 0:

- policies only, app untouched (inline checks still decide): parity passes,
  `pdp_enforced` and `inline_roles_removed` fail;
- a shadow-style `can()` that calls Cerbos but returns the legacy answer, with
  the admin short-circuit applied to every action: `app_parity_*`,
  `pdp_enforced` and `inline_roles_removed` fail;
- owner derived role with `parentRoles` limited to the four known roles (own
  suite adjusted to agree): `app_parity_*` fail on auditor-owned drafts;
- suspended deny moved into the invoice policy and the middleware gate removed:
  `app_parity_*` fail (404 where the original answers 403 for suspended
  writes to missing and cross-tenant invoices);
- suspended deny written as `P.attr.status == "suspended"` without `has()`, PEP
  omitting an absent status: normal parity passes, `app_parity_strict` fails
  on the status-less user's writes;
- export allowed to named roles only: `app_parity_*` fail for the `auditor`
  role;
- `status == "submitted"` folded into the manager approve rule: `app_parity_*`
  fail (403 where the original answers 409).

## Layout

```text
instruction.md               Agent-facing request
task.toml                    Identity, limits and artifacts
environment/Dockerfile       Pinned runtime; copies the seed app
environment/requirements.txt Pinned Python dependencies
environment/app/             Seed Flask service with inline authorization
solution/solve.sh            Installs the reference policies and app changes
solution/policies/           invoice and api resource policies, derived role, suites
solution/app/                Migrated app: authz.py PEP, can() over Cerbos
tests/test.sh                Verifier entrypoint
tests/verify.py              Stage execution and reward output
tests/contract.py            Original status-code model; generates data and cases
tests/check_app.py           Starts PDP + app and replays the matrix
tests/check_tests.py         Native test suite coverage
tests/check_structure.py     Role-literal scan of the app
tests/hidden-data.json       Verifier-owned tenants, users, invoices
tests/cases.json             Verifier-owned requests and expected statuses
```

## Running

From the repository root with Docker running:

```bash
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-migrate-inline-checks -a oracle
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-migrate-inline-checks -a nop
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-migrate-inline-checks \
  --skill ./cerbos/cerbos-authz-migration --skill ./cerbos/cerbos-policy --skill ./cerbos/cerbos-pep-integration \
  -a codex -m openai/gpt-5.6-luna --agent-kwarg version=0.154.0
```

The model run requires credentials.
