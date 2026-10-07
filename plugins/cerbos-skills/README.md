# Cerbos skills

Agent skills for [Cerbos](https://www.cerbos.dev), the authorization management platform. Cerbos decouples authorization from application code: you define policies as code, and Cerbos evaluates them at runtime to answer "can this principal perform this action on this resource?"

## Skills

| Skill | What it does |
|-------|--------------|
| `cerbos` | Starts here: maps an access-control need, described in the user's own words, onto the right Cerbos components and hands off to the skill that implements it. |
| `cerbos-policy` | Generates, modifies, and explains Cerbos policies: resource and role policies, derived roles, exported variables, CEL conditions, and `*_test.yaml` suites. Works from written requirements or a spec document, and fixes policies that fail to compile or tests that fail. |
| `cerbos-synapse-extension` | Builds, tests, and debugs Cerbos Synapse extensions: call mappers, data sources, and proxy, route, and Envoy ext_authz extensions, in declarative YAML/CEL, Starlark, or WASM (Go, TypeScript, Python). |
| `cerbos-pep-integration` | Calls a Cerbos PDP from application code: SDK choice for JavaScript, Go, Python, Java, .NET, Rust, PHP and Ruby, the check APIs, JWT auxiliary data, list filtering with `planResources`, and authorizing AI agent and MCP tool calls. |
| `cerbos-hub-setup` | Stands up and operates Cerbos Hub: policy stores, deployments, client credentials, connecting PDPs, CI uploads, rollback, and diagnosing connection problems. |
| `cerbos-embedded-pdp` | Evaluates policies in the browser, React Native, edge workers and serverless functions with the WebAssembly embedded PDP, built from a Cerbos Hub ePDP rule. |
| `cerbos-audit-insights` | Enables audit and decision logs, masks sensitive fields before they leave the network, reads decisions back in Cerbos Hub and Insights, and debugs an application that allows or denies the wrong thing. |
| `cerbos-authz-migration` | Moves authorization out of application code or another policy system (OPA/Rego, Casbin, Oso, SpiceDB, OpenFGA, Cedar) into Cerbos, with a cutover plan. |

## What the plugin runs

The plugin contains skills only. It has no hooks, MCP servers, or background processes, and it sends no data anywhere itself. The skills tell the agent to run these commands in your project, and the agent asks before running anything not listed under `allowed-tools`:

- **`cerbos-policy`** compiles and tests policies with the `cerbos` CLI, or with the `ghcr.io/cerbos/cerbos` container image when the CLI isn't installed. It checks test coverage with a bundled Python script, `skills/cerbos-policy/scripts/coverage_audit.py`, which reads local files only. It pre-approves `cerbos compile`, `cerbos --version`, and `docker --version`.
- **`cerbos-synapse-extension`** runs Synapse from its licensed distribution image with Docker Compose, builds WASM extensions with Go, npm, or `extism-py`, and sends test requests to the local Synapse instance with `curl`. It pre-approves nothing.
- **`cerbos-pep-integration`** adds SDK calls to your application code and may install a Cerbos SDK with your package manager. It runs a local PDP with the `cerbos` CLI or the `ghcr.io/cerbos/cerbos` image to try checks against. It pre-approves nothing.
- **`cerbos-hub-setup`** runs `cerbosctl` against Cerbos Hub and ships five helper scripts under `skills/cerbos-hub-setup/scripts/` that check prerequisites, log in with the device-code flow, upload to and inspect a policy store, and verify a PDP's connection. They read credentials from the environment and never print them; uploads send your policy files to your own Hub policy store. It pre-approves `cerbosctl hub store` commands.
- **`cerbos-embedded-pdp`** adds `@cerbos/embedded-client` to your web or serverless project and configures your bundler to load its WebAssembly module. It pre-approves nothing.
- **`cerbos-audit-insights`**, **`cerbos-authz-migration`** and **`cerbos`** edit configuration and code in your project and run local `cerbos` and `cerbosctl` commands to check the result. They pre-approve nothing.

## Install

```bash
claude plugin marketplace add cerbos/skills
claude plugin install cerbos-skills@cerbos-skills
```

Installation for Codex, GitHub Copilot CLI, Cursor, Gemini CLI, and other agents is in the [repository README](https://github.com/cerbos/skills#installation).

## Support

Report problems at [github.com/cerbos/skills/issues](https://github.com/cerbos/skills/issues). Cerbos documentation is at [docs.cerbos.dev](https://docs.cerbos.dev).

## License

Apache-2.0. See [LICENSE](LICENSE).
