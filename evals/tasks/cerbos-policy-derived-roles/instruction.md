# Shared derived roles

Use the installed `cerbos-policy` skill. Requirements and ALLOW/DENY effects below
are confirmed; proceed with implementation. Cerbos 0.55.0 is installed directly
in this sandbox. Docker is unavailable inside the sandbox, so use the native
`cerbos` binary for compilation and tests.

Create a Cerbos policy bundle under `/workspace/policies` for `document` and
`expense` resources, both using version `default`.

Principals have string attributes `tenant` and `department`. Resources have string
attributes `tenant`, `department`, and `owner` (a principal ID). These attributes
are present on valid requests.

Define a single shared derived-role policy named `tenant_roles`:

- `employee_owner`: requires the parent role `employee`, matching principal and
  resource tenants, and the resource owner equal to the principal ID.
- `department_reviewer`: requires the parent role `reviewer`, matching tenants,
  and matching departments.

Both resource policies must import this policy and grant permissions using its
`derivedRoles`, keeping relationship and tenant conditions in the shared policy.
For both resource kinds, owners can `view` and `edit` to maintain their own work;
department reviewers can `view` and `approve` to review their department’s work. A principal qualifying for both gets their combined
permissions. Other requests, including `delete`, are denied. Matching attributes
alone never grant access without the appropriate parent role; possessing a role
alone never crosses a tenant or relationship boundary. Derived-role names supplied
as principal roles must not impersonate those derived roles.

Use these paths:

- `derived_roles/tenant_roles.yaml`
- `resource_policies/document.yaml` and `resource_policies/expense.yaml`
- `resource_policies/document_test.yaml` and `resource_policies/expense_test.yaml`

Supply native Cerbos tests with reusable fixtures under
`resource_policies/testdata/principals.yaml` and
`resource_policies/testdata/resources.yaml`. Each
resource suite must actively test owner and reviewer grants, their overlap,
wrong parent roles despite matching attributes, tenant mismatches, relationship
mismatches, and default denial. Compile and run the tests in normal and strict
evaluation modes. The bundle must be self-contained.
