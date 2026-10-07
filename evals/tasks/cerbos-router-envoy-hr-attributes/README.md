# cerbos-router-envoy-hr-attributes

About 40 internal services sit behind Envoy; access must be decided at the
gateway by employment type (employee, contractor, intern), which lives only in
the HR Postgres database, not in the Okta token. The
[instruction](instruction.md) says the team chose Cerbos but names no Cerbos
component or skill. The agent writes `/workspace/DESIGN.md`. Exercises the
`cerbos` router skill's rows for gateway enforcement (Synapse Envoy ext_authz)
and attribute fetching (Synapse data source), the "PDP is stateless" principle,
and policy-as-the-rules with Hub delivery.

`/workspace` holds a README, `gateway/envoy.yaml` with `jwt_authn` routing and
`hr/schema.sql`.

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
| `gateway_enforcement` | judged | The design enforces at the Envoy gateway through Envoy's `ext_authz` filter calling Cerbos Synapse (its Envoy ext_authz integration / Envoy extension), which turns each request (path or prefix, HTTP method, the verified `sub`) into a Cerbos check and returns allow or deny to Envoy — with no changes to the 40 services. |
| `hr_enrichment_in_synapse` | judged | Employment type (and active status) is fetched from the HR database by a Cerbos Synapse data source (for example the built-in `system://sqldb` SQL data source) or proxy/Envoy extension that adds it to the principal's attributes before the PDP evaluates; AND the document explains that this is needed because the PDP does not fetch data itself. |
| `rules_in_policy` | judged | The allow/deny rules (per employment type, the `/finance/` and `/hr/` restriction, interns read-only, inactive denied) are written as Cerbos policies that read the enriched principal attribute, with policy tests, and future changes such as restricting `/deploy/` are described as policy changes rather than code or Envoy config changes. |
| `avoid_list` | judged | The document explicitly tells the team to avoid BOTH (1) looking up the HR database in each service or in per-service/application middleware, and (2) expecting the Cerbos PDP itself to query the HR database (or otherwise load user data). |
| `next_steps` | judged | The document ends with concrete, ordered next steps that include writing the policy with tests, building/configuring the Synapse data source and Envoy integration (with tests), wiring Envoy's `ext_authz` filter to Synapse, and rolling out per environment; and it names Cerbos Hub (or another stated mechanism) as how policy changes reach the PDP without redeploying. |
| `hub_recommended` | judged | The document recommends Cerbos Hub as a committed part of the design (not an optional extra) to deliver policy changes — compiled and tested once — to the PDP behind or inside Synapse, so rules such as the `/deploy/` restriction ship without redeploying Envoy, Synapse or the services; and it does not claim Hub hosts or runs the PDP or Synapse or evaluates the gateway's checks in the cloud. |
| `no_fabrication` | judged | Every Cerbos component, API and configuration the document names exists and is described consistently with the reference facts. In particular it does not claim the PDP queries Postgres or any database, exposes database tables or SQL functions to CEL, natively loads user attributes, or that a PDP storage driver serves user data; and it invents no product, filter or plugin (e.g. a "Cerbos Envoy plugin" or attribute loader). |

## Validated locally

The verifier, including the live Codex judge, was replayed in the built image
with `docker run` (each row twice), and oracle and nop also ran through
Harbor 0.23.0. The wrong designs are in `tests/judge-validation/`.

| Run | Reward, run 1 | Reward, run 2 | Failing checks |
| --- | --- | --- | --- |
| oracle (`solution/DESIGN.md`) | 1 | 1 | — |
| nop (no `DESIGN.md`) | 0 | 0 | every check |
| `wrong-lookup-in-services`: Cerbos PDP plus a shared middleware library in each of the 40 services that queries the HR database and calls the PDP; claims the gateway cannot do it. | 0 | 0 | `gateway_enforcement`, `hr_enrichment_in_synapse`, `rules_in_policy`, `avoid_list`, `next_steps` (both runs) |
| `wrong-pdp-queries-db`: Envoy `ext_authz` straight at the PDP, which "implements ext_authz natively" and reads the HR table through a Postgres storage driver and a CEL `db.query()` function. | 0 | 0 | all six judged criteria (both runs) |

The `wrong-pdp-queries-db` design was lengthened past the 250-word sanity
threshold after its first replay, so that the judge, not `design_doc`, rejects
it. The reference facts and fabrication definition match the other router
tasks.

`hub_recommended` was added later, together with one reference-fact bullet in
`prompt.md` (service PDPs and Synapse run in the customer's infrastructure; Hub
distributes bundles and collects audit logs but does not host PDPs or evaluate
checks, and is not required to run Cerbos). No other criterion changed. A
replay with `rescore.py` (oracle plus every wrong design) after the change gave
oracle 1 (`hub_recommended` 3/3); `wrong-lookup-in-services` 0 and `wrong-pdp-queries-db` 0, both now also failing `hub_recommended`.

## Running

From the repository root with Docker running and a ChatGPT-authenticated Codex
login for the judge:

```bash
export CODEX_AUTH_JSON="$(cat ~/.codex/auth.json)"
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-router-envoy-hr-attributes -a oracle
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-router-envoy-hr-attributes -a nop
```

The judge calls a model on every verifier run, including oracle and nop. To
replay a wrong design, run the built image with `tests/` mounted at `/tests`,
`cp /tests/judge-validation/<name>.md /workspace/DESIGN.md`, then
`bash /tests/test.sh`.
