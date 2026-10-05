Use the installed `cerbos-synapse-extension` skill to add principal enrichment to
Cerbos Synapse in `/workspace`.

Applications call Synapse's CheckResources API with a principal ID, the `employee`
role and a `tenant` attribute, but without the principal's department. The policy in
`/workspace/policies` grants `view` on a `document` to the `employee` role only when
the principal's `department` and `tenant` attributes match the document's. Leave the
policy unchanged.

Write a WebAssembly proxy extension in TypeScript or JavaScript, as one npm project
under `/workspace/extensions/` that sets the principal's `department` attribute from
this directory before the PDP evaluates CheckResources requests:

| Principal ID | Department |
| --- | --- |
| `alice` | `engineering` |
| `bob` | `sales` |

The directory is authoritative: its department replaces any `department` the caller
sends, and principals not in the directory end up with no `department` attribute at
all, even if the caller sent one, so they are denied. Keep every other attribute the
caller sends, including `tenant`.

Write the Synapse configuration to `/workspace/config.yaml`: an in-process PDP that
reads `/workspace/policies` from disk, with the built `.wasm` loaded as a proxy
extension. Build the module yourself and leave the `.wasm` on disk. Add a Synapse
test suite under `/workspace/extensions/` that shows an enriched principal is
allowed and a principal from another department is denied, and make sure it passes.

These requirements are confirmed; proceed with implementation. Synapse 0.10.2 is
installed as the native `synapse` executable, so no container image, registry login
or distribution repository is needed. Node.js 24, `extism-js` and binaryen are
installed, and the npm cache already holds `@extism/js-pdk` 1.1.1, `esbuild` 0.28.2
and `typescript` 7.0.2. Docker is unavailable inside this environment. Write every
file to disk before responding.
