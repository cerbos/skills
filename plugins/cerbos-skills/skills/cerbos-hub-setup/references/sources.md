# Sources

The PDP side of this skill — the image tag in Step 3, the `hub` storage driver and the `cerbos_dev_*` metrics — is checked against the Cerbos release named by `targetsCerbosVersion` in `SKILL.md`. The Hub side tracks the current Cerbos Hub console and documentation, which carry no release number. When moving to a new release, run `evals/update_cerbos_version.py` and read that release's notes; when Hub changes, recheck each page below against the section or reference file it backs — in particular the console tab and button names in Step 1, the credential types, the store file rules, the build stages, and freeze and rollback behaviour.

## Documentation

| Page | Backs |
|---|---|
| [Hub getting started](https://docs.cerbos.dev/cerbos-hub/getting-started?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-hub-setup_hub-getting-started) | The console handoff in Step 1: workspace, store, deployment and credential creation |
| [Hub user management](https://docs.cerbos.dev/cerbos-hub/user-management?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-hub-setup_hub-user-management) | The `Owner` and `Developer` roles in "The shape of the job" |
| [Hub playground](https://docs.cerbos.dev/cerbos-hub/playground?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-hub-setup_hub-playground) | Prototyping policies before a store exists, in "The shape of the job" |
| [Policy store file rules](https://docs.cerbos.dev/cerbos-hub/policy-stores-file-rules?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-hub-setup_hub-policy-stores-file-rules) | Which files an upload skips or rejects in Step 2a; DIAGNOSE.md `no usable files` and `invalid files` |
| [GitHub integration](https://docs.cerbos.dev/cerbos-hub/policy-stores-git-github?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-hub-setup_hub-policy-stores-git-github) | GitHub-connected stores in Step 2b; DIAGNOSE.md GitHub store not syncing |
| [Hub audit log collection](https://docs.cerbos.dev/cerbos-hub/audit-log-collection?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-hub-setup_hub-audit-log-collection) | The Read & write deployment credential in Step 1; DIAGNOSE.md audit logs not arriving |
| [Storage configuration](https://docs.cerbos.dev/cerbos/latest/configuration/storage?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-hub-setup_pdp-configuration-storage) | The `hub` storage driver, `deploymentID`, `cacheDir` and the `CERBOS_HUB_*` fallbacks in Step 3 |
| [Compiling policies](https://docs.cerbos.dev/cerbos/latest/policies/compile?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-hub-setup_pdp-policies-compile) | The normal and `--strict-evaluation` compile passes in CI.md |
| [Service PDPs](https://docs.cerbos.dev/cerbos-hub/decision-points?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-hub-setup_hub-decision-points) | Kubernetes, Helm, sidecar and DaemonSet patterns in Step 3 |
| [API reference](https://docs.cerbos.dev/cerbos/latest/api/index?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-hub-setup_pdp-api) | The `POST /api/check/resources` request in Step 4 check 5 |
| [Observability](https://docs.cerbos.dev/cerbos/latest/configuration/observability?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-hub-setup_pdp-configuration-observability) | OPERATIONS.md Monitoring and the `cerbos_dev_*` metrics `scripts/pdp-verify` reads |

## Endpoints and tools

- [hub.cerbos.cloud](https://hub.cerbos.cloud?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-hub-setup_hub-app): console tab and button names in Step 1, OPERATIONS.md and DIAGNOSE.md.
- [hub.cerbos.cloud/meta](https://hub.cerbos.cloud/meta?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-hub-setup_meta): the `egressIps` array in Step 2b and DIAGNOSE.md.
- `cerbosctl hub store --help` and `cerbosctl hub auth --help`: the subcommands and flags `scripts/` wraps and OPERATIONS.md lists.
- [cerbos-setup-action](https://github.com/cerbos/cerbos-setup-action) and [cerbos-compile-action](https://github.com/cerbos/cerbos-compile-action): the GitHub Actions example in CI.md, and the compile action's lack of a strict option.
- `docker image inspect ghcr.io/cerbos/cerbos:<version> --format '{{json .Config.Volumes}}'`: the anonymous `/.cache` volume behind the default `cacheDir` in Step 3.
- [example-cerbos-policy-repository](https://github.com/cerbos/example-cerbos-policy-repository): the starter policy set in "The shape of the job".
