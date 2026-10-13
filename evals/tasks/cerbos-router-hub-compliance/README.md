# cerbos-router-hub-compliance

Lendfield's six services already authorize with open-source Cerbos PDPs on its
own Kubernetes cluster (policies from git), and audit logs go to stdout where
nobody can search them. A SOC 2 auditor wants a searchable record of who
accessed which customer record and why, evidence of monitoring, and retention;
the entries carry staff and customer emails, JWT claims and a session token
that the data handling standard forbids sending to a third party unmasked. The
[instruction](instruction.md) names no Cerbos component or skill. The agent
writes `/workspace/DESIGN.md`. Measures whether the skills lead the agent to
Hub audit log collection with masks applied at the PDP, Hub search and
Insights for the auditor's questions, and PDPs that stay in-cluster with only
their audit configuration changing.

`/workspace` holds a README, the PDP ConfigMap and Deployment (git driver,
`file` audit backend to stdout, `x-session-token` captured), a real-shaped
decision log line, the auditor's request and the data handling standard.

## Environment

The image is the same as the other router tasks: Cerbos 0.55.0 and Python 3.12
(Debian Bookworm) pinned by digest, with PyYAML 6.0.2, Git, curl and CA
certificates, and the scenario's project files copied from
`environment/workspace/` to `/workspace`. Cerbos runs natively; there is no
Docker. Judge tooling is installed off the agent's `PATH`: Reward Kit
(`harbor-rewardkit` 0.2.1 with the pinned dependencies in
`environment/judge-requirements.txt`) in `/opt/rewardkit`, and Codex CLI 0.157.0
with a Node 22.23.3 binary (from `node:22-bookworm-slim`, pinned by digest) in
`/opt/judge`. The Dockerfile is identical to the other router tasks', so only
the final `COPY workspace/` layer is new. Limits: 2 CPUs, 2 GiB RAM, 4 GiB
storage, 600 seconds for the agent, 600 for verification.

## Verification

`tests/test.sh` runs `tests/verify.py`, then Reward Kit on `tests/judge/`
three times in parallel (Codex agent judge, `openai/gpt-5.6-luna`, working
directory `/workspace`, all criteria in one call per run), then
`tests/merge.py`, which takes the majority verdict per criterion and writes one
key per check and `reward` = all pass. A criterion a run fails to score counts
as a fail for that run. The judge prompt (`tests/judge/prompt.md`) restates the
request and gives the judge a closed list of Cerbos and Cerbos Hub facts taken
from the `cerbos`, `cerbos-hub-setup`, `cerbos-audit-insights` and
`cerbos-embedded-pdp` skills, `cerbos-policy/references/HUB.md` and
docs.cerbos.dev. Its fabrication definition names the Hub over-claims this task
family targets: Hub hosting or running the team's service PDPs, Hub evaluating
checks in the cloud, Hub being required to run Cerbos, adopting Hub requiring a
policy rewrite, and invented Hub features.

| Stage | Kind | Requirement |
| --- | --- | --- |
| `design_doc` | deterministic | `/workspace/DESIGN.md` exists and has at least 250 words. |
| `hub_recommended` | judged | The document recommends Cerbos Hub audit log collection — the PDPs' `hub` audit backend shipping decision and access logs to Cerbos Hub — as the core of the answer to the auditor, and does not make a self-run log stack (ELK/OpenSearch, Loki, a SIEM or cloud logging service the team would build and query) the primary record. Forwarding a copy elsewhere as a secondary output is allowed. |
| `masking` | judged | The document removes BOTH the email addresses (staff and customer: the principal and resource `email` attributes and the email in the JWT claims under `auxData.jwt`, or all of `auxData`) AND the `x-session-token` header (masked with the `metadata` mask section, or no longer captured via `includeMetadataKeys`/`excludeMetadataKeys`) at the PDP — `audit.hub.mask` and/or metadata capture settings — and states this happens before entries are buffered or leave the network, while keeping opaque principal and resource IDs so the record still says who accessed what. |
| `insights_or_search` | judged | The document maps the auditor's points to Hub: searchable/filterable decision logs (by principal, resource kind or ID, action and time range) showing who accessed which customer record and whether it was allowed, the policy recorded on each decision entry as the reason it was permitted, and Hub Insights (deny trends, most active principals, drill-through) or equivalent decision-log monitoring for noticing unusual access. |
| `keeps_pdps` | judged | The document says the PDPs keep running on Lendfield's own Kubernetes cluster and keep evaluating every check there (Hub only receives the audit entries), that the existing policies are kept as they are (no rewrite; the PDPs may keep the `git` storage driver), and that the change is PDP audit configuration — `audit.backend: hub` with a Read & write deployment client credential and an `audit.hub.storagePath` buffer on a persistent volume — with no change needed in the six services' authorization calls. |
| `next_steps` | judged | The document gives concrete, ordered next steps that include getting a Hub deployment client credential with Read & write access, writing the masks, verifying that the masked entries contain no emails or session tokens (for example with `pipeOutput` to stdout in staging) before production entries are sent to Hub, and rolling the configuration out to the production PDPs. |
| `no_fabrication` | judged | Every Cerbos component, setting and Hub feature the document names exists and is described consistently with the reference facts. In particular it does not say Hub hosts or runs the PDPs or evaluates checks in the cloud, that Hub is required to run Cerbos or that the PDPs must switch to Hub-hosted policies to collect audit logs, that masking happens in Hub after upload, or name an invented feature (for example automatic PII detection, a Hub log shipper agent or sidecar, or Hub-generated SOC 2 reports). |

