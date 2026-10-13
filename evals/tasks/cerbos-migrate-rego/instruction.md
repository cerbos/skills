# Replace our OPA expense policy with Cerbos

The expenses service authorizes through OPA today. The policy is in
`/workspace/opa/expenses.rego`, its role data is in `/workspace/opa/data.json`,
and there are a few Rego unit tests beside it. We are moving to Cerbos.

Translate the policy into Cerbos policies in `/workspace/policies`, with a
native test suite, so that Cerbos returns exactly the decision
`data.expenses.authz.allow` returns today, for every user, expense and action.
That includes users who hold more than one role. Don't change any rule while
translating, even if it looks odd.

The service will call the PDP's CheckResources API with:

- principal: `id` = `input.user.id`, `roles` = `input.user.roles`, and the
  attribute `department` = `input.user.department`;
- resource: kind `expense`, policy version `default`, no scope, `id` =
  `input.resource.id`, and as attributes the other fields of `input.resource`:
  `owner`, `department`, `amount`, `status`, and `legal_hold`, which is only
  present on some expenses;
- actions: `view`, `create`, `edit`, `submit`, `approve`, `delete` and `export`.

The role grants and approval limits in `data.json` change rarely and only with
a release, so it is fine for them to become part of the policies.

The test suite should show an allowed and a denied case for each rule,
including how the rules interact for users with several roles and for expenses
under legal hold. Leave the evaluation mode out of test `options`. Both of these
must pass, and decisions must be the same whether or not the PDP enables strict
evaluation:

```sh
cerbos compile /workspace/policies
cerbos compile --strict-evaluation /workspace/policies
```

Cerbos 0.55.0 is installed natively as `cerbos`. Docker and OPA are not
available. The bundle in `/workspace/policies` must be self-contained.
