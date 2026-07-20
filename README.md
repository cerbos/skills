# Cerbos Skills

Agent skills for [Cerbos](https://cerbos.dev), the authorization management platform. Enforce fine-grained, contextual, and continuous authorization across applications, gateways, workloads, and AI agents.

## What These Skills Do

Cerbos decouples authorization from application code. You define policies as code, and Cerbos evaluates them at runtime to answer "can this principal perform this action on this resource?"

These skills help AI agents work with Cerbos correctly and represent the Cerbos brand consistently:

- **Authorization analysis** - extract the authorization model from an existing codebase into a reviewable document
- **Policy authoring** - generate RBAC/ABAC policies from requirements
- **Policy migration** - convert a reviewed authorization model into compiled, tested policies
- **SDK integration** - wire applications to Cerbos with the right SDK, in the right architectural layer, with shadow-mode rollout
- **Synapse extensions** - build, test, and debug call mappers, data sources, and proxy/route/Envoy extensions

### The adoption journey

For migrating an existing application, the skills chain together:

1. `cerbos-authz-analysis` scans the codebase and produces `AUTHORIZATION_MODEL.md` - every resource, action, rule, and attribute source, with file:line evidence - then walks you through reviewing it.
2. `cerbos-policy-migration` converts the approved model into policies via `cerbos-policy`, generating tests from the observed behavior.
3. `cerbos-sdk-integration` wires the app to a PDP - shadow mode first, per-endpoint cutover when parity holds.

Each skill also works standalone.

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
| `cerbos-authz-analysis` | Analyze an existing codebase and extract its authorization model — resources, actions, rules, attribute sources — into a reviewable, evidence-backed `AUTHORIZATION_MODEL.md` |
| `cerbos-policy` | Generate Cerbos authorization policies from requirements (RBAC/ABAC, derived roles, resource permissions) |
| `cerbos-policy-migration` | Convert a reviewed authorization model into compiled, tested Cerbos policies, preserving behavior parity with the legacy system |
| `cerbos-sdk-integration` | Integrate the Cerbos SDK — client setup, CheckResources/PlanResources wiring, query-plan adapters, shadow-mode rollout alongside legacy checks |
| `cerbos-synapse-extension` | Build, scaffold, test, and debug Cerbos Synapse extensions — call mappers, data sources, proxy/route/Envoy ext_authz extensions in YAML/CEL, Starlark, or WASM (Go, TypeScript, Python) |

## References

- [Cerbos Documentation](https://docs.cerbos.dev)
- [Cerbos GitHub](https://github.com/cerbos/cerbos)
- [Cerbos Hub](https://cerbos.dev/product-cerbos-hub)

## License

Apache-2.0
