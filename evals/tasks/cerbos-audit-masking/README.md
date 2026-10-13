# cerbos-audit-masking

Turn on audit logging for a PDP so that a compliance team gets a local,
newline-delimited JSON trail at `/var/log/cerbos/audit.log` with personal data,
identity-token claims and credential headers removed by the PDP itself, while
everything an investigator needs survives. The [instruction](instruction.md)
states the requirements in business terms; it does not name config keys.

The trap the task is built around: in Cerbos 0.55.0, `mask` exists only on the
`hub` audit backend. The `file` backend has no masks, so the straightforward
"`backend: file`" answer leaks every field. Hub deployment credentials are in the
environment (`CERBOS_HUB_CLIENT_ID`, `CERBOS_HUB_CLIENT_SECRET`) but Hub is
unreachable; the working answer is the `hub` backend with masks and
`pipeOutput` to the `file` backend, since masks run before the piped copy is
written. The PDP keeps serving while Hub uploads fail. The other traps:

| Requirement | Trap |
| --- | --- |
| PII in principal attributes for checks **and** query plans | `checkResources` and `planResources` are separate mask sections with different roots (`inputs[*]…` and `input…`). |
| No identity token contents | Masking one claim (`auxData.jwt.email`) leaves the others; `aux_data` (snake case) matches nothing and fails silently. |
| `Authorization` / `X-Api-Key` absent, every other header kept | Metadata capture is off by default; an `includeMetadataKeys` allow-list drops the gateway's new headers. `excludeMetadataKeys` (or a `metadata` mask) is required. |
| Investigation fields kept | Masking `inputs[*].principal.attr` wholesale removes `department` and `approval_limit`. |
| Drop always-allowed plan noise, keep grants | `planResources.ignoreAlwaysAllow`; `ignoreAll` also drops conditional and denied plans, and `checkResources.ignoreAllowAll` drops the grant evidence. |

Facts confirmed against the real 0.55.0 binary while building the task:

- With `audit.backend: hub` and no `hub.credentials` (or the env vars), the PDP
  refuses to start. With placeholder credentials and no route to Hub it starts,
  serves, logs upload warnings, and writes piped entries immediately.
- `authorization` is never captured, whatever the metadata key lists say. The
  raw JWT is never logged; the decision entry records decoded claims under
  `auxData.jwt`.
- A `metadata` mask written as the bare key `x-api-key` makes the PDP refuse to
  start (`unexpected character for accessor: -`); the bracket form
  `['x-api-key']` works.
- The `file` backend creates `/var/log/cerbos/` itself.

## Environment

The image pins Cerbos 0.55.0 and Python 3.12 on Debian Bookworm by digest, with
PyYAML 6.0.2, Git, curl, jq and CA certificates. `/workspace` holds
`config.yaml` (disk storage, JWT key set, no audit), `policies/invoice.yaml` and
`jwks.json`. The Hub credentials are placeholder values set with `ENV`. Limits:
2 CPUs, 2 GiB RAM, 4 GiB storage, 600 seconds for the agent and 300 seconds for
verification.

## Verification

`tests/collect.py` kills any PDP the agent left running, deletes
`/var/log/cerbos/audit.log`, starts `cerbos server --config
/workspace/config.yaml` (only the listen addresses are overridden with `--set`),
and sends ten hidden HTTP requests: five `CheckResources` (batched resources,
mixed and allow-only results) and five `PlanResources` (two always-allowed, two
conditional, one always-denied). Each carries randomized PII attributes and
bank account numbers, `Authorization` and `X-Api-Key` headers with random
values, `X-Request-Id`, `X-Tenant-Id` and an unannounced `X-Edge-Trace` header,
and most carry an RS256 identity token in `auxData.jwt`. The tokens are
pre-signed in `tests/tokens.json` against the key in `jwks.json`; the private
key was discarded. The written file is then graded by `tests/check_audit.py`.

| Stage | Requirement |
| --- | --- |
| `policies_unchanged` | `policies/invoice.yaml` and `jwks.json` match their seed hashes; no files added under `policies/`. |
| `pdp_serves` | The PDP starts from the agent's config and answers all ten requests with the effects and plan kinds the unchanged policy gives. |
| `entries_recorded` | Every call has exactly one access entry with the right method; every mixed check and conditional plan has its decision entry. |
| `decision_filters` | Always-allowed plans have an access entry but no decision entry; the always-denied plan and both allow-only checks keep their decision entries. |
| `sensitive_removed` | None of the randomized `ssn`, `email`, `bank_account`, header values, token strings or token claim values appear anywhere in the file; no `ssn`/`email`/`bank_account` attribute keys, no non-empty `auxData`, no `authorization`/`x-api-key` metadata. Fails if the decision entries that carried the data are missing. |
| `investigation_fields` | Decision entries keep principal ID, roles, `department`, `approval_limit`, resource kind, ID, `amount`, `department`, `status`, `owner`, every per-action effect and plan kind; access and decision entries keep all three correlation headers. |

Each stage reports a binary score; overall `reward` is 1 only when all six pass.

## Validated locally

Harbor 0.23.0 oracle reward 1 and nop reward 0 (nop passes only
`policies_unchanged` and `pdp_serves`). The reference also passes with the
container's network disabled. Replaying the verifier in the built image against
these configurations gives reward 0:

- `file` backend with the same headers and filters but no masks:
  `sensitive_removed` fails;
- `hub` + `pipeOutput` with the `planResources` mask section missing:
  `sensitive_removed` fails;
- only the `email` token claim masked (`inputs[*].auxData.jwt.email`):
  `sensitive_removed` fails;
- `aux_data` instead of `auxData` in the mask paths: `sensitive_removed` fails;
- `inputs[*].principal.attr` masked wholesale: `investigation_fields` fails;
- `includeMetadataKeys: [x-request-id, x-tenant-id]` instead of an exclude list:
  `investigation_fields` fails;
- `planResources.ignoreAll`: `entries_recorded`, `decision_filters` and
  `sensitive_removed` fail;
- `checkResources.ignoreAllowAll` added: `decision_filters` fails.

## Layout

```text
instruction.md                Agent-facing request
task.toml                     Identity, limits, and artifacts
environment/Dockerfile        Pinned runtime, placeholder Hub credentials
environment/workspace/        Seed config, policy and JWKS copied to /workspace
solution/solve.sh             Installs the reference config
solution/config.yaml          hub backend + masks + pipeOutput to file
tests/test.sh                 Verifier entrypoint
tests/verify.py               Stage execution and reward output
tests/collect.py              Starts the agent's PDP and sends hidden requests
tests/check_audit.py          Grades the audit file
tests/tokens.json             Pre-signed hidden identity tokens and their claims
tests/seed_hashes.json        Hashes of the files that must not change
```

## Running

From the repository root with Docker running:

```bash
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-audit-masking -a oracle
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-audit-masking -a nop
```
