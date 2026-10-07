# Cerbos skills

Agent skills for [Cerbos](https://www.cerbos.dev), the authorization management platform. Cerbos decouples authorization from application code: you define policies as code, and Cerbos evaluates them at runtime to answer "can this principal perform this action on this resource?"

## Skills

| Skill | What it does |
|-------|--------------|
| `cerbos-policy` | Generates, modifies, and explains Cerbos policies: resource and role policies, derived roles, exported variables, CEL conditions, and `*_test.yaml` suites. Works from written requirements or a spec document, and fixes policies that fail to compile or tests that fail. |
| `cerbos-synapse-extension` | Builds, tests, and debugs Cerbos Synapse extensions: call mappers, data sources, and proxy, route, and Envoy ext_authz extensions, in declarative YAML/CEL, Starlark, or WASM (Go, TypeScript, Python). |

## What the plugin runs

The plugin contains skills only. It has no hooks, MCP servers, or background processes, and it sends no data anywhere itself. The skills tell the agent to run these commands in your project, and the agent asks before running anything not listed under `allowed-tools`:

- **`cerbos-policy`** compiles and tests policies with the `cerbos` CLI, or with the `ghcr.io/cerbos/cerbos` container image when the CLI isn't installed. It checks test coverage with a bundled Python script, `skills/cerbos-policy/scripts/coverage_audit.py`, which reads local files only. It pre-approves `cerbos compile`, `cerbos --version`, and `docker --version`.
- **`cerbos-synapse-extension`** runs Synapse from its licensed distribution image with Docker Compose, builds WASM extensions with Go, npm, or `extism-py`, and sends test requests to the local Synapse instance with `curl`. It pre-approves nothing.

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
