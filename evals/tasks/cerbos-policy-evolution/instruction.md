Update the existing Cerbos policy bundle in `/workspace/policies` for a new invoice approval process.

Accountants may now approve submitted invoices up to and including 5000. Finance admins may approve submitted invoices of any amount. Both roles must belong to the invoice's tenant, must not own the invoice, and must not approve an invoice with `on_hold: true`. `on_hold` is optional: an absent value or `false` permits approval when the other conditions pass. A principal with both roles gets the finance admin allowance. All other roles remain unable to approve invoices.

Preserve existing read and delete behavior: employees, accountants and finance admins may read invoices in their tenant; only finance admins may delete drafts in their tenant. Unknown actions remain denied. Keep invoice resource kind `invoice` and policy version `default`. Keep the unrelated `audit.yaml` and `audit_test.yaml` files byte-for-byte unchanged.

Update the existing invoice tests, retaining their named regression cases (adjust the obsolete approval expectation). Add active tests for the 5000/5001 boundary, unlimited finance admin and mixed-role approval, held invoices for both approving roles, an explicit false hold flag, self-approval for both roles, and finance admin approval denial for draft and paid invoices. Preserve coverage of read, delete and foreign-tenant denial. Existing fixture names may be reused or extended.

Leave a working policy bundle and tests that pass `cerbos compile /workspace/policies` and `cerbos compile --strict-evaluation /workspace/policies`.

Use the installed `cerbos-policy` skill. This change is approved: the higher accountant limit reduces routine escalations, finance admins handle larger invoices, and holds plus self-approval restrictions protect review integrity. The role effects, resource purpose and requirements above are confirmed; proceed with implementation. Cerbos 0.55.0 is installed as a native `cerbos` executable. Docker is unavailable inside this environment; use the native compiler and tests.
