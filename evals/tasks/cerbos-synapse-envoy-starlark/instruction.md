Use the installed `cerbos-synapse-extension` skill to put Cerbos Synapse in front of
a document service as an Envoy external authorization server, in `/workspace`.

The policy in `/workspace/policies` grants `view` on a `document` to the `employee`
role only when the principal's `department` and `tenant` attributes match the
document's. Leave the policy unchanged.

Envoy sends Synapse an ext_authz check for each `GET /documents/<document id>`
request, with the caller's principal ID in the `x-user-id` header and tenant in the
`x-tenant` header. Write a Starlark Envoy external authorization extension under
`/workspace/extensions/` that asks the PDP whether the caller, as an `employee` with
that tenant and the department from this directory, may `view` the document:

| Principal ID | Department |
| --- | --- |
| `alice` | `engineering` |
| `bob` | `sales` |

The documents are:

| Document ID | Department | Tenant |
| --- | --- | --- |
| `eng-acme` | `engineering` | `acme` |
| `sales-acme` | `sales` | `acme` |
| `eng-globex` | `engineering` | `globex` |

Callers not in the directory have no department, so they are denied. Allow the
request with an OK status (code 0) when the PDP allows. Deny it with
PERMISSION_DENIED (code 7) and an HTTP 403 denied response when the PDP denies or
the document is unknown.

Write the Synapse configuration to `/workspace/config.yaml`: an in-process PDP that
reads `/workspace/policies` from disk, with the extension loaded as Synapse's Envoy
external authorization extension. Add a Synapse test suite under
`/workspace/extensions/` that shows an allowed check, a denied check and an unknown
document, and make sure it passes.

These requirements are confirmed; proceed with implementation. Synapse 0.10.2 is
installed as the native `synapse` executable, so no container image, registry login
or distribution repository is needed. Docker is unavailable inside this environment.
Write every file to disk before responding.
