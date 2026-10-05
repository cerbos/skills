# Document policy repair

Use the installed `cerbos-policy` skill. Requirements below are confirmed; proceed
with implementation. Cerbos 0.55.0 is installed directly in this sandbox. Docker
is unavailable inside the sandbox, so use the native `cerbos` binary for
compilation and tests.

The bundle in `/workspace/policies` controls access to documents (resource kind
`document`, version `default`). After a recent refactor it no longer compiles,
and its tests do not pass. Repair it so that it meets the confirmed requirements
below.

Every principal has exactly one of the roles `employee`, `contractor` or
`manager`; any other role has no access. Documents always have a string `owner`
(the owning principal's ID) and a numeric `size_mb`. `classification` is an
optional string, and a document without a classification is not public.

- Employees, contractors and managers may view documents.
- Employees and contractors may edit documents they own.
- Employees may download documents up to and including 25 MB. Managers may
  download documents of any size. Contractors may not download documents.
- Managers may delete documents.
- Contractors may act only on documents classified `public`. Every action by a
  contractor on any other document, including one with no classification, is
  denied, whatever other rule would allow it.
- All other actions are denied.

Keep the existing rule names, actions and effects; repair rules rather than
replacing them. Keep every existing test in
`resource_policies/document_test.yaml` with its name, inputs and expected
effects, and keep the fixtures those tests use in `resource_policies/testdata/`
unchanged. Do not delete, skip or weaken existing tests; add new fixtures for new
cases instead of editing existing ones.

Add a regression test showing that a contractor cannot view a document that has
no classification. Leave the evaluation mode out of test `options` so each
command below controls it. Both commands must pass, and decisions must meet the
requirements whether or not the PDP enables strict evaluation:

```sh
cerbos compile /workspace/policies
cerbos compile --strict-evaluation /workspace/policies
```

The bundle must be self-contained.
