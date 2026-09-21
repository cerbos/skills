---
name: cerbos-hub-setup
description: Stand up and operate Cerbos Hub — policy store, deployment, client credentials, and a PDP fetching signed bundles. Use when setting up Cerbos Hub for the first time, connecting or configuring a PDP against a Hub deployment, rolling back or freezing a deployment, monitoring connected PDPs, or diagnosing a PDP that will not connect, a stalled deployment, a blocked API key, or a policy store that stopped syncing. Not for authoring the policies themselves, which is `cerbos-policy`.
license: Apache-2.0
compatibility: Requires cerbosctl, and Docker or a local Cerbos binary to run a PDP
metadata:
  author: cerbos
  version: "1.0"
  targetsCerbosVersion: "0.55.0"
allowed-tools: Read Write Edit Glob Grep WebFetch Bash(cerbosctl hub store:*)
---

# Cerbos Hub setup

Get from policies on disk to a PDP serving Hub-built bundles, and keep it running.

## Secrets

A client secret travels from the Hub console to the process that uses it without passing through you. The transcript is a log that gets scrolled, screen-shared and pasted into tickets, so a secret that lands there is exposed. Every script under `scripts/` reads secrets from the environment and reports them only as set or unset, and every command you write holds to the same rule.

- **Uploads need no secret.** The user runs `cerbosctl hub auth` in their own terminal and approves a device code in the browser; the login goes to the OS keyring, where your `cerbosctl` finds it. The command prints its URL and then blocks until approval, so it belongs where the user sees output as it arrives — an agent's shell holds that output until the command exits.
- **The PDP is the one process that needs a secret**, the deployment credential's. Hand the user the Step 3 command to run in a terminal where they have set `CERBOS_HUB_CLIENT_SECRET` — `read -rs CERBOS_HUB_CLIENT_SECRET && export CERBOS_HUB_CLIENT_SECRET` keeps it out of shell history too. Run it yourself only when `scripts/check-prereqs` reports the variable set in your own shell.
- **IDs are not secrets.** Put store IDs, deployment IDs and client IDs on commands yourself: `CERBOS_HUB_STORE_ID=... scripts/store-upload ./policies`.

Confirm a secret by whether it is set, never by its value: `scripts/check-prereqs` in your shell, and `kubectl describe secret <name>` on Kubernetes, which lists each key with its size in bytes. The commands that print a value are read-only, which is why they get run without a second thought — `echo "$CERBOS_HUB_CLIENT_SECRET"`, `env`, `docker inspect` on the PDP container, `kubectl get secret -o yaml`, `helm get values` on a release given the secret with `--set`. Hand those to the user.

A secret that reaches the conversation anyway is exposed. Have the user rotate it on the credential's **Client credentials** tab.

## The shape of the job

Four things have to exist before a PDP can start, and **all four are created in the Hub console — there is no API for creating them**. Walk the user through Step 1 and wait for the IDs; everything after that is yours to run.

| Order | Thing | Carries |
|---|---|---|
| 1 | Organization + workspace | — |
| 2 | Policy store | store ID |
| 3 | Deployment referencing that store | deployment ID |
| 4 | A credential on the deployment, plus one on the store for uploads from CI | client ID + secret |

