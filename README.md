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

This repository is also a plugin marketplace. Each agent reads its own manifest, and every manifest installs the same `cerbos-skills` plugin from the `skills/` directory.

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

To install it for yourself, clone the repository into Cursor's local plugin directory and reload the window (**Developer: Reload Window**):

```bash
git clone https://github.com/cerbos/skills ~/.cursor/plugins/local/cerbos-skills
```

#### Gemini CLI

```bash
gemini extensions install https://github.com/cerbos/skills
```

Run `/skills list` in a session to confirm the skills loaded. To pick up a new release, run `gemini extensions update cerbos-skills`.

#### Releasing

When you release a change, set the same `version` in every manifest; the validator fails if they disagree.

### Manual Installation

Copy the skill directories from `skills/` to your agent's skills directory.

## Available Skills

### Policy & Engineering

| Skill | Description |
|-------|-------------|
| `cerbos-policy` | Generate Cerbos authorization policies from requirements (RBAC/ABAC, derived roles, resource permissions) |
| `cerbos-synapse-extension` | Build, scaffold, test, and debug Cerbos Synapse extensions — call mappers, data sources, proxy/route/Envoy ext_authz extensions in YAML/CEL, Starlark, or WASM (Go, TypeScript, Python) |

## Evals

[Eight Harbor evals](evals/README.md) test `cerbos-policy` locally in Docker:
generating policies, evolving existing policies, using shared derived roles,
managing exported and local variables, building scoped policy hierarchies,
adding attribute schemas with shared and inline test fixtures, defining custom
roles with role policies, and adding policy outputs. Checks cover generated files,
native compilation and real PDP decisions. Nine smoke evals check that
`cerbos-synapse-extension` can build, wire and test Synapse extensions: proxy and
route extensions in Starlark and in Go, JS/TS and Python WASM, plus a Starlark Envoy
ext_authz extension. Their `prepare-image.sh` tags the licensed Synapse image
locally first. Run
them directly with Harbor and inspect the generated files and scores in its viewer.

## Development

CI checks every skill's frontmatter, size, internal references, links and pinned image tags, and requires a `metadata.version` bump whenever a skill's files change. Run the same check locally before opening a pull request:

```bash
uv run --no-project --with PyYAML==6.0.2 python scripts/validate_skills.py --base origin/main
```

Each skill's `references/sources.md` lists the documentation its guidance is checked against.

## References

- [Cerbos Documentation](https://docs.cerbos.dev)
- [Cerbos GitHub](https://github.com/cerbos/cerbos)
- [Cerbos Hub](https://cerbos.dev/product-cerbos-hub)

## License

Apache-2.0
