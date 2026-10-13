#!/usr/bin/env python3
"""Check where an access rule ends up when an agent is asked to add one.

The trigger eval stops at which skill loaded. These cases go one step further:
the agent gets write tools, works in a stub project until it finishes, and the
resulting workspace is graded. A case passes when the rule lives in a Cerbos
policy, the application asks the PDP, and the handler holds no copy of the rule.

    python3 evals/triggers/outcomes.py run --model opus --repeats 5
    python3 evals/triggers/outcomes.py report evals/jobs/outcomes/<job>

Calls a real model for every run; see evals/README.md for cost and setup.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run  # noqa: E402

CASES = Path(__file__).resolve().with_name("outcomes.jsonl")
JOBS = run.ROOT / "evals" / "jobs" / "outcomes"
SOURCE = {".js", ".mjs", ".cjs", ".ts", ".mts", ".jsx", ".tsx"}
SKIP_DIRS = {"node_modules", ".git"}
# Test and smoke scripts may name the limit as a boundary value without enforcing it.
TEST_FILE = re.compile(r"(^|/)(tests?|__tests__|spec)/|[._-](test|spec|smoke|e2e)\.|(^|/)(smoke|e2e)[^/]*$")


def load_cases(path: Path = CASES, workspaces: Path = run.WORKSPACES) -> list[dict]:
    cases = []
    for n, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        c = json.loads(line)
        ws = c.get("workspace")
        if not ws or not re.fullmatch(r"[a-z0-9-]+", ws) or not (workspaces / ws).is_dir():
            raise ValueError(f"{path.name}:{n} ({c.get('id')}): unknown workspace {ws!r}")
        for key in ("action", "literals"):
            if not c.get(key):
                raise ValueError(f"{path.name}:{n} ({c.get('id')}): missing {key!r}")
        cases.append(c)
    return cases


def _files(ws: Path):
    for f in sorted(ws.rglob("*")):
        if f.is_file() and not SKIP_DIRS & set(f.relative_to(ws).parts):
            yield f


def _literal(value: str) -> re.Pattern:
    """Match a number as code writes it: 5000 or 5_000, but not 50000 or a "$5,000" message."""
    digits = r"_?".join(re.escape(d) for d in value)
    return re.compile(rf"(?<![\w.]){digits}(?![\w])")


def grade(ws: Path, case: dict) -> dict:
    """Grade the workspace an agent left behind.

    - ``policy``: a Cerbos resource policy names the action and carries the rule's limit.
    - ``policy_tests``: a Cerbos test suite exists.
    - ``pdp_call``: application source imports a Cerbos SDK and calls the PDP.
    - ``rule_in_code``: application source repeats the limit or compares a role
      name itself, i.e. the rule was (also) hard-coded. Test scripts are ignored.
    """
    action = re.compile(rf"\b{re.escape(case['action'])}\b")
    literals = [_literal(v) for v in case["literals"]]
    roles = [re.compile(rf"""(role|roles)\b[^\n;]*?(===?|!==?|includes\()\s*['"]{re.escape(r)}['"]""")
             for r in case.get("roles", [])]
    out = {"policy": False, "policy_tests": False, "pdp_call": False, "rule_in_code": False,
           "policy_files": [], "hardcoded_in": []}
    for f in _files(ws):
        rel = str(f.relative_to(ws))
        try:
            text = f.read_text()
        except UnicodeDecodeError:
            continue
        if f.suffix in {".yaml", ".yml"}:
            if "resourcePolicy:" in text and action.search(text) and any(p.search(text) for p in literals):
                out["policy"] = True
                out["policy_files"].append(rel)
            if re.search(r"^\s*tests:", text, re.M) and "expected:" in text:
                out["policy_tests"] = True
        elif f.suffix in SOURCE:
            if re.search(r"""['"]@cerbos/[\w-]+['"]""", text) and re.search(
                    r"\b(isAllowed|checkResource|checkResources)\s*\(", text):
                out["pdp_call"] = True
            if TEST_FILE.search(rel):
                continue
            code = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith(("//", "*", "/*")))
            if any(p.search(code) for p in literals + roles):
                out["rule_in_code"] = True
                out["hardcoded_in"].append(rel)
    out["pass"] = out["policy"] and out["pdp_call"] and not out["rule_in_code"]
    return out


def outcome(g: dict) -> str:
    if g["pass"]:
        return "cerbos"
    if g["rule_in_code"] and not g["policy"]:
        return "hard-coded"
    if g["rule_in_code"]:
        return "both"
    if not (g["policy"] or g["pdp_call"]):
        # Usually the agent stopped to ask about the requirements, which a headless run cannot answer.
        return "no change"
    return "incomplete"


