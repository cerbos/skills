# Managers cannot approve invoices

## Root cause

The application, not the policy. `invoice_resource()` in `app/app.py` built the
Cerbos resource from `Invoice.to_api()`, the JSON shape for the web UI, which
names the cost centre `costCenter`. The `approve-managed` rule in
`policies/invoice.yaml` reads `R.attr.cost_center`. The decision entries in
`/var/log/cerbos/audit.log` show every denied approval carried
`resource.attr.costCenter` and no `cost_center`, so the condition
`R.attr.cost_center in P.attr.managed_cost_centers` could never be satisfied and
every approval fell through to the default deny. Viewing was unaffected because
no view rule reads the cost centre.

## Fix

`invoice_resource()` now maps the attributes the policy reads explicitly
(`owner`, `cost_center`, `amount`, `status`). The policy and the UI's JSON are
unchanged.
