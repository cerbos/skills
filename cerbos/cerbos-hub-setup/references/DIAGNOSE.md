# Diagnosing a Hub setup

Start from the symptom.

## The issues bar

Hub continuously checks the workspace and surfaces problems in an issues bar across every page, each linking to the page that resolves it. Three conditions raise one:

**Blocked API keys.** A credential used by PDPs or by audit log collection has been blocked. PDPs authenticating with it cannot connect, and running ones keep serving their cached bundle while getting no updates. Rotate or re-enable the credential on the owning store or deployment's **Client credentials** tab, then restart the PDPs with the new values.

**Stalled deployment.** A deployment was mapped to a new policy store and no new build has been activated for it in the last 15 minutes, so connected PDPs may still be serving an older bundle. Open its Builds tab: an Upcoming version sitting there means the deployment is frozen or pinned by a rollback; a failed build means compilation or the test suites blocked it.

**Store sync failures.** A GitHub-connected store is failing to sync, so recent repository changes are not reaching Hub. See [GitHub store not syncing](#github-store-not-syncing).

## `cerbosctl` upload errors

`cerbosctl hub store` exits 2 on a command error, 6 when a `--version-must-eq` condition was not satisfied, and 1 when a download found nothing.

| Message | Cause |
|---|---|
| `failed to authenticate to Cerbos Hub` | `CERBOS_HUB_CLIENT_ID` / `CERBOS_HUB_CLIENT_SECRET` wrong or unset, and no saved login in the keyring |
| `permission denied for store` | The credential is not scoped to this store, or is read-only. A **deployment** credential lands here — uploads need the credential created on the **store**, type Read & write |
| `store doesn't exist` | `CERBOS_HUB_STORE_ID` names no store the credential can see |
| `no usable files` | Every file broke a [file rule](https://docs.cerbos.dev/cerbos-hub/policy-stores-file-rules.md?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=skill&utm_content=cerbos-hub-setup); the ignored files are listed. Usually the wrong directory, or a tree holding no `.yaml`/`.yml`/`.json` |
| `invalid files` | A file classified as a policy, schema or test suite failed validation. Each is listed with its cause, and nothing was uploaded — content errors are never skipped |
| `store not modified due to unsatisfied version condition` | Another writer moved the store past the version passed to `--version-must-eq` |
| `invalid request` | Request-level validation, listed field by field |

`add-files` fails the entire batch on one rejected file where `replace-files` skips it and carries on, so prefer `replace-files` for anything bulk.

## PDP fails to start

The PDP contacts Hub at startup and refuses to start when it cannot reach it, so a startup failure is almost always credentials or egress. A Hub *API* outage alone does not block a cold start: the last built bundle for each deployment is served from `cdn.cerbos.cloud` independently of the API, encrypted to your client credentials, so a new PDP boots from the CDN and picks up the API connection in the background. Losing egress to the CDN is what stops a cold start.

- **Wrong credential kind.** PDPs use the credential created on the **deployment**, not the store. Read only is enough to receive bundles; audit log upload needs Read & write.
- **Wrong deployment ID.** `CERBOS_HUB_DEPLOYMENT_ID` must match the ID on the deployment detail page. Exactly one of `storage.hub.remote.deploymentID` or `playgroundID` may be set — supplying both, or neither, fails configuration validation.
- **Egress blocked.** Outbound 443 to `api.cerbos.cloud` and `cdn.cerbos.cloud` through every firewall, security group and network policy in the path. TLS 1.3 is required, so a middlebox that terminates and downgrades TLS is refused. Set `HTTPS_PROXY` and `NO_PROXY` where a proxy is mandatory.
- **Revoked credential.** Client credentials do not expire, but they can be revoked or blocked. Check the credential's status in Hub.

Last resort when Hub is unreachable and the PDP must come up: switch it to the `git` storage driver pointed at the policy repository. That gives up pre-compilation, testing and central management, so treat it as a bridge rather than a destination.

## PDP runs, but on the wrong bundle

Compare the build reference on the deployment's Decision points tab against the latest green build on the Builds tab.

- The latest build **failed** — the previous bundle is still live by design. Fix the policies and let the next build replace it.
- The deployment is **frozen or pinned by a rollback** — new builds queue under Upcoming versions. Unfreeze when the pin is no longer wanted ([OPERATIONS.md](OPERATIONS.md)).
- The PDP has `storage.hub.remote.disableAutoUpdate` set, which stops it applying new bundles at all.

## PDP shows disconnected in Hub

`cerbos_dev_hub_connected` is `0`, or Decision points shows a stale *Last seen*, while the PDP keeps answering authorization requests from its cached bundle.

- **Network interruption** — it reconnects by itself once egress is restored.
- **Process gone** — check the container is running and read its logs for the crash.
- **Load balancer idle timeout** closing the long-lived update stream. The PDP heartbeats every 180s by default, so a proxy that times out faster will keep cutting the connection. Raising the proxy's idle timeout above 180s is the supported fix. The interval itself is settable at `hub.connection.heartbeatInterval` (minimum 30s), but that block is deliberately excluded from the published configuration reference — treat it as unsupported and liable to change, and reach for it only with Cerbos support.

## Build fails

**Compilation errors** — invalid YAML, a policy that does not match the schema, an invalid CEL condition, or a duplicate resource/action combination within a scope across contributing stores. The build details name the file and line.

**Test failures** — Hub runs every suite it finds across the contributing stores, under its own engine. A suite that passes locally and fails here usually has a fixture missing from `testdata/` or an expectation that has drifted from the policy. Read the failure from the build's Test stage, fix it in the source, and re-upload.

Either way the previous bundle stays live, so a red build is a blocked change rather than an outage.

## GitHub store not syncing

- **Wrong branch** — Hub tracks the branch configured on the store, and pushes elsewhere are ignored.
- **Nothing relevant changed** — a build is triggered by policy file changes, not by every commit.
- **Webhook disabled** in the repository's settings.
- **`403` from an organization IP allow list** — add Hub's egress addresses, fetched from [hub.cerbos.cloud/meta](https://hub.cerbos.cloud/meta?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=skill&utm_content=cerbos-hub-setup) as `egressIps`. This is a different setting from the IP allowlist on an ePDP rule, which governs who may download embedded bundles.
- **More than three tags pushed at once** — GitHub does not notify connected apps for such a push. Cap references per push at three.

## Audit logs not arriving

`audit.enabled` true, `audit.backend` set to `hub`, `audit.hub.storagePath` pointing at a writable directory for the local buffer, and the deployment credential created as **Read & write** — a read-only credential cannot upload. Logs are buffered locally and flushed when connectivity allows, so a full volume or a crash between syncs loses entries; mount a persistent volume for the buffer. Details: [audit log collection](https://docs.cerbos.dev/cerbos-hub/audit-log-collection.md?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=skill&utm_content=cerbos-hub-setup).
