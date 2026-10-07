# cerbos-hub-ci-upload

Add GitHub Actions CI to a repository whose `policies/` directory feeds a Cerbos
Hub upload store: validate on every pull request into `main`, and upload to the
store on every push to `main` and nowhere else. The [instruction](instruction.md)
lists two pairs of repository secrets, a credential from the `billing-prod`
deployment and one from the `billing-policies` store, both Read & write, and
leaves the agent to pick. It describes, without naming strict evaluation, a DENY
that silently no-oped on a missing attribute and asks the PR check to catch that
kind of condition. Runners are self-hosted with `cerbos` and `cerbosctl` 0.55.0
on `PATH`, no Docker and no downloads.

What the task exercises from the skills:

- `cerbos-hub-setup` and `cerbos-policy/references/HUB.md`: uploads from CI
  authenticate with the store credential as `CERBOS_HUB_CLIENT_ID` and
  `CERBOS_HUB_CLIENT_SECRET` from the pipeline's secret store; store and
  deployment credentials are not interchangeable; `replace-files` is pointed at
  the policy directory itself, not the repository root that holds
  `coverage-plan.json`; `upload-git` takes `--subdirectory`; secrets stay off
  command lines.
- `cerbos-policy`: validation is a normal `cerbos compile` pass and a
  `--strict-evaluation` pass, which catches a condition erroring at runtime on a
  DENY rule.

The skills do not say whether to pin actions to commit SHAs, so the verifier does
not check it.

## Environment

The image pins Cerbos 0.55.0, cerbosctl 0.55.0 and Python 3.12 on Debian Bookworm
by digest, with PyYAML 6.0.2, Git, curl and CA certificates.
`environment/workspace/` is copied to `/workspace` and committed on `main`:
`policies/` (derived roles, an `invoice` resource policy with a guarded DENY,
a test suite and fixtures), a Node app in `src/` with `package.json`,
`docs/openapi.json`, `coverage-plan.json` at the root, and an existing
`.github/workflows/app.yaml`. Limits: 2 CPUs, 2 GiB RAM, 4 GiB storage, 600
seconds for the agent and 300 seconds for verification.

## Verification

`tests/gha.py` is a small GitHub Actions emulator. For a simulated event it
applies `on:` filters (branches, branches-ignore, paths, paths-ignore, pull
request types), orders jobs by `needs`, evaluates `if:` and `${{ }}` expressions
(`github`, `secrets`, `vars`, `env`, `needs`, `steps`, `matrix`, `runner`, status
functions, `contains`/`startsWith`/`format` and friends), and runs `run:` steps
as a Linux runner does (`bash --noprofile --norc -eo pipefail`), honouring
`env` at every level, `working-directory`, `defaults.run`, `shell`,
`continue-on-error`, `GITHUB_ENV`, `GITHUB_PATH` and `GITHUB_OUTPUT`.
`cerbos/cerbos-compile-action` is emulated as `cerbos compile <policyDir>`
(the action has no strict option); every other `uses:` step, including
`actions/checkout` and `cerbos/cerbos-setup-action`, is a successful no-op, since
the job already runs in a checkout with the tools on `PATH`.

`cerbos` and `cerbosctl` on `PATH` are wrappers that record argv, working
directory, step and exit code and then run the real 0.55.0 binaries.
`CERBOS_HUB_API_ENDPOINT` in the runner environment points the real `cerbosctl`
at `tests/fake_hub.py`, which implements `IssueAccessToken`, `GetCurrentVersion`,
`ListFiles`, `ReplaceFiles` and `ModifyFiles` over Connect with binary protobuf
(gzip-compressed request bodies included), accepts only the verifier's random
secret values, returns `permission denied for store` to a deployment credential,
and records every request including the uploaded file set.

`checks.py simulate` copies the repository, commits the working tree (CI checks
out the pushed commit, and `upload-git` reads history), and runs every workflow
for six events: a pull request into `main` with valid policies and with each of
three hidden breakages in `policies/resource_policies/invoice.yaml`, a push to
`main`, and a push to a feature branch. The checks read that recording.

