---
name: cerbos-hub-setup
description: Stand up and operate Cerbos Hub — policy store, deployment, client credentials, and a PDP fetching signed bundles. Use when setting up Cerbos Hub for the first time, connecting or configuring a PDP against a Hub deployment, rolling back or freezing a deployment, monitoring connected PDPs, or diagnosing a PDP that will not connect, a stalled deployment, a blocked API key, or a policy store that stopped syncing.
license: Apache-2.0
compatibility: Requires cerbosctl, and Docker or a local Cerbos binary to run a PDP
metadata:
  author: cerbos
  version: "1.0"
  targetsCerbosVersion: "0.55.0"
allowed-tools: Read Write Edit Bash Glob Grep WebFetch
---

# Cerbos Hub setup

Get from policies on disk to a PDP serving Hub-built bundles, and keep it running.

## Secrets

Client secrets live in the user's environment and travel from there into the process that needs them. Read them as `CERBOS_HUB_CLIENT_SECRET`, pass that variable onward, and let the user export it in their own shell. Every script under `scripts/` works this way, and so must every command written into the transcript.

## The shape of the job

Four things have to exist before a PDP can start, and **all four are created in the Hub console — there is no API for creating them**. Walk the user through Step 1 and wait for the IDs; everything after that is yours to run.

| Order | Thing | Carries |
|---|---|---|
| 1 | Organization + workspace | — |
| 2 | Policy store | store ID |
| 3 | Deployment referencing that store | deployment ID |
| 4 | One credential on the store, one on the deployment | client ID + secret |

