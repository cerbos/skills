# Cerbos Hub policy stores

Getting a validated policy directory into a Hub policy store, and from there onto a PDP.

A **store** holds policy files. A **deployment** references one or more stores, and on every change compiles them, runs every test suite it finds, and pushes a signed bundle to each PDP connected to it. A store on its own distributes nothing — a deployment has to reference it.

## One-time setup

Stores, deployments and client credentials are created in the Hub console; there is no API for creating them. The `cerbos-hub-setup` skill walks that through end to end — console steps, credential kinds, connecting and verifying a PDP, and day-two operations. Start there if this is the first upload.

Two things to carry back here: the store credential and the deployment credential are **not** interchangeable — uploads need the store's, a PDP needs the deployment's — and the upload credential must be **Read & write**.

## Authenticating

`cerbosctl` reads three environment variables:

```bash
export CERBOS_HUB_CLIENT_ID=... CERBOS_HUB_CLIENT_SECRET=... CERBOS_HUB_STORE_ID=...
```

Keep secrets out of command lines and out of the transcript — export them in the user's shell, or have the user run `cerbosctl hub auth`, which opens a device-code flow in the browser and needs no secret pasted anywhere.

Install `cerbosctl` with `brew tap cerbos/tap && brew install cerbos`, `npm install -g cerbosctl`, `npx cerbosctl`, or a [release binary](https://docs.cerbos.dev/cerbos-hub/policy-stores-cli-binary?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-policy_hub-policy-stores-cli-binary).

## Uploading

| Command | Use it when |
|---|---|
| `cerbosctl hub store replace-files <dir\|zip\|->` | The directory is the whole intended contents of the store. Safe to point at a repository root — anything the store rejects is skipped and listed. |
| `cerbosctl hub store upload-git` | The policies live in a git repository. Applies the diff between the commit recorded in the store and `HEAD`. |
| `cerbosctl hub store add-files <paths>` | Adding or updating a handful of named files. |
| `cerbosctl hub store delete-files <paths>` | Removing named files. |

Two behaviours to plan around:

- `add-files` fails the **entire batch** on one rejected file, where `replace-files` skips it and carries on. Prefer `replace-files` for anything bulk.
- `upload-git` reads **committed history, not the working tree**. Uncommitted edits never upload, so commit first. The `cerbos-hub-setup` skill has the full flag set.

Run `cerbosctl hub store --help` for the current flags.

## What the store accepts

Uploads are filtered by fixed rules — there is no ignore-file mechanism. The layout Phase 2 writes already satisfies them; these are the edges worth knowing:

- Only `.json`, `.yaml` and `.yml`. A `README.md` or `Makefile` is not a store file.
- Any path with a dot-prefixed component is rejected, so `.github/` and `.gitlab-ci.yml` never enter the store.
- `_schemas/` must contain JSON. A YAML file there is rejected.
- Files under `testdata/` must be named `principals`, `resources` or `auxdata` (`auxData` and `aux_data` also accepted). Any other name is rejected.
- A test suite is a file ending in `_test` before the extension. A suite named `tests.yaml` is read as a policy and rejected as malformed.
- Malformed **contents** — a bad policy, schema or suite — fail the upload outright in every command. Only rule violations are skippable.

Limits: 5 MiB per file, 15 MiB per zipped `replace-files`, 50 MiB extracted, 25 operations per `add-files`/`delete-files` batch, 1024-character paths. Full rules: [file rules and limits](https://docs.cerbos.dev/cerbos-hub/policy-stores-file-rules?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-policy_hub-policy-stores-file-rules).

Test suites and `testdata/` belong in the store. Hub runs them on every build and strips them from the runtime bundle, so they cost nothing at serving time.

## After the upload

Upload validates that each file parses. The suites run later, when a deployment referencing the store builds a bundle — so a green upload is not a green build.

Watch the deployment's **Builds** tab. A failing suite blocks the bundle and leaves the previous one live, which is the intended safety behaviour, not an outage. Read the failures from the build's **Test** stage and return to Phase 4.

[Deployments](https://docs.cerbos.dev/cerbos-hub/deployments?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-policy_hub-deployments) covers build history, the effect matrix, freezing and rollback.

## Connecting a PDP

Pointing a PDP at the deployment, the YAML and environment-variable forms, bundle caching and connectivity behaviour: the `cerbos-hub-setup` skill.
