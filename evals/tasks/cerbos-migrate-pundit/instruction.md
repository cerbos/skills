# Replace our Pundit document policy with Cerbos

The Rails documents service authorizes with Pundit today. The policies are in
`/workspace/app/policies/`, the controller that calls them is in
`/workspace/app/controllers/`, and `/workspace/app/schema.md` describes the
user and document fields they read. We are moving authorization to Cerbos so
other services can share the rules.

Translate the policies into Cerbos policies in `/workspace/policies`, with a
native test suite, so that Cerbos allows exactly what `authorize` allows today
for every user, document and controller action. A request where Pundit raises
`Pundit::NotAuthorizedError` counts as a deny. Don't change any rule while
translating, even if it looks odd.

The controller will call the PDP's CheckResources API with:

- principal, for a signed-in user: `id` = `user.id`, `roles` = `user.roles`,
  and the attribute `team_ids` = `user.team_ids`; the attribute
  `suspended: true` is sent only for suspended accounts and is absent
  otherwise;
- principal, for a signed-out visitor: `id` = `anonymous`, `roles` =
  `["anonymous"]`, and no attributes;
- resource: kind `document`, policy version `default`, no scope, `id` =
  `document.id`, and the attributes `owner_id`, `team_id`, `published`,
  `confidential`, and `locked_by`, which is only present while a document is
  locked;
- actions: one per controller action, named after it: `show`, `new`, `create`,
  `edit`, `update`, `publish` and `destroy`.

The test suite should show an allowed and a denied case for each rule,
including users who hold more than one role, users whose role the policies
never mention, signed-out visitors and suspended accounts. Leave the
evaluation mode out of test `options`. Both of these must pass, and decisions
must be the same whether or not the PDP enables strict evaluation:

```sh
cerbos compile /workspace/policies
cerbos compile --strict-evaluation /workspace/policies
```

Cerbos 0.55.0 is installed natively as `cerbos`. Docker, Ruby and Rails are not
available. The bundle in `/workspace/policies` must be self-contained.