Creating stores, deployments and credentials — and freezing or rolling back a deployment later — needs the `Owner` or `Developer` role in the workspace ([roles](https://docs.cerbos.dev/cerbos-hub/user-management)).

No policies yet? Fork [example-cerbos-policy-repository](https://github.com/cerbos/example-cerbos-policy-repository) for a working set, or prototype in a Hub [playground](https://docs.cerbos.dev/cerbos-hub/playground) and export from there.

## Step 0 — prerequisites

```bash
scripts/check-prereqs
```

It reports which of `cerbosctl`, `docker` and `cerbos` are on PATH, which `CERBOS_HUB_*` variables are set, and how to install what is missing. A PDP needs Cerbos 0.45.1 or later to speak to Hub.

## Step 1 — the console handoff

Give the user these steps and ask them to report back the **store ID** and the **deployment ID**, and to have both credential secrets ready to export.

1. Sign in at [hub.cerbos.cloud](https://hub.cerbos.cloud). First time through, the onboarding wizard creates an Organization and its first Workspace.
2. **Policy stores → New store.** Name it after what it holds (`orders-service`), and pick the source:
   - **Browser upload** — contents come from CLI uploads or ZIP drops. Pick this when the policies are on disk or produced by a CI job.
   - **GitHub repository** — Hub mirrors a branch, optionally one subdirectory of it. Pick this when the policies already live in a reviewed repo. Details in Step 2b.
3. **Deployments → New deployment.** Select the store, **Create**. Hub starts the first build; note the deployment ID from the detail page.
4. On the **store's Client credentials** tab: **Generate a client credential**, type **Read & write**. This is the upload credential.
5. On the **deployment's Client credentials** tab: **Generate a client credential**, type **Read only**. This is the PDP credential. Choose **Read & write** instead if these PDPs will also ship [audit logs](https://docs.cerbos.dev/cerbos-hub/audit-log-collection) to Hub.

Each secret is shown once, at creation.

**Store credentials and deployment credentials are scoped to the thing they were created on and are not interchangeable.** Uploads authenticate with the store credential plus the store ID; PDPs authenticate with the deployment credential plus the deployment ID. Crossing them is the most common setup failure — see [DIAGNOSE.md](references/DIAGNOSE.md) for the errors it produces.

Full console walkthrough with screenshots: [Hub getting started](https://docs.cerbos.dev/cerbos-hub/getting-started).

## Step 2 — policies into the store

### 2a — CLI upload

Ask the user to export these in the shell that will run the upload:

```bash
export CERBOS_HUB_STORE_ID=...      # from the store's detail page
export CERBOS_HUB_CLIENT_ID=...     # store credential, read & write
export CERBOS_HUB_CLIENT_SECRET=... # store credential, read & write
```

Or skip the secret entirely: `scripts/hub-login` runs `cerbosctl hub auth` in device-code mode, the user approves in a browser, and the token is saved to the OS keyring. After that only `CERBOS_HUB_STORE_ID` is needed.

```bash
scripts/store-upload ./policies
scripts/store-status
```

`store-upload` wraps `cerbosctl hub store replace-files`, which makes the store's contents exactly what the directory holds. It is safe to point at a repository root: anything the store's [file rules](https://docs.cerbos.dev/cerbos-hub/policy-stores-file-rules) reject is skipped and listed, while a file that parses as a malformed policy fails the upload outright and leaves the store untouched. Keep test suites and `testdata/` in the store — Hub runs them on every build and strips them from the runtime bundle.

`store-status` prints the version the store is now at. That number is what `--version-must-eq` guards against when more than one writer shares a store; pushing further changes is covered in [OPERATIONS.md](references/OPERATIONS.md).

### 2b — GitHub-connected store

Nothing to upload: Hub mirrors the branch, and every push that changes a policy file triggers a build. Set the branch when connecting the repository, and set the directory field when the policies sit inside a monorepo (`policies/cerbos`).

If the GitHub organization enforces an IP allow list, add Hub's egress addresses or the connection fails with a `403` and an already-connected store stops syncing. Fetch them from [hub.cerbos.cloud/meta](https://hub.cerbos.cloud/meta), which returns an `egressIps` array, rather than hard-coding them. Setup details: [GitHub integration](https://docs.cerbos.dev/cerbos-hub/policy-stores-git-github).

### 2c — browser upload

Drag a ZIP onto the store's **Import** tab, with the policies at the root of the archive rather than in a subdirectory. Each upload fully replaces the store's contents.

## Step 3 — connect a PDP

The PDP needs the deployment ID and the **deployment** credential.

```bash
docker run --rm --name cerbos -p 3592:3592 -p 3593:3593 \
  -e CERBOS_HUB_DEPLOYMENT_ID -e CERBOS_HUB_CLIENT_ID -e CERBOS_HUB_CLIENT_SECRET \
  ghcr.io/cerbos/cerbos:latest server
```

Naming a variable with no `=value` forwards its value from the caller's shell, so the secret never reaches the command line. Set `CERBOS_HUB_PDP_ID` as well to name this instance on the Decision points tab; without it Hub generates a random identifier.

The configuration-file equivalent:

```yaml
hub:
  credentials:
    clientID: "..."
    clientSecret: "..."      # omit and let CERBOS_HUB_CLIENT_SECRET supply it
    pdpID: "orders-pdp-01"   # optional
storage:
  driver: hub
  hub:
    remote:
      deploymentID: "..."
      cacheDir: /var/cerbos/hub
```

`deploymentID` and the three credential fields each fall back to their `CERBOS_HUB_*` variable when left out of the file, so the file can carry the IDs while the secret stays in the environment. Mount the file and start with `--config=/conf/.cerbos.yaml`; the rest of the PDP configuration is in the [storage reference](https://docs.cerbos.dev/cerbos/latest/configuration/storage).

**`cacheDir`** persists downloaded bundles so an unchanged bundle is not re-downloaded on restart. Unset, it defaults to a `cerbos-hub` directory under the OS cache directory, which a container throws away on restart — so set it and mount a persistent volume there.

**Network.** Outbound HTTPS on 443 to `api.cerbos.cloud` (the long-lived update stream and audit ingest) and `cdn.cerbos.cloud` (every bundle download). TLS 1.3 is required and a proxy that downgrades below it is refused. `HTTP_PROXY`, `HTTPS_PROXY` and `NO_PROXY` are honoured.

**Startup versus runtime.** The PDP contacts Hub at startup and fails to start if it cannot be reached — caching does not buy an offline start. A PDP starting while the Hub API is down can still come up from the last built bundle, which is served from the CDN independently of the API. Once running, a PDP keeps serving its current bundle through an interruption and reconnects in the background, so authorization decisions are unaffected.

Kubernetes with Helm, sidecar and DaemonSet patterns: [service PDPs](https://docs.cerbos.dev/cerbos-hub/decision-points).

## Step 4 — verify

All five checks pass before the setup is done.

1. `scripts/store-status` — the uploaded files, at a version number.
2. Hub → the deployment's **Builds** tab — a build whose Compile and Test stages both passed. A failing suite blocks the bundle and leaves the previous one live, which is the designed safety behaviour rather than an outage.
3. `scripts/pdp-verify` — `/_cerbos/health` returns 200 and `cerbos_dev_hub_connected` is `1`.
4. Hub → the deployment's **Decision points** tab — this PDP listed, running the build reference from check 2.
5. One `POST /api/check/resources` request covering a rule whose answer is already known, returning that answer ([API reference](https://docs.cerbos.dev/cerbos/latest/api/index)).

A connected PDP running an older build than check 2 reported means the deployment is frozen or pinned by a rollback — see [OPERATIONS.md](references/OPERATIONS.md).

## Scripts

| Script | Does |
|---|---|
| `scripts/check-prereqs` | Which tools are installed, which `CERBOS_HUB_*` variables are set |
| `scripts/hub-login` | `cerbosctl hub auth` via the device-code flow, saved to the OS keyring |
| `scripts/store-upload <dir>` | `cerbosctl hub store replace-files`, after checking the environment |
| `scripts/store-status` | The store's current version and file list |
| `scripts/pdp-verify [host:port]` | PDP health and the `cerbos_dev_hub_connected` gauge |

Each takes `-h`. `store-upload` passes extra `cerbosctl` flags through after `--`, and `cerbosctl hub store --help` is the authority on what those flags are.

## References

- [references/OPERATIONS.md](references/OPERATIONS.md) — pushing changes, build life cycle, rollback and freeze, monitoring connected PDPs, metrics
- [references/DIAGNOSE.md](references/DIAGNOSE.md) — the workspace issues Hub raises, `cerbosctl` upload errors, PDP connection failures, GitHub sync failures
