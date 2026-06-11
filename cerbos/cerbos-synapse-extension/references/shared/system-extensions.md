# Built-in system extensions

Addressed via `extensionURL: "system://<name>"`. No compilation/distribution. Check these before writing a custom extension.

| URL | Kind | What it does |
|-----|------|--------------|
| `system://sqldb` | Data source | Query Litestream, MySQL, PostgreSQL, SQLite. `query` = SQL string; `queryParameters` = dict of named params (`:name`). Single row → object; multi-row → array. Supports DML on SQLite. |
| `system://aperture` | Route extension | Tailscale Aperture guardrail hooks → Cerbos `CheckResources` against `aperture_hook` resource policy. Configure under `extensions.routeExtensions.<name>`, route `/aperture` → `["POST"]`. Optional `configuration.resourceKind` / `resourcePolicyVersion` / `resourceScope`. **Important**: absent resource policy → LLM request *allowed* (opposite of PDP default deny). Policy outputs merge with default response — an `EFFECT_ALLOW` rule returning `{"action": "block"}` incorrectly blocks; guard for copy-paste errors. |

Both behave like any other extension from the configuration's perspective.
