# Sources

This skill pins no release: it tracks the current Cerbos Hub documentation and the `latest` Cerbos PDP documentation. When the PDP or Hub ships a change to auditing, read the release notes, then recheck each page below against the section or reference file it backs — in particular the `audit` block defaults, the backend list, the mask syntax, the Hub console tab names and the roles that can see audit data.

## Documentation

| Page | Backs |
|---|---|
| [Audit configuration](https://docs.cerbos.dev/cerbos/latest/configuration/audit?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-audit-insights_pdp-configuration-audit) | Backend table, configuration and `storagePath` in `SKILL.md`; decision log filters; MASKING.md sections and path syntax; DEBUG.md minimum configuration per backend and `pipeOutput` |
| [Hub audit log collection](https://docs.cerbos.dev/cerbos-hub/audit-log-collection?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-audit-insights_hub-audit-log-collection) | Enabling collection and what a request records in `SKILL.md`; MASKING.md; READING.md audit logs, exports, retention, residency and compliance questions |
| [Hub Insights](https://docs.cerbos.dev/cerbos-hub/insights?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-audit-insights_hub-insights) | READING.md Insights charts, rankings and drill-through |
| [Hub usage dashboard](https://docs.cerbos.dev/cerbos-hub/usage-dashboard?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-audit-insights_hub-usage-dashboard) | READING.md usage dashboard |
| [Hub user management](https://docs.cerbos.dev/cerbos-hub/user-management?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-audit-insights_hub-user-management) | Who can see it in `SKILL.md`; READING.md access and the export role |
| [Hub on-premises deployments](https://docs.cerbos.dev/cerbos-hub/on-premises?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-audit-insights_hub-on-premises) | READING.md on-premises storage and residency |
| [Hub troubleshooting](https://docs.cerbos.dev/cerbos-hub/troubleshooting?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-audit-insights_hub-troubleshooting) | The verify checklist in `SKILL.md` |
| [Hub playground](https://docs.cerbos.dev/cerbos-hub/playground?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-audit-insights_hub-playground) | DEBUG.md reproducing a decision away from the application |
| [`cerbosctl` CLI](https://docs.cerbos.dev/cerbos/latest/cli/cerbosctl?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-audit-insights_pdp-cli-cerbosctl) | `cerbosctl audit` and `cerbosctl decisions` in DEBUG.md and READING.md |

## Tools

- [age](https://age-encryption.org): READING.md export encryption and the decryption command.
