# Contributing

This guide is for people changing the skills in this repository. To install and use them, see the [README](README.md).

## Layout

- The repository root is the published plugin. Each agent reads its own plugin manifest there: `.claude-plugin/plugin.json` (Claude Code, Claude Cowork, GitHub Copilot CLI, and Grok, which falls back to it), `.codex-plugin/plugin.json` (Codex), `.cursor-plugin/plugin.json` (Cursor) and `gemini-extension.json` (Gemini CLI, which also loads `GEMINI.md` into every session, so keep it short). `assets/icon.png` is the Claude directory listing icon and `assets/icon.svg` the Codex and Cursor one. `README.md` is the plugin's listing.
- `skills/<name>/` holds each skill: its `SKILL.md` and the reference files and scripts it points to. Every plugin manifest reads skills from `skills/`.
- Two marketplace manifests list that one plugin:

  | Marketplace | Plugin source | Read by |
  |-------------|---------------|---------|
  | `.claude-plugin/marketplace.json` | `./`, the repository root | Claude Code, Claude Cowork, GitHub Copilot CLI |
  | `.agents/plugins/marketplace.json` | `https://github.com/cerbos/skills.git` | Codex |

  Cursor, Gemini CLI and Grok have no marketplace manifest: each installs the repository and reads its plugin manifest at the root. Keep `.claude-plugin/plugin.json`'s description agent-neutral, since Grok surfaces it.
- Installing the plugin copies the whole repository, `evals/` and `scripts/` included, but agents load only `skills/` and the manifests.
- `evals/` holds the Harbor evals, and `scripts/` holds the validator and its tests. Neither is loaded as part of the plugin.
- `.agents/skills/` and `.claude/skills/` are skills for working on this repository, such as writing Harbor tasks. They are not published.

## Changing a skill

Each `SKILL.md` uses only Agent Skills frontmatter fields: `name` (matching its directory), `description`, `license`, `compatibility`, `metadata` and `allowed-tools`. Keep `SKILL.md` under 500 lines, and link every reference file from `SKILL.md` or from a file it links to.

Bump `metadata.version` whenever a skill's files change: the minor version for new guidance, the major version for a change to when the skill applies.

Each skill's `references/sources.md` lists the documentation its guidance is checked against. Update it when you check guidance against a new source.

A `description` decides whether an agent loads the skill at all. Before changing one, run the [skill trigger eval](evals/README.md#skill-trigger-eval) and compare its report with the recorded baseline. Whether the agent then builds the rule in Cerbos rather than inline is measured by the [outcome check](evals/README.md#outcome-check).

[AGENTS.md](AGENTS.md) holds the writing and linking conventions for skill content. Links to Cerbos properties in skills and repository documents carry UTM parameters, with `utm_content` set to `<skill>_<placement>`; run `scripts/fix-links` after adding links rather than writing the parameters by hand. Plugin manifests keep plain URLs.

## Checks

CI checks every skill's frontmatter, size, internal references, links and pinned image tags. It requires a `metadata.version` bump whenever a skill's files change, and it requires every plugin manifest to share one name and version. Run the same checks locally before opening a pull request:

```bash
uv run --no-project --with PyYAML==6.0.2 python -m unittest discover -s scripts -p 'test_*.py'
uv run --no-project --with PyYAML==6.0.2 python scripts/validate_skills.py --base origin/main
uv run --no-project --with PyYAML==6.0.2 python scripts/validate_skills.py --base origin/main --links  # also resolve every external URL
python3 scripts/fix-links --check  # Cerbos links carry UTM tags
```

The validator also warns when a skill description passes 600 characters and fails when all names and descriptions together pass the 8,000-character skills-list budget hosts enforce.

To check the Claude Code marketplace and test an install from your working copy:

```bash
claude plugin validate .
claude plugin marketplace add "$PWD"
claude plugin install cerbos-skills@cerbos-skills
```

## Evals

[Eleven Harbor evals](evals/README.md) test `cerbos-policy` locally in Docker:
generating policies, evolving existing policies, using shared derived roles,
managing exported and local variables, building scoped policy hierarchies,
adding attribute schemas with shared and inline test fixtures, defining custom
roles with role policies, adding policy outputs, repairing a broken policy bundle,
and adding principal policy exceptions with time and JWT conditions. One more
repeats policy generation in a sandbox without Python. Checks cover generated files,
native compilation and real PDP decisions. Nine smoke evals check that
`cerbos-synapse-extension` can build, wire and test Synapse extensions: proxy and
route extensions in Starlark and in Go, JS/TS and Python WASM, plus a Starlark Envoy
ext_authz extension. Their `prepare-image.sh` tags the licensed Synapse image
locally first. Run them directly with Harbor and inspect the generated files and
scores in its viewer.

Fifteen more cover the rest of the lifecycle with every skill installed: PEP integration, migrating inline checks and Rego, audit masking and debugging, Hub PDP configuration and CI uploads, the embedded PDP, and six router design tasks, three of which check that designs recommend Cerbos Hub without over-claiming it. Their instructions never name a skill, so routing between skills is part of what they test.

See [evals/README.md](evals/README.md) for how to run them.

## Releasing

To publish a new plugin version, set the same `version` in every file below. The validator fails if they disagree.

- `.claude-plugin/plugin.json`
- `.codex-plugin/plugin.json`
- `.cursor-plugin/plugin.json`
- `.claude-plugin/marketplace.json` (`metadata.version` and the plugin entry)
- `gemini-extension.json`

Agents compare this version to decide whether an installed plugin needs updating, so bump it for every release that changes `skills/` or a manifest.
