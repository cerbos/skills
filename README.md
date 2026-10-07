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

### Plugin marketplaces

This repository is also a plugin marketplace. Each agent reads its own manifest, and every manifest installs the same `cerbos-skills` plugin from the [`plugins/cerbos-skills/`](plugins/cerbos-skills) directory.

#### Claude Code

```bash
claude plugin marketplace add cerbos/skills
claude plugin install cerbos-skills@cerbos-skills
```

Inside a session, `/plugin` opens the same marketplace browser. To pick up a new release, run `claude plugin marketplace update cerbos-skills`.

#### Codex

```bash
codex plugin marketplace add cerbos/skills
codex plugin add cerbos-skills@cerbos-skills
```

You can also open `/plugins` in a Codex session and install from the `cerbos-skills` marketplace. To pick up a new release, run `codex plugin marketplace upgrade cerbos-skills`.

#### GitHub Copilot CLI

```bash
copilot plugin marketplace add cerbos/skills
copilot plugin install cerbos-skills@cerbos-skills
```

To pick up a new release, run `copilot plugin update cerbos-skills`.

#### Cursor

On a Teams or Enterprise plan, an admin adds the repository as a team marketplace:

1. Open the Cursor dashboard and go to **Plugins & MCPs**.
2. Under **Team Marketplaces**, click **Add Marketplace**, choose **Import from Repo**, and paste `https://github.com/cerbos/skills`.
3. Developers open **Customize** in the Cursor sidebar, find `cerbos-skills`, and click **Install**.

To install it for yourself, copy the plugin into Cursor's local plugin directory and reload the window (**Developer: Reload Window**):

```bash
git clone --depth 1 https://github.com/cerbos/skills /tmp/cerbos-skills
cp -R /tmp/cerbos-skills/plugins/cerbos-skills ~/.cursor/plugins/local/cerbos-skills
```

To pick up a new release, repeat both steps after removing `~/.cursor/plugins/local/cerbos-skills` and `/tmp/cerbos-skills`.

#### Gemini CLI

```bash
gemini extensions install https://github.com/cerbos/skills
```

Run `/skills list` in a session to confirm the skills loaded. To pick up a new release, run `gemini extensions update cerbos-skills`.

### Manual Installation

Copy the skill directories from [`plugins/cerbos-skills/skills/`](plugins/cerbos-skills/skills) to your agent's skills directory.

## Available Skills

### Policy & Engineering

| Skill | Description |
|-------|-------------|
| `cerbos-policy` | Generate Cerbos authorization policies from requirements (RBAC/ABAC, derived roles, resource permissions) |
| `cerbos-synapse-extension` | Build, scaffold, test, and debug Cerbos Synapse extensions — call mappers, data sources, proxy/route/Envoy ext_authz extensions in YAML/CEL, Starlark, or WASM (Go, TypeScript, Python) |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to change a skill, run the checks and evals, and release a new version.

## References

- [Cerbos Documentation](https://docs.cerbos.dev)
- [Cerbos GitHub](https://github.com/cerbos/cerbos)
- [Cerbos Hub](https://cerbos.dev/product-cerbos-hub)

## License

Apache-2.0. See [LICENSE](LICENSE).
