# Stop the helpdesk assistant deleting things for the wrong people

Our helpdesk assistant is an LLM agent that calls tools on our MCP server on
behalf of whichever support staff member is chatting with it (code in
`/workspace/mcp_server` and `/workspace/agent`, background in
`/workspace/README.md`).

Last week a support agent asked the assistant to "clean up" a customer's
tickets and it deleted them. Deleting is supposed to be for support leads and
admins only. The rule we want:

- `delete_ticket` and `delete_customer_attachment` — and any `delete_*` tool we
  add later — may only run when the person the assistant is acting for is a
  `support_lead` or an `admin`.
- Everyone with a support role may use the read and update tools.
- The assistant must never be able to do more than the person it is acting for
  could do themselves, however it is prompted.

More tools are coming, and the rules will keep changing (security is already
asking that support agents may only update tickets assigned to them), so we
don't want these rules hard-coded in Python.

We've chosen Cerbos for authorization, but nobody here has used it. Write
`/workspace/DESIGN.md` for the team that:

1. recommends which parts of Cerbos to use and where they fit between the agent,
   the MCP server and Okta,
2. explains why each part is the right fit,
3. calls out the approaches we should avoid, and
4. lists the concrete next implementation steps, in order.

Do not implement anything yet; the design document is the deliverable. Cerbos
0.55.0 is installed in this sandbox if you want to try something; Docker is not
available.
