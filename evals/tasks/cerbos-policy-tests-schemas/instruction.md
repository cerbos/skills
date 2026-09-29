# Attribute schemas and policy tests

Use the installed `cerbos-policy` skill. Requirements below are confirmed; proceed
with implementation. Cerbos 0.55.0 is installed directly in this sandbox. Docker
is unavailable inside the sandbox, so use the native `cerbos` binary for
compilation and tests.

`/workspace/policies` contains two working resource policies without attribute
schemas or tests: `resource_policies/finance/expense.yaml` (kind `expense`) and
`resource_policies/hr/leave_request.yaml` (kind `leave_request`), both version
`default`. Do not change their rules; add schemas and tests around them.

## Attribute schemas

Our PDP rejects requests whose attributes do not match the declared schemas, so
malformed data is denied instead of being evaluated. Add JSON schemas and
reference them from both policies:

- `_schemas/principal.json`, shared by both policies. `department` is required
  and is one of `finance`, `hr`, or `sales`. `approval_limit` is optional and is a
  number of at least 0. No other principal attributes are allowed.
- `_schemas/resources/expense.json`. Required: `owner` (string), `department`
  (one of the three departments), `amount` (number of at least 0), and `status`
  (`draft`, `submitted`, or `approved`). No other attributes are allowed.
- `_schemas/resources/leave_request.json`. Required: `owner` (string),
  `department` (one of the three departments), and `days` (an integer from 1 to
  30 inclusive). No other attributes are allowed.

Clients check `create` before the server has assigned a new record's attributes,
so resource attributes must not be validated for `create`. Principal attributes
are always validated.

## Tests

Write native Cerbos test suites in two styles:

- `resource_policies/finance/expense_test.yaml` takes every principal and
  resource from shared fixture files:
  `resource_policies/finance/testdata/principals.yaml` and
  `resource_policies/finance/testdata/resources.yaml`. The suite itself defines
  no principals or resources.
- `resource_policies/hr/leave_request_test.yaml` is self-contained: it defines
  its principals and resources inline. There is no
  `resource_policies/hr/testdata/` directory.

Each suite must actively test its policy's allowed and denied decisions: an
employee viewing their own record and being denied someone else's, a manager
approving a record in their department and being denied one from another
department, and an employee creating a record. Each suite must also show that
schema validation denies a request the policy would otherwise allow when the
principal has an invalid attribute, when the resource is missing a required
attribute, when a resource attribute has an invalid value, and when the resource
has an unknown attribute. Each suite must show that a `create` check succeeds
for a resource with incomplete attributes.

Compile and run the tests in normal and strict evaluation modes. The bundle must
be self-contained.
