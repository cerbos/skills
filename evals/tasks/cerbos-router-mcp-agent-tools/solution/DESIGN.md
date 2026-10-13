# Authorizing the helpdesk assistant's tool calls

## Summary

Enforce in the **MCP server**, not in the agent or its prompt. Every tool call
is authorized by a **Cerbos PDP** before the tool runs, using the Python SDK
(`cerbos` package) as the policy enforcement point. The **principal is the staff
member** from the verified Okta token the agent forwards — not the agent and not
the helpdesk service account — so the assistant can never do more than that
person. The rules live in **Cerbos policies**, tested and shipped through
**Cerbos Hub** to a **service PDP** running next to the MCP server.

## Components

### 1. Policy enforcement point in the MCP server

- Add one wrapper (decorator or FastMCP middleware) applied to every tool. It
  takes the already-verified access token (`get_access_token()`), builds the
  principal `{ id: sub, roles: token roles }`, and calls the PDP before the
  tool body runs. A deny raises a tool error ("not permitted") that the agent
  sees; the tool never touches the database.
- Two resource shapes:
  - kind `mcp_tool`, id = tool name, action = the tool name (`delete_ticket`,
    `update_ticket`, ...) — the gate on which tools a person may call at all;
  - for record-level rules, the record itself: kind `ticket` with attributes
    loaded from the database (`assignee`, `status`), action `update` / `delete`.
    This is where "support agents may only update tickets assigned to them" goes.
- Use `check_resources` with both resources in one request, so each tool call
  costs one round trip to a local PDP.
- Optionally, filter `list_tools` with the same checks so the model is not even
  offered tools the person cannot use. That improves behaviour, but the check
  in the call path is what enforces.

Why: the MCP server is the only place the agent cannot talk its way around.
The token was verified there, and the server decides whether the database is
touched.

### 2. Policies

- `mcp_tool` resource policy: allow the read and update tools to
  `support_agent`, `support_lead` and `admin`; allow actions matching
  `delete_*` only to `support_lead` and `admin`. Cerbos actions support
  wildcards, so a future `delete_*` tool is covered without a policy change,
  and anything not allowed is denied by default.
- `ticket` resource policy: `update` for `support_agent` only when
  `R.attr.assignee == P.id`; leads and admins on any ticket.
- Optionally carry agent context as principal attributes (e.g.
  `P.attr.via_agent: true`) so a policy can restrict what may be done through
  the assistant even further than the person themselves. The principal's
  identity stays the human's.
- Every policy has a `_test.yaml` suite covering each role and tool.

### 3. Service PDP and Cerbos Hub

- Run the PDP as a sidecar in the MCP server pod (localhost gRPC, low latency).
- Keep policies in git mirrored to a Hub policy store, with staging and prod
  deployments. Hub compiles and tests every change and pushes it to the PDPs, so
  rule changes need no MCP server release.
- Turn on Hub audit log collection: every allowed and denied tool call is
  recorded with the staff member's identity, which answers "who made the
  assistant delete this?".

## Approaches to avoid

- **Relying on the system prompt or the model** ("only delete for leads",
  "confirm first"). Prompts are not a security boundary; prompt injection or a
  persuasive user gets around them.
- **Authorizing as the agent or the service account.** If the principal is the
  assistant, every user inherits its permissions — the incident we just had.
- **Role checks hard-coded in each tool** (`if "admin" in roles`). They spread
  through Python, drift, and need a release to change.
- **Only hiding tools from `list_tools`.** The agent can still call a tool by
  name; the check must run on the call.
- **Trusting identity claims passed in tool arguments** instead of the verified
  bearer token.

## Next steps

1. Write the `mcp_tool` and `ticket` resource policies with test suites for
   each role, including a support agent denied `delete_ticket` and
   `delete_customer_attachment`; run `cerbos compile` (cerbos-policy).
2. Set up the Hub policy store, staging and prod deployments, and the PDP
   sidecar (cerbos-hub-setup).
3. Add the `cerbos` Python SDK to the MCP server and the authorization wrapper
   on every tool, mapping the verified token to the principal and returning a
   tool error on deny (cerbos-pep-integration).
4. Add tests that call each tool as each role through the MCP server and assert
   the deletes are refused for support agents.
5. Filter `list_tools` per user, and enable audit log collection.
