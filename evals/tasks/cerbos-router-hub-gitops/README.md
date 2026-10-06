# cerbos-router-hub-gitops

Freightline already runs the open-source Cerbos PDP as a sidecar in every
`shipments-api` pod in dev, staging and prod; policies are copied into the
sidecar image when the API is built. A one-line policy fix needs an API release,
environments drift, an untested policy reached prod, and rollback took a
47-minute redeploy. The [instruction](instruction.md) describes those pains and
says the team wants to keep Cerbos and git-reviewed policies, but names no
Cerbos component or skill. The agent writes `/workspace/DESIGN.md`. Measures
whether the skills lead the agent to recommend Cerbos Hub where it genuinely
fits — a git-mirrored policy store, tested builds that block bad policies, a
deployment per environment pushing signed bundles to the existing sidecars,
rollback and freeze — while keeping the PDPs in Freightline's clusters and
without over-claiming what Hub does.

`/workspace` holds a README, the policy, the PDP Dockerfile and disk-driver
config, the Kubernetes Deployment with the sidecar, the GitHub Actions release
workflow and the incident write-up.

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
| `hub_recommended` | judged | The document recommends Cerbos Hub as the core of the solution (not as an optional later add-on or one of several equal alternatives) and ties it explicitly to at least three of the four stated problems: policy fixes needing an API release, environment drift / not knowing which version is live, no test gate before production, and slow rollback. |
| `pipeline` | judged | Policies stay in the git repository and reach a Hub policy store by Hub mirroring the repository/branch (or by CI uploading to the store on merge), and the document states that Hub compiles the policies and runs their test suites on every change and that a failing build (for example a failing test) is blocked and never reaches the PDPs. |
| `environments` | judged | The document gives each environment (dev, staging, prod) its own Hub deployment, says passing builds are pushed as signed bundles to the existing sidecar PDPs connected to that deployment without an API redeploy, and names Hub rollback and/or freeze as the way to undo or hold a bad policy. |
| `keeps_pdps` | judged | The document says the sidecar PDPs keep running in Freightline's own Kubernetes clusters next to the API, that the change for them is PDP configuration (the Hub storage driver with a deployment ID and client credential instead of policies baked into the image), and that the existing policies are reused as they are, not rewritten. |
| `next_steps` | judged | The document gives concrete, ordered next steps that include creating the Hub policy store connected to the repository (or a CI upload to it), creating a deployment per environment with its client credential, and pointing the sidecar PDPs in each environment at their deployment, with the store and deployments created before the PDPs are switched over. |
| `no_fabrication` | judged | Every Cerbos component, setting and Hub feature the document names exists and is described consistently with the reference facts. In particular it does not say Hub hosts, runs or scales the PDPs, that checks are sent to Hub for evaluation, that Hub is required to run Cerbos, that the policies must be rewritten for Hub, or name an invented Hub feature (approval workflow, canary percentages, Hub-run CI, and the like). |

## Validated locally

The verifier, including the live Codex judge (three runs per replay,
majority per criterion), was replayed in the built image with
`.claude/hillclimb/cerbos-skills/rescore.py` (`oracle validation`), and oracle
and nop also ran once each through Harbor 0.23.0. The wrong designs are in
`tests/judge-validation/`. Every result below was produced with the final
rubric and prompt unless noted.

| Run | Rewards | Failing checks |
| --- | --- | --- |
| oracle (`solution/DESIGN.md`) | 1, 1 (rescore); 1 (Harbor) | — (every criterion 3/3 in both replays) |
| nop (no `DESIGN.md`) | 0 (Harbor) | every check |
| `wrong-self-managed-ci`: never recommends Hub — a GitHub Actions test gate, environment branches and the PDP `git` driver polling them; dismisses Hub as unnecessary. | 0, 0 | `hub_recommended`, `pipeline`, `environments`, `keeps_pdps`, `next_steps` (both) |
| `wrong-hub-later`: CI test gate plus the `blob` driver on S3 now; Hub "to evaluate next year". | 0, 0 | `hub_recommended`, `pipeline`, `environments`, `keeps_pdps`, `next_steps` (both) |
| `wrong-hub-hosts-pdps`: recommends Hub but retires the sidecars for "hosted PDP endpoints" where Hub evaluates checks, a `cerbosctl hub convert` policy conversion and a Hub approval workflow. | 0, 0 | `environments`, `keeps_pdps`, `next_steps`, `no_fabrication` (both); `pipeline` in the first |

Calibration: the first rubric's `pipeline` asked for "a failing compile or
test" to block the bundle and the judge failed a design that said only "a
failing test blocks the build"; it now asks for a failing build (for example a
failing test). After the compliance task showed the judge treating real but
unlisted details as fabrication, the shared reference facts gained
`CERBOS_HUB_PDP_ID`, the audit buffer's acknowledge-then-delete behaviour and
an explicit "absent from these facts is not fabrication" rule; the second
replay above used that final prompt.

## Running

From the repository root with Docker running and a ChatGPT-authenticated Codex
login for the judge:

```bash
export CODEX_AUTH_JSON="$(cat ~/.codex/auth.json)"
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-router-hub-gitops -a oracle
uvx --from harbor==0.23.0 harbor run --jobs-dir evals/jobs -p evals/tasks/cerbos-router-hub-gitops -a nop
python3 .claude/hillclimb/cerbos-skills/rescore.py cerbos-router-hub-gitops oracle validation
```

The judge calls a model on every verifier run, including oracle and nop. To
replay a wrong design by hand, run the built image with `tests/` mounted at
`/tests`, `cp /tests/judge-validation/<name>.md /workspace/DESIGN.md`, then
`bash /tests/test.sh`.
