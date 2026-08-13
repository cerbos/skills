# Built-in system extensions

Addressed via `extensionURL: "system://<name>"`. No compilation/distribution. Check these before writing a custom extension.

| URL | Kind | What it does |
|-----|------|--------------|
| `system://sqldb` | Data source | Query Litestream, MySQL, PostgreSQL, SQLite. `query` = SQL string; `queryParameters` = dict of named params (`:name`). Single row → object; multi-row → array. Supports DML on SQLite. |
| `system://claude` | Route extension | Demo Claude Code hook handler → Cerbos `CheckResources`. Route `/claude` → `["POST"]`. `resource.kind` = hook event (`PreToolUse`, …), `resource.attr` = hook payload, `action` = tool name for tool-call hooks else `event`; `principal.id`/`roles` from `X-Claude-User` / `X-Claude-User-Roles` headers (default `claude_user`), `resource.scope` from `X-Cerbos-Scope`. **Important**: no matching policy → tool call *allowed*. Policy output is merged **verbatim** into the hook response and must be valid for that hook — Claude Code ignores a malformed one and proceeds with the action even after a deny. |
| `system://aperture` | Route extension | Tailscale Aperture guardrail hooks → Cerbos `CheckResources` against `aperture_hook` resource policy. Configure under `extensions.routeExtensions.<name>`, route `/aperture` → `["POST"]`. Optional `configuration.resourceKind` / `resourcePolicyVersion` / `resourceScope`. **Important**: absent resource policy → LLM request *allowed* (opposite of PDP default deny). Policy outputs merge with default response — an `EFFECT_ALLOW` rule returning `{"action": "block"}` incorrectly blocks; guard for copy-paste errors. |

All behave like any other extension from the configuration's perspective.
