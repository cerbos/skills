# Acme custom roles

Use the installed `cerbos-policy` skill. Requirements and ALLOW/DENY effects below
are confirmed; proceed with implementation. Cerbos 0.55.0 is installed directly
in this sandbox. Docker is unavailable inside the sandbox, so use the native
`cerbos` binary for compilation and tests.

`/workspace/policies/resource_policies/` contains the shared base policies for
`document` and `invoice` (version `default`, no scope):

- Documents: `viewer` may `view`; `editor` may `view`, `edit`, and `comment`;
  `admin` may also `delete` and `share`.
- Invoices: `accountant` may `view` and `approve`; `admin` may also `void`.

Do not change these files. The tenant Acme (scope `acme`) needs custom roles, which
it manages from each role's perspective using role policies. Principals have a
string attribute `department`. Documents have a string `department` and an
optional boolean `contractor_editable`, where absence means false. Invoices have a
string `department`.

In the `acme` scope:

- `contractor` is based on the `editor` role. Contractors help with Acme
  documents: they may `view` and `comment` on documents, and `edit` only documents
  whose `contractor_editable` is true. Because contractors are based on Acme's
  `editor` role, Acme's department rule for editors below also applies to them:
  a contractor edit additionally requires the document to be in the contractor's
  department. They have no other access, including no invoice access.
- `auditor` is based on both the `viewer` and `accountant` roles. Auditors
  inspect records without changing them: they may `view` documents and invoices,
  and nothing else.
- Acme narrows its `editor` role so that departments own their content: editors
  may `view` and `comment` on documents, and `edit` only documents in their own
  department. Editors outside Acme keep the base permissions.
- Every other role keeps its base permissions in Acme.

Contractors and auditors have no access outside Acme. Requests without a scope
use the base policies.

Use these paths:

- `role_policies/acme/contractor.yaml`
- `role_policies/acme/auditor.yaml`
- `role_policies/acme/editor.yaml`

Supply native Cerbos tests in `role_policies/acme/acme_roles_test.yaml`, with
reusable fixtures in `role_policies/acme/testdata/principals.yaml` and
`role_policies/acme/testdata/resources.yaml`. Use principals with a single role.
The tests must actively cover:

- contractors viewing documents, and editing with `contractor_editable` true,
  false, and absent;
- contractors denied editing a contractor-editable document from another
  department;
- contractors denied invoices and document deletion;
- auditors viewing documents and invoices, and being denied invoice approval
  and document edits;
- Acme editors editing documents in their own department and being denied other
  departments;
- an editor editing a document from another department outside Acme, which
  the base policy allows;
- contractors and auditors denied outside Acme;
- a role without an Acme role policy keeping its base permissions in Acme.

Compile and run the tests in normal and strict evaluation modes. The bundle must
be self-contained.