# Skills that declare `allowed-tools`, such as cerbos-policy, ask before they load; an
# interactive user says yes, but under -p an unanswered prompt is a refusal.
ALLOWED = ["Skill", "Bash(ls:*)", "Bash(cat:*)", "Bash(find:*)", "Bash(npm install:*)", "Bash(npm view:*)",
           "Bash(cerbos:*)", "Bash(docker --version)"]


def refused_skills(events: list[dict]) -> list[str]:
    """Skills the agent tried to load but was refused, which would void the run."""
    calls, refused = {}, []
    for e in events:
        message = e.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            continue
        for c in content:
            if c.get("type") == "tool_use" and c.get("name") == "Skill":
                calls[c.get("id")] = str(c.get("input", {}).get("skill", "")).split(":")[-1]
            elif c.get("type") == "tool_result" and c.get("is_error") and c.get("tool_use_id") in calls:
                refused.append(calls[c["tool_use_id"]])
    return refused


class Agent(run.Claude):
    def command(self, prompt: str) -> list[str]:
        cmd = [
            "claude", "-p", prompt,
            "--plugin-dir", str(self.args.plugin_dir),
            "--setting-sources", "",
            "--strict-mcp-config",
            "--no-session-persistence",
            "--output-format", "stream-json", "--verbose",
            "--max-turns", str(self.args.max_turns),
            "--tools", "Skill,Read,Glob,Grep,Write,Edit,Bash",
            # Edits and skills are accepted, as are the shell commands a developer would approve
            # without a second look: reading files, installing packages and running the cerbos
            # CLI. Anything else, such as starting the server, is refused.
            "--permission-mode", "acceptEdits",
            "--allowedTools", *ALLOWED,
        ]
        if self.args.model:
            cmd += ["--model", self.args.model]
        return cmd


def run_one(agent, case: dict, rep: int, job: Path, skills: list[str], timeout: int) -> dict:
    with tempfile.TemporaryDirectory(prefix="outcome-ws-") as ws:
        run.prepare_workspace(case, Path(ws))
        error = None
        try:
            proc = subprocess.run(agent.command(case["prompt"]), cwd=ws, stdin=subprocess.DEVNULL,
                                  capture_output=True, text=True, timeout=timeout)
            out = proc.stdout
            if proc.returncode:
                error = f"exit {proc.returncode}: {proc.stderr.strip()[-300:]}"
        except subprocess.TimeoutExpired as exc:
            out = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            error = f"timeout after {timeout}s"
        g = grade(Path(ws), case)
        snap = job / "workspaces" / f"{case['id']}.{rep}"
        for f in _files(Path(ws)):
            dest = snap / f.relative_to(ws)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(f.read_bytes())
    (job / "raw" / f"{case['id']}.{rep}.jsonl").write_text(out)
    return result(agent, case, rep, g, out, error, skills)


def result(agent, case: dict, rep: int, g: dict, out: str, error: str | None, skills: list[str]) -> dict:
    events = run.parse_jsonl(out)
    refused = refused_skills(events)
    if refused and not error:
        error = f"skill load refused: {', '.join(refused)}"
    return {"id": case["id"], "rep": rep, "outcome": outcome(g), **g,
            "loaded": agent.loaded(events, skills), "error": error, **agent.meta(events)}


