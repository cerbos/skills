Use the installed `cerbos-synapse-extension` skill to add a document access endpoint
to Cerbos Synapse in `/workspace`.

The policy in `/workspace/policies` grants `view` on a `document` to the `employee`
role only when the principal's `department` and `tenant` attributes match the
document's. Leave the policy unchanged.

Write a WebAssembly route extension in Python under `/workspace/extensions/` that
serves `GET /ext/documents?id=<document id>`. Callers send their principal ID in the
`X-User-Id` header and their tenant in the `X-Tenant` header. For each request, ask
the PDP whether the caller, as an `employee` with that tenant and the department
from this directory, may `view` the document:

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

Callers not in the directory have no department, so they are denied. Respond with
HTTP 200 and the JSON body `{"allowed": true}` when the PDP allows, HTTP 403 and
`{"allowed": false}` when it denies, and HTTP 404 for an unknown document ID.

Write the Synapse configuration to `/workspace/config.yaml`: an in-process PDP that
reads `/workspace/policies` from disk, with the built `.wasm` loaded as a route
extension. Build the module yourself and leave the `.wasm` on disk. Add a Synapse
test suite under `/workspace/extensions/` that shows an allowed request, a denied
request and an unknown document, and make sure it passes.

These requirements are confirmed; proceed with implementation. Synapse 0.10.2 is
installed as the native `synapse` executable, so no container image, registry login
or distribution repository is needed. `extism-py` 0.1.5, `wasm-tools` and binaryen
(`wasm-merge`) are installed as native executables; run build steps directly rather
than through Docker. Docker is unavailable inside this environment. Write every file
to disk before responding.