## Validated locally

The verifier, including the live Codex judge (three runs per replay,
majority per criterion), was replayed in the built image with
`.claude/hillclimb/cerbos-skills/rescore.py` (`oracle validation`), and oracle
and nop also ran once each through Harbor 0.23.0. The wrong designs are in
`tests/judge-validation/`. Every result below was produced with the final
rubric and prompt unless noted.

| Run | Rewards | Failing checks |
| --- | --- | --- |
| oracle (`solution/DESIGN.md`) | 0 → fixed, then 1, 1 (rescore); 1 (Harbor) | first replay (earlier prompt): `no_fabrication` 1/3; after the fix every criterion 3/3 in both replays |
| nop (no `DESIGN.md`) | 0 (Harbor) | every check |
| `wrong-elk-stack`: never recommends Hub — Fluent Bit, self-hosted OpenSearch and a Lua redaction filter; rules Hub out. | 0, 0, 0 | `hub_recommended`, `masking`, `insights_or_search`, `keeps_pdps`, `next_steps` (all) |
| `wrong-hub-auto-redaction`: Hub audit, but "Hub auto-detects and redacts PII", PDPs must switch to Hub storage first, a "Hub log shipper sidecar", Hub-generated SOC 2 report. | 0, 0, 0 | `masking`, `insights_or_search`, `keeps_pdps`, `next_steps`, `no_fabrication` (all) |
| `wrong-hub-hosted-pdps`: services call "Hub's managed PDPs" in the cloud; masks configured in Hub workspace settings. | 0, 0, 0 | `masking`, `keeps_pdps`, `next_steps`, `no_fabrication` (all); `hub_recommended` (all); `insights_or_search` in the first |

Calibration: the first oracle replay failed `no_fabrication` (1/3) because two
runs treated real details absent from the reference list —
`CERBOS_HUB_PDP_ID`, and buffered entries being deleted only after Hub
acknowledges them — as fabricated. The shared facts now list both and say a
statement is fabrication only when it names something that does not exist or
contradicts the facts. `next_steps` was also loosened before the first replay
so it no longer requires the 1 November date; it still requires verifying the
masks before production entries are sent. The mask configuration in the oracle
was checked against Cerbos 0.55.0 (hub backend with placeholder credentials and
`pipeOutput` to stdout): the PDP started, and both email attributes were
deleted from the emitted decision entry while the session header was not
captured. The wrong designs' first replay used the earlier prompt.

## Running

From the repository root with Docker running and a ChatGPT-authenticated Codex
login for the judge:

```bash
export CODEX_AUTH_JSON="$(cat ~/.codex/auth.json)"
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-router-hub-compliance -a oracle
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-router-hub-compliance -a nop
python3 .claude/hillclimb/cerbos-skills/rescore.py cerbos-router-hub-compliance oracle validation
```

The judge calls a model on every verifier run, including oracle and nop. To
replay a wrong design by hand, run the built image with `tests/` mounted at
`/tests`, `cp /tests/judge-validation/<name>.md /workspace/DESIGN.md`, then
`bash /tests/test.sh`.
