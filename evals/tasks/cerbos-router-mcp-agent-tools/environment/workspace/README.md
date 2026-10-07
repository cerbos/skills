# Helpdesk assistant

An LLM agent (`agent/`) helps support staff work the ticket queue. Staff chat
with it in our helpdesk web app; the agent calls tools on our MCP server
(`mcp_server/server.py`, Python, FastMCP, streamable HTTP) to read and change
tickets in the helpdesk database.

Staff sign in with Okta. The web app passes the user's Okta access token to the
agent, which sends it to the MCP server as the `Authorization` bearer token on
every tool call. The token's `sub` is the staff member and its `roles` claim
holds one or more of `support_agent`, `support_lead` and `admin`.

The MCP server and agent run in Kubernetes in staging and prod.
