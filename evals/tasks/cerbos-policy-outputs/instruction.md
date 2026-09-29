# Payout policy outputs

Use the installed `cerbos-policy` skill. Requirements below are confirmed; proceed
with implementation. Cerbos 0.55.0 is installed directly in this sandbox. Docker
is unavailable inside the sandbox, so use the native `cerbos` binary for
compilation and tests.

`/workspace/policies/resource_policies/payout.yaml` controls payouts (resource
kind `payout`, version `default`). Principals with the `manager` role always have
a numeric `approval_limit`. Payouts have a numeric `amount`, a string `account`,
and an optional boolean `frozen`, where absence means false.

The payments service reads policy outputs from CheckResources responses to write
audit events and explain denials. Add these outputs without changing any existing
rule's name, actions, roles, effect, or condition:

- `approve-within-limit`: when the rule grants approval, output
  `{"event": "payout_approved", "payout": <payout ID>, "approver": <principal ID>}`.
  When a manager's approval fails the limit condition, output
  `{"reason": "over_limit", "amount": <payout amount>, "limit": <principal approval limit>}`.
- `block-frozen-accounts`: when the rule denies an action on a frozen account,
  output `{"reason": "account_frozen", "account": <payout account>}`. Output
  nothing for payouts that are not frozen.
- `view-payouts`: no output.

Also add a rule named `flag-payouts` so that `clerk` and `manager` may `flag`
payouts for review. Flagging raises a review ticket, so the rule always outputs
`{"event": "payout_flagged", "by": <principal ID>, "priority": <priority>}`, where
the priority is `"high"` for amounts above 10000 and `"normal"` otherwise. Frozen
accounts still block flagging.

Write native Cerbos tests in `resource_policies/payout_test.yaml` with reusable
fixtures in `resource_policies/testdata/principals.yaml` and
`resource_policies/testdata/resources.yaml`. The tests must assert both effects
and outputs:

- the approval event for a payout within the limit, including an amount equal
  to the limit;
- the over-limit reason for a payout just above the limit;
- the frozen-account reason on a frozen payout that the manager could otherwise
  approve;
- the flag event with `"normal"` priority at exactly 10000 and `"high"` priority
  above it, for both clerks and managers;
- the frozen-account reason when flagging a frozen payout.

Compile and run the tests in normal and strict evaluation modes. The bundle must
be self-contained.
