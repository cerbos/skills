# Authorizing the helpdesk assistant's tool calls

## Summary

Decide in the agent which tools the model is allowed to see. Before each
conversation turn, the agent asks Cerbos which tools the signed-in staff member
may use and only gives the model those tool definitions. If the model never
sees `delete_ticket`, it cannot call it.

## Components

### Cerbos PDP and policies

Run a Cerbos PDP next to the agent. Write an `mcp_tool` resource policy where
the read and update tools are allowed to `support_agent`, `support_lead` and
`admin`, and `delete_*` actions only to `support_lead` and `admin`. Cerbos
supports action wildcards, so new `delete_*` tools are covered automatically.
Policies are tested with `cerbos compile`.

### Tool filtering in the agent

When a session starts, the agent decodes the user's Okta token, builds the
principal from `sub` and `roles`, and calls `check_resources` for every tool
the MCP server advertises. Tools that are denied are removed from the tool list
passed to the LLM. The system prompt is also updated:

> Only support leads and admins may delete tickets or attachments. If the user
> is not one of them, refuse.

### MCP server

No changes are needed in the MCP server: it keeps running every tool with the
helpdesk service account, because the agent will only ever call tools that
Cerbos allowed for the user. This keeps the MCP server generic and fast.

## Approaches to avoid

- Hard-coding role checks in Python.
- Letting the model see tools the user cannot use.

## Next steps

1. Write the `mcp_tool` policy and tests.
2. Deploy the PDP next to the agent.
3. Add tool filtering to the agent and update the system prompt.
