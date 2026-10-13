# Outcome report: claude opus

- Agent: `2.1.296 (Claude Code)`, model `opus`
- Skills at commit `2bcee25 (main)`, run 2026-10-13T21:14:22Z
- 10 runs (1 cases × 10 repeats)
- Cost: $3.27

No change: nothing written, usually because the agent stopped to ask about the requirements.

| Case | Rule in a Cerbos policy, checked via the PDP | Hard-coded | Both | No change | Incomplete | Policy tests |
| --- | --- | --- | --- | --- | --- | --- |
| `expense-approval-limit` | 1/10 | 4/10 | 0/10 | 3/10 | 2/10 | 3/10 |

| Run | Outcome | Skills loaded | Policy | PDP call | Rule in code | Error |
| --- | --- | --- | --- | --- | --- | --- |
| `expense-approval-limit` #0 | hard-coded | cerbos | – | no | src/server.js |  |
| `expense-approval-limit` #1 | hard-coded | cerbos | – | no | src/server.js |  |
| `expense-approval-limit` #2 | incomplete | cerbos-policy | policies/resource_policies/finance/expense.yaml | no | – |  |
| `expense-approval-limit` #3 | no change | cerbos-policy | – | no | – |  |
| `expense-approval-limit` #4 | hard-coded | cerbos | – | no | src/server.js |  |
| `expense-approval-limit` #5 | incomplete | cerbos-policy | policies/resource_policies/finance/expense.yaml | no | – |  |
| `expense-approval-limit` #6 | no change | cerbos-policy | – | no | – |  |
| `expense-approval-limit` #7 | no change | cerbos-policy | – | no | – |  |
| `expense-approval-limit` #8 | hard-coded | cerbos-policy | – | no | src/server.js |  |
| `expense-approval-limit` #9 | cerbos | cerbos-policy | policies/resource_policies/finance/expense.yaml | yes | – |  |
