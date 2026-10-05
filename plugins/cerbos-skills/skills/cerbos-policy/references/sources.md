# Sources

The guidance in this skill is checked against the Cerbos release named by `targetsCerbosVersion` in `SKILL.md`. When moving to a new release, run `evals/update_cerbos_version.py`, read that release's notes, then recheck each page below against the reference file it backs.

## Documentation

| Page | Backs |
|---|---|
| [Release notes](https://github.com/cerbos/cerbos/releases) | New CEL functions (CEL.md **0.55+** markers), policy fields, compiler and test-runner changes |
| [Resource policies](https://docs.cerbos.dev/cerbos/latest/policies/resource_policies.html?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-policy_pdp-policies-resource-policies-html) | POLICIES.md resource policy structure |
| [Role policies](https://docs.cerbos.dev/cerbos/latest/policies/role_policies.html?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-policy_pdp-policies-role-policies-html) | POLICIES.md role policies, `parentRoles` |
| [Principal policies](https://docs.cerbos.dev/cerbos/latest/policies/principal_policies.html?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-policy_pdp-policies-principal-policies-html) | POLICIES.md principal policies |
| [Derived roles](https://docs.cerbos.dev/cerbos/latest/policies/derived_roles.html?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-policy_pdp-policies-derived-roles-html) | POLICIES.md derived roles |
| [Variables](https://docs.cerbos.dev/cerbos/latest/policies/variables.html?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-policy_pdp-policies-variables-html) | POLICIES.md exported and local variables, variable dependency design |
| [Scoped policies](https://docs.cerbos.dev/cerbos/latest/policies/scoped_policies.html?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-policy_pdp-policies-scoped-policies-html) | POLICIES.md scopes and scope permissions |
| [Schemas](https://docs.cerbos.dev/cerbos/latest/policies/schemas.html?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-policy_pdp-policies-schemas-html) | `_schemas/` layout and enforcement |
| [Outputs](https://docs.cerbos.dev/cerbos/latest/policies/outputs.html?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-policy_pdp-policies-outputs-html) | POLICIES.md outputs |
| [Conditions](https://docs.cerbos.dev/cerbos/latest/policies/conditions.html?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-policy_pdp-policies-conditions-html) | CEL.md objects, functions and condition nesting |
| [Compile and test](https://docs.cerbos.dev/cerbos/latest/policies/compile.html?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-policy_pdp-policies-compile-html) | TEST-SUITES.md suite and fixture format; `compile --output=json` and `--strict-evaluation` in SKILL.md |
| [Best practices](https://docs.cerbos.dev/cerbos/latest/policies/best_practices.html?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-policy_pdp-policies-best-practices-html) | Policy layout and naming in SKILL.md |
| [`cerbos` CLI](https://docs.cerbos.dev/cerbos/latest/cli/cerbos.html?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-policy_pdp-cli-cerbos-html) | `cerbos compile` flags |
| [`cerbosctl` CLI](https://docs.cerbos.dev/cerbos/latest/cli/cerbosctl.html?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=cerbos-policy_pdp-cli-cerbosctl-html) | TESTING.md REPL usage |

## Schemas and tools

- `https://api.cerbos.dev/latest/cerbos/policy/v1/*.schema.json`: the `yaml-language-server` headers in POLICIES.md and TEST-SUITES.md.
- `cerbos compile --help` and `cerbosctl repl` in the pinned `ghcr.io/cerbos/cerbos` and `ghcr.io/cerbos/cerbosctl` images: flags and REPL behaviour.
- The eval tasks under `evals/tasks/` pin the same release by digest and exercise this guidance against a real PDP.
