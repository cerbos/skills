# Authorizing the helpdesk assistant's tool calls

## Summary

Authorize every tool call in the MCP server with Cerbos, treating the assistant
as the principal. The assistant gets its own Cerbos identity and the policy
decides what it may do based on who asked it.

## Components

### Enforcement in the MCP server

Wrap every tool in a decorator that calls the Cerbos PDP through the Python
SDK before the tool body runs, and raises a tool error on a deny. The principal
is the assistant itself: `{ id: "helpdesk-assistant", roles: ["assistant"] }`,
which matches the helpdesk service account the tools already run as. Each
tool gains an `acting_user_role` argument that the model fills in from the
conversation (the staff member says who they are), and the decorator passes it
as `P.attr.acting_user_role`.

### Policies

An `mcp_tool` resource policy for the `assistant` role: read and update tools
are always allowed; `delete_*` actions are allowed when
`P.attr.acting_user_role in ["support_lead", "admin"]`. New `delete_*` tools are
covered by the wildcard. Policy tests cover each acting role.

### Service PDP and Cerbos Hub

Run the PDP as a sidecar in the MCP server pod, with policies delivered from a
Hub policy store with staging and prod deployments, so rule changes need no
release. Hub audit logs show every decision.

## Approaches to avoid

- Relying on the system prompt to stop deletes.
- Hard-coding role checks in the tools.

## Next steps

1. Create the `helpdesk-assistant` principal and write the policy with tests.
2. Set up Hub and the PDP sidecar.
3. Add the decorator and the `acting_user_role` argument to every tool.
