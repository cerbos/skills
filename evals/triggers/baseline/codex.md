# Trigger report: codex (CLI default model)

- Agent: `codex-cli 0.160.1`, model: the CLI default, which `codex exec --json` does not report
- Skills at commit `ffb3f4c`, run 2026-10-13T16:58:40Z
- 164 runs (82 prompts × 2 repeats), 0 errored and excluded

| Overall | |
| --- | --- |
| Expected skill loaded (recall) | 100% (132/132) |
| Expected skill loaded first | 93% (123/132) |
| Any Cerbos skill loaded on a Cerbos prompt | 100% (132/132) |
| Any Cerbos skill loaded on an unrelated prompt | 3% (1/32) |

Recall: the expected skill loaded at any point. First pick: it was the first Cerbos skill loaded.
Precision: of the runs where the skill loaded, the share where it was expected or listed in `also_ok`.
Near-miss fired: how often it loaded on prompts listing it under `near` (lower is better).

| Skill | Recall | First pick | Precision | Near-miss fired |
| --- | --- | --- | --- | --- |
| `cerbos` | 100% (18/18) | 94% (17/18) | 92% (24/26) | 6% (1/18) |
| `cerbos-audit-insights` | 100% (16/16) | 100% (16/16) | 100% (18/18) | 0% (0/12) |
| `cerbos-authz-migration` | 100% (16/16) | 100% (16/16) | 100% (16/16) | 0% (0/2) |
| `cerbos-embedded-pdp` | 100% (16/16) | 56% (9/16) | 100% (18/18) | 0% (0/10) |
| `cerbos-hub-setup` | 100% (16/16) | 94% (15/16) | 100% (16/16) | 0% (0/6) |
| `cerbos-pep-integration` | 100% (16/16) | 100% (16/16) | 96% (24/25) | 6% (1/18) |
| `cerbos-policy` | 100% (18/18) | 100% (18/18) | 100% (21/21) | 0% (0/24) |
| `cerbos-synapse-extension` | 100% (16/16) | 100% (16/16) | 100% (18/18) | 0% (0/2) |

## Confusion matrix

Rows are the expected skill; columns are the first Cerbos skill loaded.

| expected ↓ / loaded → | router | audit-insights | authz-migration | embedded-pdp | hub-setup | pep-integration | policy | synapse-extension | none |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| router | **17** | 1 | · | · | · | · | · | · | · |
| audit-insights | · | **16** | · | · | · | · | · | · | · |
| authz-migration | · | · | **16** | · | · | · | · | · | · |
| embedded-pdp | 6 | · | · | **9** | · | 1 | · | · | · |
| hub-setup | 1 | · | · | · | **15** | · | · | · | · |
| pep-integration | · | · | · | · | · | **16** | · | · | · |
| policy | · | · | · | · | · | · | **18** | · | · |
| synapse-extension | · | · | · | · | · | · | · | **16** | · |
| none | 1 | · | · | · | · | · | · | · | **31** |

## Misses

Runs where the expected skill did not load, or an unexpected skill did.

| Prompt | Rep | Expected | Loaded |
| --- | --- | --- | --- |
| `epdp-lambda` | 0 | embedded-pdp | pep-integration, embedded-pdp |
| `epdp-lambda` | 1 | embedded-pdp | router, embedded-pdp |
| `none-postgres-role` | 0 | none | router |
