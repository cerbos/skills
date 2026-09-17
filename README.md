# Cerbos Skills

Agent skills for [Cerbos](https://www.cerbos.dev), the authorization management platform. Enforce fine-grained, contextual authorization across applications, gateways, workloads, and AI agents.

## What These Skills Do

Cerbos decouples authorization from application code. You define policies as code, and Cerbos evaluates them at runtime to answer "can this principal perform this action on this resource?"

These skills take an agent through the whole lifecycle — recognising an authorization problem, writing the policies, distributing them, enforcing them in application code, and proving what happened afterwards.

## Available Skills

Start with `cerbos`. It maps a described need onto the right component and hands off to the skill that implements it, including when the user has not named Cerbos at all.

| Skill | Use it for |
|-------|------------|
| `cerbos` | Choosing between the PDP, Hub, Synapse, embedded PDPs and the PEP SDKs; recognising an access-control problem described in the user's own words |
| `cerbos-policy` | Writing and modifying policies — resource and role policies, derived roles, CEL conditions, and `*_test.yaml` suites |
| `cerbos-pep-integration` | Calling the PDP from application code: SDK choice, the check APIs, JWT auxiliary data, and filtering queries with `planResources` and its ORM adapters |
| `cerbos-hub-setup` | Standing up and operating Cerbos Hub — policy stores, deployments, credentials, connecting a PDP, rollback and monitoring |
| `cerbos-embedded-pdp` | Authorization in browsers, edge functions, serverless handlers and React Native, evaluated locally in WebAssembly |
| `cerbos-audit-insights` | Streaming decision logs to Hub, masking sensitive fields before they leave the network, and reading the Insights dashboards |
| `cerbos-synapse-extension` | Synapse extensions — call mappers, data sources, proxy/route/Envoy ext_authz extensions in YAML/CEL, Starlark, or WASM |
| `cerbos-authz-migration` | Moving off hand-rolled permission checks or another authorization system |

## The platform

| Component | Role |
|---|---|
| **Cerbos PDP** | Open-source policy decision point. Stateless — it evaluates the request it is given and fetches nothing on its own. |
| **Cerbos Hub** | Control plane: playground, managed build-test-sign-distribute pipeline, push distribution to a PDP fleet, embedded PDPs, audit aggregation and Insights. |
| **Cerbos Synapse** | Context enrichment and protocol adapters for Envoy, Kafka, Trino and others. |
| **PEP SDKs** | JavaScript, Go, Python, Java, .NET, Rust, PHP, Ruby. |

The open-source PDP runs standalone with no account and no licence. [Cerbos Hub](https://docs.cerbos.dev/cerbos-hub/index) adds the managed pipeline, fleet-wide push distribution, embedded PDPs and audit aggregation on top of it; switching is a configuration change, not a policy rewrite.

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

### Claude Code

```bash
claude plugin marketplace add cerbos/skills
claude plugin install cerbos-skills@cerbos-skills
```

### Codex

```sh
codex plugin marketplace add cerbos/skills
codex plugin add cerbos@cerbos
```

### Cursor

Install from the Cursor marketplace, or add manually via **Settings → Rules → Add Rule → Remote Rule (GitHub)** with `cerbos/skills`.

### Manual Installation

Copy the skill directories from `cerbos/` into your agent's skills directory.

| Agent | Skill directory |
|-------|-----------------|
| Claude Code | `~/.claude/skills/` |
| Cursor | `~/.cursor/skills/` |
| OpenCode | `~/.config/opencode/skills/` |
| OpenAI Codex | `~/.codex/skills/` |

## Contributing

Skills live in `cerbos/<skill-name>/SKILL.md`, with deeper material under `references/` and executable helpers under `scripts/`. `plugins/cerbos-skills/skills` symlinks to `cerbos/`, so a new skill directory needs no plugin registration — add a row to the table above and to [AGENTS.md](AGENTS.md).

Before opening a pull request:

```bash
scripts/validate-skills          # structure, frontmatter, relative links
scripts/validate-skills --links  # also resolves every external URL
```

CI runs the same checks on every pull request.

## References

- [Cerbos documentation](https://docs.cerbos.dev)
- [Cerbos Hub](https://hub.cerbos.cloud)
- [Cerbos on GitHub](https://github.com/cerbos/cerbos)

## License

Apache-2.0
