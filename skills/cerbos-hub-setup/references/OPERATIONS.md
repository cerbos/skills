# Operating a Hub deployment

Everything after the first green build: pushing changes, controlling what is live, and watching the fleet.

## Pushing a change

**A browser-upload store, from a directory.** `scripts/store-upload <dir>` replaces the whole store. When another writer might be touching the same store, read the version first with `scripts/store-status` and guard the write:

```bash
scripts/store-upload ./policies -- --version-must-eq 41 --message "add refund rules"
```

Exit code 6 means the store had moved on and nothing was written. Re-read the version, rebase the change, retry.

**A browser-upload store, from a git repository.** `cerbosctl hub store upload-git` applies a commit range as a diff instead of re-uploading everything, and records the commit in the store so the next run knows where to start.

| Flag | Effect |
|---|---|
| `--to` | Revision to diff to. Defaults to `HEAD`. |
| `--from` | Revision to diff from. Must be an ancestor of `--to`. Omit it to start from the commit recorded in the store's current version. |
| `--path` | Path to the repository. Defaults to the working directory. |
| `--subdirectory` (`--subdir`) | Upload only this subdirectory of the repository, stripping the prefix from the stored paths. |
| `--version-must-eq` | Same guard as above. |
| `--message` | Commit message recorded against the store version. Defaults to the git commit's own message. |

It reads **committed history, not the working tree**, so uncommitted edits never upload — commit first. When the store's current version carries no git details (a store previously filled by `replace-files` or the browser), `upload-git` replaces the whole store with the files at `--to` rather than applying a diff. Changes go up in batches of 25 operations, and a file over 5 MiB aborts the run.

Run `cerbosctl hub store --help` for the current flag set and the other subcommands (`add-files`, `delete-files`, `get-files`, `download`).

**A GitHub-connected store.** Push to the tracked branch. Hub syncs and builds; there is nothing to run locally.

## Build life cycle

Any change to a store feeding a deployment launches a build, which runs four stages:

1. **In progress** — queued.
2. **Compilation** — policies from every contributing store compiled together.
3. **Test execution** — every test suite found across the contributing stores.
4. **Bundle generation** — the bundle is built and every PDP on the deployment is pushed a notification to download and activate it.

A failure at stage 2 or 3 stops there and the previously built bundle stays live. Open the build reference to read the Compile and Test stage output, and the bundle file explorer to confirm what actually shipped.

## The Builds tab

Two tables. **Upcoming versions** holds builds newer than the live version that have not replaced it — normally transient, and permanent while the deployment is frozen. **Deployed versions** is the history, each row carrying the build reference, *Active from*, *Active to* (a dash for the live one) and the number of contributing sources. Expanding a row lists each contributing store and its version, and each store name links to its Policies tab at that version — which is how you answer "what exactly was in effect at 14:20 last Tuesday".

## Freeze and rollback

**Freeze** (deployment **Settings** tab → *Freeze deployment*) holds the live version in place. Changes to the contributing stores still build, but the results queue under Upcoming versions instead of reaching PDPs, and the deployment is labelled *Frozen*. *Unfreeze deployment* builds and deploys the latest policies, replacing whatever was live.

**Roll back** is the action on any deployed version older than the live one; **Promote** appears on versions newer than the live one, which is what you see once a rollback has pinned the deployment backwards. Either one deploys that version immediately **and freezes the deployment**, so the version you picked survives the next policy change landing in a contributing store. Unfreezing releases the pin and deploys the latest.

If someone else changes the same deployment while the page is open, the action is rejected and the page refreshes — re-read the state before retrying.

## Reading what is deployed

The deployment's **Policies** tab toggles between two views of the current build, with a bundle selector for looking at earlier ones.

**Source view** lists the files in the bundle exactly as compiled.

**Effect matrix** lays roles and actions on the axes for a chosen resource, policy version and scope, each cell showing `Allow`, `Deny` or `Conditional` (the effect depends on a condition evaluated at request time). Cells influenced by a wildcard rule such as `*` or `foo:*` are flagged so the broader grant is visible. Derived roles and role-policy custom roles each get their own row. Selecting a cell drills into the rules that produce it.

The matrix reports which rules *match* a cell rather than fully evaluating the policy, so: effects are for the selected scope only and a scoped policy higher up can override them; derived-role rules do not show in the cells of the roles they extend; role-policy rules do not show in the cells whose effects they restrict.

**Download policies** gives the build's files as a zip, one folder per contributing store, following the bundle selector — useful for diffing a live build against the policy repository.

## Monitoring

**Decision points tab** (per deployment) lists recently connected PDP instances with the PDP ID, the build each is running, active sessions, Cerbos version, when it was last seen, and a link to its audit logs. A fleet split across two build references is a rollout in flight; one stuck there is not.

**Prometheus metrics** at `/_cerbos/metrics` on each PDP:

| Metric | Reports |
|---|---|
| `cerbos_dev_hub_connected` | `1` connected to Hub, `0` disconnected and serving the cached bundle |
| `cerbos_dev_store_bundle_updates_count` | Bundle updates received |
| `cerbos_dev_store_bundle_op_latency` | Time taken by bundle operations |
| `cerbos_dev_store_bundle_fetch_errors_count` | Errors downloading bundles |

`scripts/pdp-verify` reads these for a single PDP. Alert on `cerbos_dev_hub_connected` dropping to 0 and on `cerbos_dev_store_bundle_fetch_errors_count` climbing. Full metric list: [observability](https://docs.cerbos.dev/cerbos/latest/configuration/observability?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-hub-setup_pdp-configuration-observability).

**Workspace issues bar** appears across every Hub page when something needs attention — [DIAGNOSE.md](DIAGNOSE.md) covers what each issue means.