Creating stores, deployments and credentials — and freezing or rolling back a deployment later — needs the `Owner` or `Developer` role in the workspace ([roles](https://docs.cerbos.dev/cerbos-hub/user-management?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-hub-setup_hub-user-management)).

No policies yet? Fork [example-cerbos-policy-repository](https://github.com/cerbos/example-cerbos-policy-repository) for a working set, or prototype in a Hub [playground](https://docs.cerbos.dev/cerbos-hub/playground?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-hub-setup_hub-playground) and export from there.

## Step 0 — prerequisites

```bash
scripts/check-prereqs
```

It reports which of `cerbosctl`, `docker` and `cerbos` are on PATH, which `CERBOS_HUB_*` variables are set, and how to install what is missing. A PDP needs Cerbos 0.45.1 or later to speak to Hub.

## Step 1 — the console handoff

Give the user these steps and ask them to report back the **store ID**, the **deployment ID** and the deployment credential's **client ID**. The secret stays with them; [Secrets](#secrets) covers where it goes.

1. Sign in at [hub.cerbos.cloud](https://hub.cerbos.cloud?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-hub-setup_hub-app). First time through, the onboarding wizard creates an Organization and its first Workspace.
2. **Policy stores → New store.** Name it after what it holds (`orders-service`), and pick the source:
   - **Browser upload** — contents come from CLI uploads or ZIP drops. Pick this when the policies are on disk or produced by a CI job.
   - **GitHub repository** — Hub mirrors a branch, optionally one subdirectory of it. Pick this when the policies already live in a reviewed repo. Details in Step 2b.
3. **Deployments → New deployment.** Select the store, **Create**. Hub starts the first build; note the deployment ID from the detail page.
4. On the **deployment's Client credentials** tab: **Generate a client credential**, type **Read only**. This is the PDP credential. Choose **Read & write** instead if these PDPs will also ship [audit logs](https://docs.cerbos.dev/cerbos-hub/audit-log-collection?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-hub-setup_hub-audit-log-collection) to Hub.
5. Only when uploads will run from CI or another machine without a browser: on the **store's Client credentials** tab, **Generate a client credential**, type **Read & write**. Interactive uploads use `cerbosctl hub auth` instead.

Each secret is shown once, at creation.

**Store credentials and deployment credentials are scoped to the thing they were created on and are not interchangeable.** Credential-based uploads authenticate with the store credential plus the store ID; PDPs authenticate with the deployment credential plus the deployment ID. Crossing them is the most common setup failure — see [DIAGNOSE.md](references/DIAGNOSE.md) for the errors it produces.

Full console walkthrough with screenshots: [Hub getting started](https://docs.cerbos.dev/cerbos-hub/getting-started?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-hub-setup_hub-getting-started).

## Step 2 — policies into the store

### 2a — CLI upload

Once the user has run `cerbosctl hub auth` (see [Secrets](#secrets)), the store ID is all an upload needs:

```bash
CERBOS_HUB_STORE_ID=... scripts/store-upload ./policies
CERBOS_HUB_STORE_ID=... scripts/store-status
```

Uploads from CI authenticate with the store credential instead, as `CERBOS_HUB_CLIENT_ID` and `CERBOS_HUB_CLIENT_SECRET` in the pipeline's secret store.

`store-upload` wraps `cerbosctl hub store replace-files`, which makes the store's contents exactly what the directory holds. It is safe to point at a repository root: anything the store's [file rules](https://docs.cerbos.dev/cerbos-hub/policy-stores-file-rules?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-hub-setup_hub-policy-stores-file-rules) reject is skipped and listed, while a file that parses as a malformed policy fails the upload outright and leaves the store untouched. Keep test suites and `testdata/` in the store — Hub runs them on every build and strips them from the runtime bundle.

`store-status` prints the version the store is now at. That number is what `--version-must-eq` guards against when more than one writer shares a store; pushing further changes is covered in [OPERATIONS.md](references/OPERATIONS.md).

### 2b — GitHub-connected store

Nothing to upload: Hub mirrors the branch, and every push that changes a policy file triggers a build. Set the branch when connecting the repository, and set the directory field when the policies sit inside a monorepo (`policies/cerbos`).

If the GitHub organization enforces an IP allow list, add Hub's egress addresses or the connection fails with a `403` and an already-connected store stops syncing. Fetch them from [hub.cerbos.cloud/meta](https://hub.cerbos.cloud/meta?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-hub-setup_meta), which returns an `egressIps` array, rather than hard-coding them. Setup details: [GitHub integration](https://docs.cerbos.dev/cerbos-hub/policy-stores-git-github?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-hub-setup_hub-policy-stores-git-github).

### 2c — browser upload

Drag a ZIP onto the store's **Import** tab, with the policies at the root of the archive rather than in a subdirectory. Each upload fully replaces the store's contents.

## Step 3 — connect a PDP

The PDP needs the deployment ID and the **deployment** credential. Fill in the two IDs and hand the command over as [Secrets](#secrets) describes:

```bash
docker run --rm --name cerbos -p 3592:3592 -p 3593:3593 \
  -e CERBOS_HUB_DEPLOYMENT_ID=... -e CERBOS_HUB_CLIENT_ID=... \
  -e CERBOS_HUB_CLIENT_SECRET \
  ghcr.io/cerbos/cerbos:latest server
```

`-e CERBOS_HUB_CLIENT_SECRET` with no `=value` forwards the value from the shell that runs the command, so the secret never reaches the command line. Set `CERBOS_HUB_PDP_ID` as well to name this instance on the Decision points tab; without it Hub generates a random identifier.

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

`deploymentID` and the three credential fields each fall back to their `CERBOS_HUB_*` variable when left out of the file, so the file can carry the IDs while the secret stays in the environment. Mount the file and start with `--config=/conf/.cerbos.yaml`; the rest of the PDP configuration is in the [storage reference](https://docs.cerbos.dev/cerbos/latest/configuration/storage?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-hub-setup_pdp-configuration-storage).

**`cacheDir`** persists downloaded bundles so an unchanged bundle is not re-downloaded on restart. Unset, it defaults to a `cerbos-hub` directory under the OS cache directory, which a container throws away on restart — so set it and mount a persistent volume there.

**Network.** Outbound 443 to `api.cerbos.cloud` and `cdn.cerbos.cloud`; proxies and TLS constraints in [references/DIAGNOSE.md](references/DIAGNOSE.md).

Kubernetes with Helm, sidecar and DaemonSet patterns: [service PDPs](https://docs.cerbos.dev/cerbos-hub/decision-points?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-hub-setup_hub-decision-points).

## Step 4 — verify

All five checks pass before the setup is done.

1. `scripts/store-status` — the uploaded files, at a version number.
2. Hub → the deployment's **Builds** tab — a build whose Compile and Test stages both passed. A failing suite blocks the bundle and leaves the previous one live, which is the designed safety behaviour rather than an outage.
3. `scripts/pdp-verify` — `/_cerbos/health` returns 200 and `cerbos_dev_hub_connected` is `1`.
4. Hub → the deployment's **Decision points** tab — this PDP listed, running the build reference from check 2.
5. One `POST /api/check/resources` request covering a rule whose answer is already known, returning that answer ([API reference](https://docs.cerbos.dev/cerbos/latest/api/index?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-hub-setup_pdp-api)).

A connected PDP running an older build than check 2 reported means the deployment is frozen or pinned by a rollback — see [OPERATIONS.md](references/OPERATIONS.md).

## Step 5 — close the loop

Step 4 proves a PDP can load a bundle. This step proves what Hub is for: a policy change reaching a running PDP with no restart and no release. Run it on a new deployment fed by CLI upload, before anything depends on it.

1. `scripts/pdp-verify` and note `cerbos_dev_store_bundle_updates_count`. The PDP bumps it each time it swaps in a new bundle.
2. Change the rule check 5 exercised so its answer flips — one condition or one role is enough — and upload with `scripts/store-upload`.
3. `scripts/pdp-verify --await-update <count>` returns once the new bundle is live, or after a minute with where to look. Re-running it with the same count keeps waiting.
4. Send the check 5 request again and show the user both responses: same request, different answer, no code shipped.
5. Revert the change and upload again, so the store holds the policies the user intended.

## Scripts

| Script | Does |
|---|---|
| `scripts/check-prereqs` | Which tools are installed, which `CERBOS_HUB_*` variables are set |
| `scripts/hub-login` | `cerbosctl hub auth` forced into the device-code flow — for the user's terminal, like the command it wraps |
| `scripts/store-upload <dir>` | `cerbosctl hub store replace-files`, after checking the environment |
| `scripts/store-status` | The store's current version and file list |
| `scripts/pdp-verify [--await-update N] [host:port]` | PDP health and the `cerbos_dev_hub_connected` gauge; with `--await-update`, waits for the bundle-update counter to pass `N` |

Each takes `-h`. `store-upload` passes extra `cerbosctl` flags through after `--`, and `cerbosctl hub store --help` is the authority on what those flags are.

## References

- [references/OPERATIONS.md](references/OPERATIONS.md) — pushing changes, build life cycle, rollback and freeze, monitoring connected PDPs, metrics
- [references/DIAGNOSE.md](references/DIAGNOSE.md) — the workspace issues Hub raises, `cerbosctl` upload errors, PDP connection failures, GitHub sync failures
