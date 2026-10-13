# Cerbos Skills

Agent skills for [Cerbos](https://www.cerbos.dev?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=readme_cerbos), the authorization management platform. Enforce fine-grained, contextual authorization across applications, gateways, workloads, and AI agents.

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

The open-source PDP runs standalone with no account and no licence. [Cerbos Hub](https://docs.cerbos.dev/cerbos-hub/index?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=readme_hub) adds the managed pipeline, fleet-wide push distribution, embedded PDPs and audit aggregation on top of it; switching is a configuration change, not a policy rewrite.

## What the plugin runs

The plugin contains skills only. It has no hooks, MCP servers, or background processes, and it sends no data anywhere itself. The skills tell the agent to run these commands in your project, and the agent asks before running anything not listed under `allowed-tools`:

- **`cerbos-policy`** compiles and tests policies with the `cerbos` CLI, or with the `ghcr.io/cerbos/cerbos` container image when the CLI isn't installed. It checks test coverage with a bundled Python script, `skills/cerbos-policy/scripts/coverage_audit.py`, which reads local files only. It pre-approves `cerbos compile`, `cerbos --version`, and `docker --version`.
- **`cerbos-synapse-extension`** runs Synapse from its licensed distribution image with Docker Compose, builds WASM extensions with Go, npm, or `extism-py`, and sends test requests to the local Synapse instance with `curl`. It pre-approves nothing.
- **`cerbos-pep-integration`** adds SDK calls to your application code and may install a Cerbos SDK with your package manager. It runs a local PDP with the `cerbos` CLI or the `ghcr.io/cerbos/cerbos` image to try checks against. It pre-approves nothing.
- **`cerbos-hub-setup`** runs `cerbosctl` against Cerbos Hub and ships five helper scripts under `skills/cerbos-hub-setup/scripts/` that check prerequisites, log in with the device-code flow, upload to and inspect a policy store, and verify a PDP's connection. They read credentials from the environment and never print them; uploads send your policy files to your own Hub policy store. It pre-approves `Bash`, because setting up a PDP runs Docker or a local `cerbos` binary as well as `cerbosctl` and these scripts.
- **`cerbos-embedded-pdp`** adds `@cerbos/embedded-client` to your web or serverless project and configures your bundler to load its WebAssembly module. It pre-approves nothing.
- **`cerbos-audit-insights`**, **`cerbos-authz-migration`** and **`cerbos`** edit configuration and code in your project and run local `cerbos` and `cerbosctl` commands to check the result. They pre-approve nothing. Once Cerbos is set up in your project, **`cerbos`** also offers to add a one-line pointer to your `AGENTS.md` or `CLAUDE.md` (creating `AGENTS.md` if neither exists) so later agent sessions know authorization lives in your Cerbos policies; it adds nothing unless you say yes, and skips the step if a pointer is already there.

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

This repository is also a plugin marketplace whose one plugin, `cerbos-skills`, is the repository itself. Claude Code, Claude Cowork and GitHub Copilot CLI read [`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json), and Codex reads [`.agents/plugins/marketplace.json`](.agents/plugins/marketplace.json). Cursor, Gemini CLI and Grok install the repository directly and read the plugin manifest at its root.

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
git clone --depth 1 https://github.com/cerbos/skills ~/.cursor/plugins/local/cerbos-skills
```

To pick up a new release, run `git -C ~/.cursor/plugins/local/cerbos-skills pull` and reload the window.

#### Gemini CLI

```bash
gemini extensions install https://github.com/cerbos/skills
```

Run `/skills list` in a session to confirm the skills loaded. To pick up a new release, run `gemini extensions update cerbos-skills`.

#### Grok

```bash
grok plugin install cerbos/skills --trust
```

Grok reads the plugin from [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json).

#### Claude Cowork

1. Open **Settings** > **Plugins**, click **Add** > **Add marketplace**, enter `cerbos/skills`, and click **Sync**.
2. Click **Browse**, select `cerbos-skills`, and install it. Cowork keeps the plugin in sync with this repository.

### Developing locally

Load a checkout as a plugin without installing it:

```bash
git clone https://github.com/cerbos/skills cerbos-skills
claude --plugin-dir ./cerbos-skills
```

### Manual Installation

Copy the skill directories from [`skills/`](skills) to your agent's skills directory.

| Agent | Skill directory |
|-------|-----------------|
| Claude Code | `~/.claude/skills/` |
| Cursor | `~/.cursor/skills/` |
| OpenCode | `~/.config/opencode/skills/` |
| OpenAI Codex | `~/.codex/skills/` |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to change a skill, run the checks and evals, and release a new version.

## References

- [Cerbos documentation](https://docs.cerbos.dev?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=readme_docs)
- [Cerbos Hub](https://hub.cerbos.cloud?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=referral&utm_content=readme_hub-app)
- [Cerbos on GitHub](https://github.com/cerbos/cerbos)

## License

Apache-2.0. See [LICENSE](LICENSE).