| Stage | Requirement |
| --- | --- |
| `workflows_valid` | Every workflow under `.github/workflows` parses with `on` and `jobs`; `app.yaml` is unchanged; a policy workflow or job was added. |
| `pr_passes_valid_policies` | On a pull request with the valid policies, at least one `cerbos compile` runs and no step that ran `cerbos` fails. |
| `pr_catches_compile_error` | With a rule referencing an undefined derived role, a step that ran `cerbos` fails the job. |
| `pr_catches_test_failure` | With `refund` removed from the finance rule, so a seed test fails, a step that ran `cerbos` fails the job. |
| `pr_catches_strict_only_failure` | With the `has()` guard removed from the archived-invoice DENY, which passes `cerbos compile` and fails only under `--strict-evaluation`, a step that ran `cerbos` fails the job. |
| `no_upload_outside_main` | No `ReplaceFiles` or `ModifyFiles` reaches the fake Hub for any pull request run or for the feature-branch push. |
| `main_uploads_policies` | On a push to `main`, a store write to `S7NQ4KDZ2WXM` succeeds and the final `ReplaceFiles` holds exactly the files of `policies/`, at paths relative to it, after dropping what Hub's file rules skip (other extensions, dot-prefixed paths). `replace-files` and `upload-git --subdirectory` are both accepted. |
| `main_uses_store_credential` | Every Hub authentication on the push to `main` uses the `HUB_POLICIES_*` store credential, and no client secret appears in any recorded `cerbos` or `cerbosctl` argv. |

Each stage reports a binary score; overall `reward` is 1 only when all eight
pass. The simulation is logged to `simulation.log` and `simulation.json` in the
verifier logs.

## Validated locally

Harbor 0.23.0: oracle reward 1 (`cerbos-hub-ci-upload-oracle-1`), nop reward 0
(`cerbos-hub-ci-upload-nop-1`; every stage fails except
`no_upload_outside_main`).

Replaying the verifier in the built image with `--network none`, starting from
the reference workflow:

| Variant | Result |
| --- | --- |
| `replace-files .` (repository root) | `main_uploads_policies` fails (`coverage-plan.json`, `package.json`, `docs/openapi.json` and `policies/...` paths uploaded) |
| `upload-git` without `--subdirectory` | `main_uploads_policies` fails (same paths) |
| `HUB_DEPLOY_*` credential | `main_uploads_policies` and `main_uses_store_credential` fail (`permission denied for store`) |
| Strict pass removed | `pr_catches_strict_only_failure` fails |
| Upload job's `if:` removed, so pull requests upload | `no_upload_outside_main` fails |
| Push trigger widened to all branches and the job gated only on `push` | `no_upload_outside_main` fails |
| `cerbos compile .` at the repository root | `pr_passes_valid_policies` fails (`coverage-plan.json: unknown field "resources"`), and nothing uploads |
| `--client-secret "${{ secrets.HUB_POLICIES_CLIENT_SECRET }}"` on the command line | `main_uses_store_credential` fails |
| Validation steps with `continue-on-error: true` | all three `pr_catches_*` stages fail |

Equivalent workflows pass: one job running both passes with JSON output and an
`upload-git --subdirectory=policies` step gated by
`${{ github.event_name == 'push' && github.ref_name == 'main' }}`, with a
SHA-pinned checkout and `fetch-depth: 0`; and two workflows, a pull request one
using `cerbos/cerbos-setup-action`, `cerbos/cerbos-compile-action` and a strict
`run:` step, and a push-to-`main` one with `paths:`, job-level credential `env`,
`defaults.run.working-directory: policies` and
`cerbosctl hub store --store-id=S7NQ4KDZ2WXM replace-files .`.

Known limits of the emulation: a workflow that installs tools at run time fails
here as it would on the described runners; reusable workflows (`jobs.<id>.uses`)
and Docker-based steps are not emulated; a matrix runs its first combination
only.

## Layout

```text
instruction.md            Agent-facing request
task.toml                 Identity, limits and artifacts
environment/Dockerfile    Pinned runtime; copies and commits the seed repository
environment/workspace/    Billing repository with policies/ and the app workflow
solution/solve.sh         Installs the reference workflow
solution/workflows/       Reference policies.yaml
tests/test.sh             Verifier entrypoint
tests/verify.py           Runs the simulation, then each stage
tests/checks.py           Simulation driver and the eight checks
tests/gha.py              GitHub Actions emulator
tests/fake_hub.py         Fake Hub API recording authentication and store writes
tests/seed/app.yaml       The original app workflow
```

## Running

From the repository root with Docker running:

```bash
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-hub-ci-upload -a oracle
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-hub-ci-upload -a nop
```
