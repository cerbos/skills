# Cerbos Skills

Agent skills for working with [Cerbos](https://cerbos.dev), the open source authorization layer for building fine-grained access control into your applications.

## What These Skills Do

Cerbos decouples authorization from application code. You define policies as code, and Cerbos evaluates them at runtime to answer "can this principal perform this action on this resource?"

These skills help AI agents work with Cerbos correctly and represent the Cerbos brand consistently:

- **Policy authoring** - generate RBAC/ABAC policies from requirements

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

## References

- [Cerbos Documentation](https://docs.cerbos.dev)
- [Cerbos GitHub](https://github.com/cerbos/cerbos)
- [Cerbos Hub](https://cerbos.dev/product-cerbos-hub)

## License

Apache-2.0
