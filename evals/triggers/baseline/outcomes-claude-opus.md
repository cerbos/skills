# Outcome report: claude opus

- Agent: `2.1.296 (Claude Code)`, model `opus`
- Skills at commit `2bcee25 plus this change`, run 2026-10-13T21:14:22Z
- 10 runs (1 cases × 10 repeats)
- Cost: $7.53

No change: nothing written, usually because the agent stopped to ask about the requirements.

| Case | Rule in a Cerbos policy, checked via the PDP | Hard-coded | Both | No change | Incomplete | Policy tests |
| --- | --- | --- | --- | --- | --- | --- |
| `expense-approval-limit` | 9/10 | 0/10 | 0/10 | 1/10 | 0/10 | 9/10 |

| Run | Outcome | Skills loaded | Policy | PDP call | Rule in code | Error |
| --- | --- | --- | --- | --- | --- | --- |
| `expense-approval-limit` #0 | cerbos | cerbos-policy | policies/resource_policies/finance/expense.yaml | yes | – |  |
| `expense-approval-limit` #1 | cerbos | cerbos-policy | policies/resource_policies/finance/expense.yaml | yes | – |  |
| `expense-approval-limit` #2 | cerbos | cerbos, cerbos-policy, cerbos-pep-integration | policies/resource_policies/finance/expense.yaml | yes | – |  |
| `expense-approval-limit` #3 | cerbos | cerbos, cerbos-policy, cerbos-pep-integration | policies/resource_policies/finance/expense.yaml | yes | – |  |
| `expense-approval-limit` #4 | cerbos | cerbos-policy | policies/resource_policies/finance/expense.yaml | yes | – |  |
| `expense-approval-limit` #5 | no change | cerbos-policy | – | no | – |  |
| `expense-approval-limit` #6 | cerbos | cerbos-policy, cerbos-pep-integration | policies/resource_policies/finance/expense.yaml | yes | – |  |
| `expense-approval-limit` #7 | cerbos | cerbos, cerbos-policy, cerbos-pep-integration | policies/resource_policies/finance/expense.yaml | yes | – |  |
| `expense-approval-limit` #8 | cerbos | cerbos, cerbos-policy, cerbos-pep-integration | policies/resource_policies/finance/expense.yaml | yes | – |  |
| `expense-approval-limit` #9 | cerbos | cerbos-policy | policies/resource_policies/finance/expense.yaml | yes | – |  |
