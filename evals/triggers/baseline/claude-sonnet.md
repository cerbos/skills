# Trigger report: claude sonnet

- Agent: `2.1.296 (Claude Code)`, model `sonnet`
- Skills at commit `ffb3f4c`, run 2026-10-13T16:58:40Z
- 164 runs (82 prompts × 2 repeats), 0 errored and excluded
- Cost: $9.72

| Overall | |
| --- | --- |
| Expected skill loaded (recall) | 94% (124/132) |
| Expected skill loaded first | 94% (124/132) |
| Any Cerbos skill loaded on a Cerbos prompt | 96% (126/132) |
| Any Cerbos skill loaded on an unrelated prompt | 0% (0/32) |

Recall: the expected skill loaded at any point. First pick: it was the first Cerbos skill loaded.
Precision: of the runs where the skill loaded, the share where it was expected or listed in `also_ok`.
Near-miss fired: how often it loaded on prompts listing it under `near` (lower is better).

| Skill | Recall | First pick | Precision | Near-miss fired |
| --- | --- | --- | --- | --- |
| `cerbos` | 100% (18/18) | 100% (18/18) | 100% (20/20) | 0% (0/18) |
| `cerbos-audit-insights` | 100% (16/16) | 100% (16/16) | 100% (16/16) | 0% (0/12) |
| `cerbos-authz-migration` | 88% (14/16) | 88% (14/16) | 100% (14/14) | 0% (0/2) |
| `cerbos-embedded-pdp` | 75% (12/16) | 75% (12/16) | 100% (12/12) | 0% (0/10) |
| `cerbos-hub-setup` | 100% (16/16) | 100% (16/16) | 100% (16/16) | 0% (0/6) |
| `cerbos-pep-integration` | 100% (16/16) | 100% (16/16) | 100% (16/16) | 0% (0/18) |
| `cerbos-policy` | 89% (16/18) | 89% (16/18) | 100% (16/16) | 0% (0/24) |
| `cerbos-synapse-extension` | 100% (16/16) | 100% (16/16) | 100% (16/16) | 0% (0/2) |

## Confusion matrix

Rows are the expected skill; columns are the first Cerbos skill loaded.

| expected ↓ / loaded → | router | audit-insights | authz-migration | embedded-pdp | hub-setup | pep-integration | policy | synapse-extension | none |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| router | **18** | · | · | · | · | · | · | · | · |
| audit-insights | · | **16** | · | · | · | · | · | · | · |
| authz-migration | 2 | · | **14** | · | · | · | · | · | · |
| embedded-pdp | · | · | · | **12** | · | · | · | · | 4 |
| hub-setup | · | · | · | · | **16** | · | · | · | · |
| pep-integration | · | · | · | · | · | **16** | · | · | · |
| policy | · | · | · | · | · | · | **16** | · | 2 |
| synapse-extension | · | · | · | · | · | · | · | **16** | · |
| none | · | · | · | · | · | · | · | · | **32** |

## Misses

Runs where the expected skill did not load, or an unexpected skill did.

| Prompt | Rep | Expected | Loaded |
| --- | --- | --- | --- |
| `epdp-hide-delete` | 0 | embedded-pdp | none |
| `epdp-hide-delete` | 1 | embedded-pdp | none |
| `epdp-vue-menu` | 0 | embedded-pdp | none |
| `epdp-vue-menu` | 1 | embedded-pdp | none |
| `migrate-is-admin-mess` | 0 | authz-migration | router |
| `migrate-is-admin-mess` | 1 | authz-migration | router |
| `policy-explain-derived-role` | 0 | policy | none |
| `policy-explain-derived-role` | 1 | policy | none |
