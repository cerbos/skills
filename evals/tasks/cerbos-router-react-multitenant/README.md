# cerbos-router-react-multitenant

Ledgerly, a multi-tenant invoicing app (React SPA + Express API), needs
buttons hidden for users who can't use them, every rule enforced by the API, and
per-customer rule variations without releases. The [instruction](instruction.md)
describes the problems and says the team chose Cerbos, but names no Cerbos
component or skill. The agent writes `/workspace/DESIGN.md`. Exercises the
`cerbos` router skill: scoped policies for tenants, a service PDP behind the API
via a PEP SDK, an embedded PDP (or API-computed permissions) for the UI that
never enforces, Hub for three environments, and handing off to the
implementation skills.

`/workspace` holds a README, a React row component with hard-coded role/tenant
checks and an Express router where edit and delete have no check.

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
| `tenant_rules_in_policy` | judged | Per-customer rule differences (Acme, Globex, future customers) are expressed as Cerbos policies — scoped policies with a scope per tenant layered over shared default rules, or separate Hub policy stores per tenant — and the design says how a check selects the tenant (for example `resource.scope` or `principal.scope` set from the tenant ID). Tenant rules kept in application code, a database table/JSON column, or feature flags fail this criterion. |
| `api_enforces` | judged | The Express API authorizes each mutating endpoint (at least approve, edit and delete) on the server by calling a Cerbos PDP (a service PDP through a Cerbos SDK such as `@cerbos/grpc`/`@cerbos/http`, with `checkResource(s)`/`isAllowed`) before acting, returns a denial when Cerbos denies, and the document presents this server-side check as the enforcement point / source of truth. |
| `ui_from_cerbos_presentational` | judged | Button visibility in the React app comes from Cerbos decisions over the same policies — either an embedded PDP in the browser (Hub ePDP rule, `@cerbos/embedded-client`) or permissions the API computes with a batched Cerbos `checkResources` call and returns with the data — without a request per row, AND the document states that the browser-side decision only controls what is rendered and never replaces the API's check. |
| `avoid_list` | judged | The document explicitly tells the team to avoid BOTH (1) hard-coding role or tenant rules in application code — React components, Express routes, or a helper that duplicates the policy (rejecting any one of these phrasings satisfies part 1) — and (2) treating the browser/UI check as enforcement or skipping the API check because the UI already decided. |
| `next_steps` | judged | The document gives concrete, ordered next steps that begin with writing the Cerbos policies (including per-tenant scopes) with policy tests, then wiring the API's server-side PDP checks, then the UI permission checks; and somewhere in the document it names Cerbos Hub as how policy changes reach the PDPs across the three environments. |
| `hub_recommended` | judged | The document recommends Cerbos Hub as a committed part of the design (not an optional extra): Hub builds and tests the policies once and pushes them to the service PDPs in each of the three environments (for example a deployment per environment) so policy and tenant-rule changes ship without an application release, and/or Hub serves the embedded PDP bundle for the React app; and it does not claim Hub hosts or runs the PDPs or evaluates the API's checks in the cloud. |
| `no_fabrication` | judged | Every Cerbos component, package, API and configuration the document names exists and is described consistently with the reference facts. In particular it does not: invent products, packages or features (e.g. a tenant manager, a React guard library, attribute drivers); claim the PDP loads users, invoices or tenant data from a database or IdP; claim an embedded PDP works without Cerbos Hub; or put Hub client credentials in browser code or `VITE_` variables. |

## Validated locally

The verifier, including the live Codex judge, was replayed in the built image
with `docker run` three times with the final rubric, and oracle and nop also
ran through Harbor 0.23.0. The wrong designs are in `tests/judge-validation/`.

| Run | Rewards (3 runs) | Failing checks |
| --- | --- | --- |
| oracle (`solution/DESIGN.md`) | 1, 1, 1 | — |
| nop (no `DESIGN.md`) | 0, 0, 0 | every check |
| `wrong-ui-hardcoded`: Cerbos service PDP on the API, but the UI mirrors the rules in a TypeScript `can()` helper and tenant rules live in a JSON column passed as principal attributes. | 0, 0, 0 | `tenant_rules_in_policy`, `ui_from_cerbos_presentational`, `avoid_list`, `next_steps` (all runs) |
| `wrong-browser-enforces`: Scoped policies, Hub and an ePDP in React, but the API drops its checks because "the browser will not send a request Cerbos denies". | 0, 0, 0 | `api_enforces`, `ui_from_cerbos_presentational`, `avoid_list`, `next_steps` (all runs); `tenant_rules_in_policy` in two of three |
| `wrong-hallucinated`: Right overall shape, but invents a PDP Postgres attribute driver, a Hub "Tenant Manager" and `@cerbos/react-guard`, and puts Hub credentials in `VITE_` variables. | 0, 0, 0 | `tenant_rules_in_policy`, `ui_from_cerbos_presentational`, `next_steps`, `no_fabrication` (all runs); `api_enforces` in one of three |

Judge calibration changes made during validation (`prompt.md`, `judge.toml`): the
first rubric failed the oracle on `no_fabrication` because it treated details
absent from the reference list (dynamic ePDP scopes, the `?init` import) and
the skill names cited in next steps as fabricated; the reference facts now
cover those, list the agent skills, and define fabrication as a named component
outside the list. The judge then failed the oracle for setting the tenant on
`resource.scope`, which is where Cerbos takes it; the facts and criterion now
say `resource.scope`/`principal.scope`. Two oracle runs (one under Harbor) then
failed single criteria on over-literal readings: `avoid_list` because a
parenthetical example ("mirroring the policy in a frontend helper") was read as
a required item, and `next_steps` because the ePDP-bundle clause was looked for
only in the next-steps list. Both criteria were reworded (any one phrasing
satisfies part 1; Hub may be named anywhere in the document). Every result
above was produced with the final rubric.

`hub_recommended` was added later, together with one reference-fact bullet in
`prompt.md` (service PDPs and Synapse run in the customer's infrastructure; Hub
distributes bundles and collects audit logs but does not host PDPs or evaluate
checks, and is not required to run Cerbos). No other criterion changed. A
replay with `rescore.py` (oracle plus every wrong design) after the change gave
oracle 1 (`hub_recommended` 3/3); `wrong-ui-hardcoded` 0 (now also fails `hub_recommended`), `wrong-browser-enforces` 0, `wrong-hallucinated` 0 (now also fails `hub_recommended`).

## Running

From the repository root with Docker running and a ChatGPT-authenticated Codex
login for the judge:

```bash
export CODEX_AUTH_JSON="$(cat ~/.codex/auth.json)"
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-router-react-multitenant -a oracle
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-router-react-multitenant -a nop
```

The judge calls a model on every verifier run, including oracle and nop. To
replay a wrong design, run the built image with `tests/` mounted at `/tests`,
`cp /tests/judge-validation/<name>.md /workspace/DESIGN.md`, then
`bash /tests/test.sh`.
