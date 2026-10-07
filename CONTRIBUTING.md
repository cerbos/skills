# Contributing

This guide is for people changing the skills in this repository. To install and use them, see the [README](README.md).

## Layout

- `plugins/cerbos-skills/` is the published plugin, and the only directory agents install. It holds the plugin manifests, `README.md` (the Claude plugin directory listing), `LICENSE`, `assets/icon.png` (Claude directory listing), `assets/icon.svg` (Codex and Cursor), and `skills/`. Keep everything else out of it.
- `plugins/cerbos-skills/skills/<name>/` holds each skill: its `SKILL.md` and the reference files and scripts it points to.
- The marketplace manifests at the repository root point each agent at `plugins/cerbos-skills/`:

  | Marketplace | Plugin manifest in `plugins/cerbos-skills/` | Agent |
  |-------------|---------------------------------------------|-------|
  | `.claude-plugin/marketplace.json` | `.claude-plugin/plugin.json` | Claude Code |
  | `.agents/plugins/marketplace.json` | `.codex-plugin/plugin.json` | Codex |
  | `.github/plugin/marketplace.json` | `.claude-plugin/plugin.json` | GitHub Copilot CLI |
  | `.cursor-plugin/marketplace.json` | `.cursor-plugin/plugin.json` | Cursor |

- Gemini CLI installs the whole repository and reads skills from `skills/` at its root, so `gemini-extension.json` stays at the root and `skills` is a symlink to `plugins/cerbos-skills/skills`.
- `evals/` holds the Harbor evals, and `scripts/` holds the validator and its tests. Neither is published.
- `.agents/skills/` and `.claude/skills/` are skills for working on this repository, such as writing Harbor tasks. They are not published.

## Changing a skill

Each `SKILL.md` uses only Agent Skills frontmatter fields: `name` (matching its directory), `description`, `license`, `compatibility`, `metadata` and `allowed-tools`. Keep `SKILL.md` under 500 lines, and link every reference file from `SKILL.md` or from a file it links to.

Bump `metadata.version` whenever a skill's files change: the minor version for new guidance, the major version for a change to when the skill applies.

Each skill's `references/sources.md` lists the documentation its guidance is checked against. Update it when you check guidance against a new source.

[AGENTS.md](AGENTS.md) holds the writing and linking conventions for skill content. Links to Cerbos properties in skills and repository documents carry UTM parameters, with `utm_content` set to `<skill>_<placement>`; run `scripts/fix-links` after adding links rather than writing the parameters by hand. Plugin manifests and the plugin's listing README keep plain URLs.

## Checks

CI checks every skill's frontmatter, size, internal references, links and pinned image tags. It requires a `metadata.version` bump whenever a skill's files change, and it requires every plugin manifest to share one name and version. Run the same checks locally before opening a pull request:

```bash
uv run --no-project --with PyYAML==6.0.2 python -m unittest discover -s scripts -p 'test_*.py'
uv run --no-project --with PyYAML==6.0.2 python scripts/validate_skills.py --base origin/main
```

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

See [evals/README.md](evals/README.md) for how to run them.

## Releasing

To publish a new plugin version, set the same `version` in every file below. The validator fails if they disagree.

- `plugins/cerbos-skills/.claude-plugin/plugin.json`
- `plugins/cerbos-skills/.codex-plugin/plugin.json`
- `plugins/cerbos-skills/.cursor-plugin/plugin.json`
- `.claude-plugin/marketplace.json` (`metadata.version` and the plugin entry)
- `.github/plugin/marketplace.json` (`metadata.version` and the plugin entry)
- `.cursor-plugin/marketplace.json` (`metadata.version` and the plugin entry)
- `gemini-extension.json`

Agents compare this version to decide whether an installed plugin needs updating, so bump it for every release that changes `plugins/cerbos-skills/`.
