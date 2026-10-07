# Policy CI for a browser-upload store

A pipeline that validates every change and feeds the store from the main branch. A GitHub-connected store (Step 2b) needs only the validation half; Hub syncs the branch itself.

## The rules

- **Validate on every pull request with two compile passes**: `cerbos compile` as normal, then again with `--strict-evaluation`. The strict pass catches conditions that error at runtime, which the normal pass silently treats as false — on a DENY rule that means the deny never fires. `cerbos-policy` explains why both must pass ([compile docs](https://docs.cerbos.dev/cerbos/latest/policies/compile?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-hub-setup_pdp-policies-compile) as fallback). `cerbos/cerbos-compile-action` has no strict option, so run the strict pass as a plain step after `cerbos/cerbos-setup-action`.
- **Upload only on push to the main branch**, after validation passes. Pull requests never write to the store.
- **Upload the policy directory, not the repository root.** Any other JSON under the uploaded path — coverage plans, compile reports, `package.json` — parses as a malformed policy and fails the whole upload.
- **Authenticate with the store credential** (Read & write, created on the store's Client credentials tab). A deployment credential fails with `permission denied for store`. Put the ID and secret in the CI secret store and expose them as the `CERBOS_HUB_CLIENT_ID` and `CERBOS_HUB_CLIENT_SECRET` environment variables, which `cerbosctl` reads; a secret on the command line ends up in the job log and the process table.
- **`upload-git` needs full history.** It diffs from the commit recorded in the store, which a shallow clone does not contain: check out with `fetch-depth: 0`. Pass `--subdirectory policies` when the policies sit in a subfolder, so stored paths are relative to it. `replace-files <dir>` needs neither.

## GitHub Actions

```yaml
name: policies
on:
  pull_request:
  push:
    branches: [main]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: cerbos/cerbos-setup-action@v1
        with:
          version: 0.55.0
      - run: cerbos compile policies
      - run: cerbos compile --strict-evaluation policies

  upload:
    needs: validate
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: cerbos/cerbos-setup-action@v1
        with:
          version: 0.55.0
      - run: cerbosctl hub store upload-git --subdirectory policies
        env:
          CERBOS_HUB_STORE_ID: ${{ vars.CERBOS_HUB_STORE_ID }}
          CERBOS_HUB_CLIENT_ID: ${{ secrets.CERBOS_HUB_CLIENT_ID }}
          CERBOS_HUB_CLIENT_SECRET: ${{ secrets.CERBOS_HUB_CLIENT_SECRET }}
```

Give the upload job a `concurrency` group when merges land close together, so two runs never write the store at once.
