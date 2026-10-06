# cerbos-router-mcp-agent-tools

An LLM helpdesk assistant calls tools on a Python FastMCP server for whichever
staff member is chatting; it deleted tickets for a user who should not be able
to. `delete_*` tools must be limited to support leads and admins and the
assistant must never exceed the user's own permissions. The
[instruction](instruction.md) says the team chose Cerbos but names no Cerbos
component or skill. The agent writes `/workspace/DESIGN.md`. Exercises the
`cerbos` router skill's row for MCP tool calls and agent actions (PEP SDK in
the tool handler, user as principal) and policy-as-the-rules with Hub delivery.

`/workspace` holds a README, `mcp_server/server.py` (tools run as a service
account, the bearer token is already verified) and the agent's system prompt.

## Environment

The image pins Cerbos 0.55.0 and Python 3.12 (Debian Bookworm) by digest, with
PyYAML 6.0.2, Git, curl and CA certificates, and copies the scenario's project
files from `environment/workspace/` to `/workspace`. Cerbos runs natively; there
is no Docker. Judge tooling is installed off the agent's `PATH`: Reward Kit
(`harbor-rewardkit` 0.2.1 with the pinned dependencies in
`environment/judge-requirements.txt`) in `/opt/rewardkit`, and Codex CLI 0.157.0
with a Node 22.23.3 binary (from `node:22-bookworm-slim`, pinned by digest) in
`/opt/judge`. Limits: 2 CPUs, 2 GiB RAM, 4 GiB storage, 600 seconds for the
agent, 300 for verification.

## Verification

`tests/test.sh` runs `tests/verify.py`, then Reward Kit on `tests/judge/`
(Codex agent judge, `openai/gpt-5.6-luna`, working directory `/workspace`, all
criteria in one call), then `tests/merge.py`, which writes one key per check and
`reward` = all pass. A criterion the judge fails to score counts as 0. The
judge prompt (`tests/judge/prompt.md`) restates the request and gives the judge
a closed list of real Cerbos components and facts from the `cerbos` skill and
its linked docs, so `no_fabrication` is judged against a reference rather than
the judge's memory.

| Stage | Kind | Requirement |
| --- | --- | --- |
| `design_doc` | deterministic | `/workspace/DESIGN.md` exists and has at least 250 words. |
| `check_in_tool_path` | judged | Every tool call is authorized on the MCP server side — in the tool handler or a wrapper/middleware that every tool call passes through — by a Cerbos check (Python SDK `is_allowed`/`check_resources` against a PDP) made before the tool runs, with a denial returned to the agent instead of running the tool. Filtering the tool list (in the agent or in `list_tools`) may be added, but a design whose only control is filtering, or whose check runs only in the agent process, fails this criterion. |
| `user_is_principal` | judged | The Cerbos principal for each tool call is the staff member the assistant acts for — `id` and `roles` taken from the verified Okta bearer token on the request — not the assistant, an agent identity, or the helpdesk service account, and not identity or role values supplied by the model in tool arguments or the conversation. |
| `rules_in_policy` | judged | The rules are Cerbos policies: tools modelled as a resource (and/or the underlying ticket records) with actions per tool, `delete_*` allowed only to `support_lead` and `admin` (a wildcard or an explicit rule that the document says covers future delete tools), read/update tools for every support role, deny by default, with policy tests; and the "update only tickets assigned to them" change is described as a policy condition on a resource attribute supplied by the MCP server, not as Python code. |
| `avoid_list` | judged | The document explicitly tells the team to avoid BOTH (1) relying on the system prompt or the model to refuse disallowed tool calls, and (2) authorizing tool calls as the assistant/agent or the helpdesk service account instead of the human user. |
| `next_steps` | judged | The document ends with concrete, ordered next steps that start with writing the Cerbos tool policy with tests (including a support agent denied the delete tools), then running a PDP for the MCP server (with Cerbos Hub or another stated way for policy changes to reach it without an MCP server release), then adding the Cerbos check to the MCP server's tool-call path. |
| `hub_recommended` | judged | The document recommends Cerbos Hub as a committed part of the design (not an optional extra) so that tool-policy changes are compiled and tested once and reach the MCP server's PDP without an MCP server release; and it does not claim Hub hosts or runs the PDP or evaluates the tool-call checks in the cloud. |
| `no_fabrication` | judged | Every Cerbos component, package, API and configuration the document names exists and is described consistently with the reference facts. In particular it does not invent an MCP-specific Cerbos product, agent SDK or gateway, does not claim the PDP fetches ticket or user records itself, and does not misdescribe what an embedded PDP or Synapse does if it mentions them. |

## Validated locally

The verifier, including the live Codex judge, was replayed in the built image
with `docker run` (each row twice), and oracle and nop also ran through
Harbor 0.23.0. The wrong designs are in `tests/judge-validation/`.

| Run | Reward, run 1 | Reward, run 2 | Failing checks |
| --- | --- | --- | --- |
| oracle (`solution/DESIGN.md`) | 1 | 1 | — |
| nop (no `DESIGN.md`) | 0 | 0 | every check |
| `wrong-filter-in-agent`: Cerbos policies with a `delete_*` wildcard, but the only control is the agent filtering the tool list it gives the model, plus a system-prompt rule; the MCP server stays unchanged. | 0 | 0 | `check_in_tool_path`, `user_is_principal`, `rules_in_policy`, `avoid_list`, `next_steps` (both runs) |
| `wrong-agent-principal`: Checks in an MCP server decorator, but the principal is the assistant's service identity and the user's role is a tool argument the model fills in. | 0 | 0 | `user_is_principal`, `rules_in_policy`, `avoid_list`, `next_steps` (both runs) |

The reference facts note that the PDP can verify a JWT passed as auxiliary data
against a JWKS, so a design using that is not marked as fabricated.

`hub_recommended` was added later, together with one reference-fact bullet in
`prompt.md` (service PDPs and Synapse run in the customer's infrastructure; Hub
distributes bundles and collects audit logs but does not host PDPs or evaluate
checks, and is not required to run Cerbos). No other criterion changed. A
replay with `rescore.py` (oracle plus every wrong design) after the change gave
oracle 1 (`hub_recommended` 3/3); `wrong-agent-principal` 0, `wrong-filter-in-agent` 0 (now also fails `hub_recommended`).

## Running

From the repository root with Docker running and a ChatGPT-authenticated Codex
login for the judge:

```bash
export CODEX_AUTH_JSON="$(cat ~/.codex/auth.json)"
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-router-mcp-agent-tools -a oracle
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-router-mcp-agent-tools -a nop
```

The judge calls a model on every verifier run, including oracle and nop. To
replay a wrong design, run the built image with `tests/` mounted at `/tests`,
`cp /tests/judge-validation/<name>.md /workspace/DESIGN.md`, then
`bash /tests/test.sh`.
