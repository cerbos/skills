# Ecosystem recipe template

Every ecosystem recipe in this directory follows this exact structure. To add support for a
new language or framework, copy this template to `<language>.md` and fill in every section.
Recipes carry **stable patterns**; they must never pin SDK versions or duplicate API
reference detail — instead they link the live sources the agent fetches at integration time.

## Required header

```markdown
# <Language> integration recipe

**SDK packages**: <package names with registry links>
**Live sources — fetch these before writing any integration code:**
- SDK repo README: <https://github.com/cerbos/cerbos-sdk-...> (raw README URL)
- SDK API docs: <generated docs site if one exists>
- Query-plan adapters: <adapter repo/docs URLs>
- Docs index: https://docs.cerbos.dev/llms.txt
```

## Required sections

1. **Client setup** — installing the SDK, constructing the client (gRPC vs HTTP transport,
   when to choose each), connection/TLS config from environment variables, client lifecycle
   (singleton per process, never per request).
2. **Principal construction** — building the Cerbos principal from the app's existing auth
   context (JWT claims, session, auth middleware). One canonical helper, used everywhere.
3. **Framework integration points** — for each covered framework: where checks belong
   (middleware/guard vs service layer per the placement rules in
   [ARCHITECTURE.md](../ARCHITECTURE.md)), with idiomatic code for that framework.
4. **Single-resource checks** — `CheckResources` / `isAllowed` at the point where the
   resource is already loaded, including batching multiple actions in one call.
5. **List filtering** — `PlanResources` for list/search endpoints, wiring the query-plan
   adapter for the ecosystem's ORMs, and handling the three plan outcomes
   (`ALWAYS_ALLOWED` / `ALWAYS_DENIED` / `CONDITIONAL`).
6. **The authorization helper** — one helper that always runs the real Cerbos check, with
   a per-callsite mode flag deciding whether a Cerbos deny blocks (`enforce`) or is only
   logged while legacy stands (`shadow`), per [ARCHITECTURE.md](../ARCHITECTURE.md) §4. Not
   a separate shadow path: in shadow the legacy decision stays authoritative, Cerbos runs
   in parallel, mismatches are logged with structured context; cutover is a config change.
   Name it for the check, not for shadow (`authorize`/`checkAccess`, never `shadowCheck`).
7. **Testing** — exercising checks against a real local PDP, asserting on decisions.
   Lead with reusing an existing docker-compose PDP stack if the app has one; present
   container-based tests (testcontainers or equivalent) as the fallback when it does not.
8. **Local dev PDP** — minimal `docker compose` (or equivalent) service running
   `ghcr.io/cerbos/cerbos:latest` with a mounted `policies/` directory.

## Rules for recipe authors

- Code samples must be complete enough to adapt, not pseudo-code — but the agent applying
  the recipe MUST first fetch the live sources in the header and prefer them if anything
  here has drifted.
- Public URLs only. Never reference local file paths or private repositories.
- Follow the target application's existing conventions (naming, error handling, DI style)
  over the style shown in samples.
- Every sample that makes a decision must fail closed: errors and timeouts deny.
