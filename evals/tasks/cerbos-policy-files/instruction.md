Use the installed `cerbos-policy` skill to generate a complete Cerbos policy
bundle in `/workspace/policies` for this confirmed specification:

- In the `content` domain, resource kind `document`: role `reader` may `view`;
  role `editor` may `view` and `edit`. Readers consume content; editors maintain it.
- In the `billing` domain, resource kind `invoice`: role `accountant` may `view`
  and `approve`. Accountants review and approve invoices.
- These permissions are unconditional. Every other role/action combination is
  denied by default, including `delete` on either resource and access by `visitor`.
- Both policies use version `default`. Principals and resources have no attributes.
  No other policy kinds, resource policies, versions or scopes are needed.

I confirm these effects and purposes and authorize generation now. Include the
attribute schemas, reusable fixtures and executable policy tests that belong
with the bundle. Organize and validate the deliverables according to the skill.

Cerbos 0.55.0 is installed directly in this sandbox. Docker is unavailable inside
the sandbox. Write the completed bundle to disk before responding.