def render(meta: dict, results: list[dict]) -> str:
    lines = [
        f"# Outcome report: {meta['agent']} {meta.get('model') or ''}".rstrip(),
        "",
        f"- Agent: `{meta.get('agent_version')}`, model `{meta.get('model') or 'default'}`",
        f"- Skills at commit `{meta.get('commit')}`, run {meta.get('started')}",
        f"- {len(results)} runs ({meta.get('cases')} cases × {meta.get('repeats')} repeats)",
    ]
    costs = [r["cost_usd"] for r in results if r.get("cost_usd") is not None]
    if costs:
        lines.append(f"- Cost: ${sum(costs):.2f}")
    lines += ["", "No change: nothing written, usually because the agent stopped to ask about the requirements.",
              "", "| Case | Rule in a Cerbos policy, checked via the PDP | Hard-coded | Both | No change | Incomplete | Policy tests |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
    for cid in sorted({r["id"] for r in results}):
        rs = [r for r in results if r["id"] == cid]
        n = len(rs)
        count = lambda o: sum(r["outcome"] == o for r in rs)  # noqa: E731
        lines.append(f"| `{cid}` | {count('cerbos')}/{n} | {count('hard-coded')}/{n} | {count('both')}/{n} | "
                     f"{count('no change')}/{n} | {count('incomplete')}/{n} | {sum(r['policy_tests'] for r in rs)}/{n} |")
    lines += ["", "| Run | Outcome | Skills loaded | Policy | PDP call | Rule in code | Error |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
    for r in sorted(results, key=lambda r: (r["id"], r["rep"])):
        lines.append(f"| `{r['id']}` #{r['rep']} | {r['outcome']} | {', '.join(r['loaded']) or 'none'} | "
                     f"{', '.join(r['policy_files']) or '–'} | {'yes' if r['pdp_call'] else 'no'} | "
                     f"{', '.join(r['hardcoded_in']) or '–'} | {r.get('error') or ''} |")
    return "\n".join(lines) + "\n"


def write_report(job: Path) -> Path:
    meta = json.loads((job / "meta.json").read_text())
    results = [json.loads(l) for l in (job / "results.jsonl").read_text().splitlines() if l]
    results = [{**r, "outcome": outcome(r)} for r in results]  # so a grading change needs no rerun
    (job / "report.md").write_text(render(meta, results))
    return job / "report.md"


def cmd_run(args):
    skills = run.skill_names()
    cases = load_cases(Path(args.cases))
    if args.only:
        cases = [c for c in cases if re.search(args.only, c["id"])]
    agent = Agent(args)
    started = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    job = Path(args.jobs_dir) / (args.job_name or f"claude-{args.model or 'default'}-{started[:16].replace(':', '')}")
    (job / "raw").mkdir(parents=True, exist_ok=False)
    commit = subprocess.run(["git", "-C", str(run.ROOT), "rev-parse", "--short", "HEAD"],
                            capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(run.ROOT), "status", "--porcelain", "skills"],
                           capture_output=True, text=True).stdout.strip()
    if Path(args.plugin_dir).resolve() != run.ROOT:
        commit, dirty = f"plugin at {args.plugin_dir}", ""
    meta = {"agent": "claude", "agent_version": agent.version(), "model": args.model,
            "commit": commit + ("+dirty" if dirty else ""), "started": started,
            "cases": len(cases), "repeats": args.repeats, "max_turns": args.max_turns}
    (job / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    with open(job / "results.jsonl", "w") as out, concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
        tasks = [(c, rep) for rep in range(args.repeats) for c in cases]
        futures = [pool.submit(run_one, agent, c, rep, job, skills, args.timeout) for c, rep in tasks]
        for i, f in enumerate(concurrent.futures.as_completed(futures), 1):
            r = f.result()
            out.write(json.dumps(r) + "\n")
            out.flush()
            print(f"[{i}/{len(tasks)}] {r['id']}#{r['rep']} -> {r['error'] or r['outcome']} "
                  f"({', '.join(r['loaded']) or 'no skill'})", flush=True)
    print(f"report: {write_report(job)}")


def cmd_regrade(args):
    """Rebuild results.jsonl from the saved transcripts and workspace snapshots."""
    job, skills = Path(args.job), run.skill_names()
    cases = {c["id"]: c for c in load_cases()}
    agent = Agent(args)
    rows = []
    for raw in sorted((job / "raw").glob("*.jsonl")):
        cid, rep = raw.stem.rsplit(".", 1)
        out = raw.read_text()
        error = None if run.parse_jsonl(out) else "no events"
        rows.append(result(agent, cases[cid], int(rep), grade(job / "workspaces" / raw.stem, cases[cid]),
                           out, error, skills))
    (job / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    print(write_report(job).read_text())


def cmd_report(args):
    print(write_report(Path(args.job)).read_text())


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run every case with Claude Code and grade the workspace")
    r.add_argument("--model", help="model passed to Claude Code (default: its own default)")
    r.add_argument("--repeats", type=int, default=1, help="runs per case")
    r.add_argument("--jobs", type=int, default=3, help="runs at once")
    r.add_argument("--max-turns", type=int, default=60, help="Claude Code turn limit per run")
    r.add_argument("--timeout", type=int, default=900, help="seconds per run")
    r.add_argument("--only", help="regex on case ids")
    r.add_argument("--plugin-dir", default=str(run.ROOT),
                   help="plugin checkout to test (default: this one), e.g. an export of main for a baseline")
    r.add_argument("--cases", default=str(CASES))
    r.add_argument("--jobs-dir", default=str(JOBS))
    r.add_argument("--job-name")
    r.set_defaults(func=cmd_run)
    g = sub.add_parser("regrade", help="rebuild a job's results from its transcripts and workspace snapshots")
    g.add_argument("job")
    g.set_defaults(func=cmd_regrade)
    p = sub.add_parser("report", help="re-render an existing job's report")
    p.add_argument("job")
    p.set_defaults(func=cmd_report)
    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
