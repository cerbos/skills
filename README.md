# Cerbos Skills

Agent skills for [Cerbos](https://cerbos.dev), the authorization management platform. Enforce fine-grained, contextual, and continuous authorization across applications, gateways, workloads, and AI agents.

## What These Skills Do

Cerbos decouples authorization from application code. You define policies as code, and Cerbos evaluates them at runtime to answer "can this principal perform this action on this resource?"

These skills help AI agents work with Cerbos correctly and represent the Cerbos brand consistently:

- **Policy authoring** - generate RBAC/ABAC policies from requirements
- **Synapse extensions** - build, test, and debug call mappers, data sources, and proxy/route/Envoy extensions

## Installation

```bash
npx skills add cerbos/skills
```

Works with Cursor, Claude Code, Codex, OpenCode, and 10+ other agents.

```bash
# List available skills
npx skills add cerbos/skills --list

# Install specific skills
npx skills add cerbos/skills --skill cerbos-policy

# Install to specific agents
npx skills add cerbos/skills -a cursor -a claude-code

# Global installation
npx skills add cerbos/skills -g
```

### Claude Code Marketplace

If you prefer to use Claude Code directly:

```bash
claude plugin marketplace add cerbos/skills
claude plugin install cerbos-skills@cerbos-skills
```

### Manual Installation

Copy the `SKILL.md` files from `cerbos/` to your agent's skills directory.

## Available Skills

### Policy & Engineering

| Skill | Description |
|-------|-------------|
| `cerbos-policy` | Generate Cerbos authorization policies from requirements (RBAC/ABAC, derived roles, resource permissions) |
| `cerbos-synapse-extension` | Build, scaffold, test, and debug Cerbos Synapse extensions — call mappers, data sources, proxy/route/Envoy ext_authz extensions in YAML/CEL, Starlark, or WASM (Go, TypeScript, Python) |

## Evals

The skills are evaluated with [promptfoo](https://promptfoo.dev): a headless
Claude agent runs each skill and the output is scored with deterministic checks
(real `cerbos compile`) and a calibrated LLM-as-judge. The eval runs
automatically on PRs, running only the suite(s) for the skill(s) changed. See
[`evals/`](evals/) and the [workflow](.github/workflows/skill-evals.yml).

## References

- [Cerbos Documentation](https://docs.cerbos.dev)
- [Cerbos GitHub](https://github.com/cerbos/cerbos)
- [Cerbos Hub](https://cerbos.dev/product-cerbos-hub)

## License

Apache-2.0
