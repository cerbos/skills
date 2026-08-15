# Cerbos skills — evals

Nightly evaluation of the agent skills in this repo, built on
[promptfoo](https://promptfoo.dev). It drives a headless Claude agent that has a
skill loaded, then scores what the agent actually produced — with **deterministic
ground-truth checks** where we have them and an **LLM-as-judge** for the rest.

## Why this shape

- **Deterministic first.** A generated Cerbos policy either `cerbos compile`s
  (and passes its bundled tests) or it doesn't. That's a free, non-flaky, binary
  signal — we run the real compiler on the exact files the agent wrote and never
  trust the agent's self-report.
- **Narrow-criteria judge.** For everything the compiler can't see (deny-holes,
  audit-trail comments, over-engineering), the judge answers a handful of
  **narrow, binary questions**, each tied to one named failure mode — not a fuzzy
  "score out of 10". Criteria live in [`criteria/`](criteria/) so they're
  reviewable on their own.
- **Calibrated judge.** An LLM judge is only worth trusting if it agrees with a
  human. [`calibration/`](calibration/) holds human-labeled known-good and
  known-bad outputs; the **calibration gate** replays them through the *same*
  judge and fails the run if the judge no longer reproduces the labels. Grow this
  set whenever you disagree with the judge — that's how it stays calibrated.

## What we evaluate

Beyond "does it compile", the criteria target the mistakes that compile cleanly
but are wrong — grounded in the Cerbos docs.

**cerbos-policy** (`criteria/cerbos-policy.json` + deterministic asserts):
deny-holes, audit-trail comments, requirement coverage, no fabricated
attributes, actually-ran-compile — plus the evaluation-model footguns:
conditional **DENY that fails open** on a missing attribute, **single-role deny**
defeated by an allow on another role, **weak happy-path-only tests**,
**over-broad wildcards** (least privilege), **derived roles not imported**,
**role policies misused to grant**, and **schemas not actually wired**.

**cerbos-synapse-extension** (`criteria/cerbos-synapse-extension.json` + asserts):
ask-for-licence-first, simplest kind/runtime, references loaded, correct
entry-point/callback names, tests when asked — plus **unpinned remote extension
URLs** (checksum), **wrong Envoy response mode / missing map_cerbos_response**,
and **unverified JWTs** (`auxData.jwt` without `keySetID`).

Each criterion has a good+bad calibration fixture; the deterministic policy
fixtures are real bundles that `cerbos compile` accepts.

## Layout

```
evals/
├── promptfoo.calibration.yaml   # judge-vs-human agreement gate (run first)
├── promptfoo.policy.yaml        # cerbos-policy cases
├── promptfoo.synapse.yaml       # cerbos-synapse-extension cases
├── promptfoo.trigger.yaml       # does the right skill fire / stay silent
├── providers/
│   ├── skill-runner.js          # runs a skill in an isolated workspace, returns files
│   └── replay.js                # replays a labeled fixture (calibration)
├── assertions/
│   ├── cerbos-compile.js        # ground truth: real `cerbos compile` (policy)
│   ├── policy-static.js         # schema headers, rule names, has-tests
│   ├── synapse-static.js        # forbidden signatures, entrypoints, config wiring
│   ├── judge.js                 # narrow-criteria LLM judge (real + calibration modes)
│   └── skill-fired.js           # trigger check
├── criteria/*.json              # the judge's binary failure-mode criteria
├── tests/*.yaml                 # the eval prompts
├── calibration/                 # human-labeled fixtures
└── scripts/summary.js           # JSON results -> GitHub job summary
```

## Run it

Requires Node 20+, Docker (for the policy compile checks), and
`ANTHROPIC_API_KEY`.

```bash
cd evals
npm install

npm run calibrate      # judge calibration gate (cheap — no agent, just the judge)
npm run eval:policy    # cerbos-policy suite
npm run eval:synapse   # cerbos-synapse-extension suite
npm run eval           # calibration + both suites

npx promptfoo view     # browse the last run in the local UI
```

### Targeting specific cases (surgical runs)

Iterating on one failure? Don't re-run the whole suite. `scripts/eval.sh <suite>
[pattern]` filters by test description (regex):

```bash
scripts/eval.sh policy multi-role            # only cases matching /multi-role/i
scripts/eval.sh synapse envoy                # only synapse Envoy cases
scripts/eval.sh calibration jwt              # only jwt calibration fixtures
scripts/eval.sh policy --failing policy.json # rerun ONLY the last run's failures
```

Equivalently `npm run target -- policy multi-role`, or promptfoo directly with
`--filter-pattern <regex>` / `--filter-failing <prior.json>` / `--filter-range
0:5`. In CI, the manual `workflow_dispatch` run takes a `filter` input for the
same effect.

Models are configurable:

| Env var | Default | Used for |
|---|---|---|
| `EVAL_ACTOR_MODEL` | `claude-sonnet-5` | the agent under test (what users actually run) |
| `EVAL_JUDGE_MODEL` | `claude-haiku-4-5-20251001` | the judge (cheap; temperature 0) |
| `CERBOS_IMAGE` | `ghcr.io/cerbos/cerbos:latest` | compile check image |

## CI

[`.github/workflows/skill-evals.yml`](../.github/workflows/skill-evals.yml) runs
on PRs that touch a skill or the eval harness, plus manual dispatch. It:

1. **selects suites from the changed paths** — a change under
   `cerbos/cerbos-policy/**` or the policy-specific eval files runs the policy
   suite; `cerbos-synapse-extension/**` or synapse eval files run the synapse
   suite; a shared harness change (judge, providers, calibration, deps) runs
   **both**. PRs touching neither skill nor the harness don't trigger it at all;
2. runs the **calibration gate** — hard-fails if the judge drifted from the labels;
3. runs the selected suite(s);
4. writes a pass/fail summary and uploads JSON + JUnit;
5. fails the check if a suite that ran regressed.

Manual dispatch (`workflow_dispatch`) takes a `run` input (`all` / `policy` /
`synapse`) to force a suite. Set the repo secret `ANTHROPIC_API_KEY`; optionally
set repo variables `EVAL_ACTOR_MODEL` / `EVAL_JUDGE_MODEL`.

## Extending

- **New case:** add an entry to `tests/policy.yaml` or `tests/synapse.yaml` (a
  `description` + `vars.request`; `vars.criteria` to scope the judge;
  `vars.seedFiles` to start from existing files).
- **New judge criterion:** add to the relevant `criteria/*.json`, then add at
  least one calibration fixture that exercises it so it's calibrated.
- **New calibration fixture:** a dir under `calibration/<skill>/<name>/` with
  `label.json` (`label` + expected per-criterion verdicts), optional
  `transcript.txt`, and a `files/` tree; reference it from
  `promptfoo.calibration.yaml`.

## What this is not

- **Not a live Synapse runner.** The Synapse image is licensed, so CI can't
  execute those extensions — the synapse suite relies on static signature checks
  and the judge. If you wire a licensed image + credentials into CI, you can add
  a real `synapse test` assertion later.
- **Not variance analysis.** Runs are single-shot per case. If flakiness becomes
  an issue, add `--repeat N` and gate on pass-rate instead of all-pass.
```
