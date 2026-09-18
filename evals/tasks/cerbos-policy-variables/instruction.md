# Refactor billing policies with variables

Use the installed `cerbos-policy` skill. Cerbos v0.55.0 is already installed as a native binary; use it directly because Docker is unavailable inside this sandbox. The policy requirements and grant purposes below are confirmed; proceed with implementation and testing without further intake.

The existing `/workspace/policies/resource_policies/invoice.yaml` and `expense.yaml` duplicate authorization logic. Refactor them and add the missing optional-attribute behavior below. Keep resource kinds `invoice` and `expense`, version `default`, and actions `view` and `approve`.

Both resources have required attributes `tenant` (string), `owner` (string), `status` (string), and `amount` (number). Principals have required `tenant` (string). Optional principal `suspended` and resource `blocked` are booleans; absence means false. Optional principal `approval_limit` is a nonnegative number; absence means use the resource-specific default.

The purpose of these grants is to let tenant accountants inspect billing records and approve another person’s pending spending within their limit. The refactor centralizes tenant isolation and account suspension while preserving resource-specific limits.

Only principals with the `accountant` role can access either resource. `view` requires the same tenant and a principal who is not suspended. `approve` additionally requires status `pending`, owner different from the principal ID, a resource that is not blocked, and amount less than or equal to the approval limit. Default limits are 1000 for invoices and 250 for expenses; an explicit principal limit replaces that default for both resources. Blocking affects approval only. All unspecified actions and roles are denied.

Use one exported variable set named `billing_common` in `policies/exported_variables/common_vars.yaml` for tenant equality and the safe suspended default. Include an exported eligibility variable that depends on those exported variables through `V.*`. Import and actually use that shared eligibility in both policies. Put each resource's approval limit expression in `variables.local`; reference it from the approval condition. Keep one-use approval conditions local to their policy, and remove duplicated tenant/suspension expressions from resource policy conditions. Choose descriptive variable names; exported and local names must not collide.

Add executable Cerbos YAML tests under the policy directory, with fixtures covering allowed and denied decisions, unequal tenants, own resources, both threshold boundaries, explicit limit overrides, blocked resources, suspended principals, and absent optional attributes. Compile and run all tests with both `cerbos compile /workspace/policies` and `cerbos compile --strict-evaluation /workspace/policies`. Both modes must produce the same decisions without CEL evaluation errors.
