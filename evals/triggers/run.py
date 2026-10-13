#!/usr/bin/env python3
"""Measure which Cerbos skill an agent loads for each prompt in prompts.jsonl.

Each prompt runs in a fresh workspace with the plugin installed from this
checkout. The workspace is empty unless the prompt names a stub project under
workspaces/, which is copied in first. The runner records every Cerbos skill the agent loaded, in order, and
writes a per-skill precision/recall report with a confusion matrix.

    python3 evals/triggers/run.py run --agent claude --model sonnet
    python3 evals/triggers/run.py run --agent codex
    python3 evals/triggers/run.py report evals/jobs/triggers/<job>

Calls a real model for every prompt; see evals/README.md for cost and setup.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROMPTS = Path(__file__).resolve().with_name("prompts.jsonl")
WORKSPACES = Path(__file__).resolve().with_name("workspaces")
JOBS = ROOT / "evals" / "jobs" / "triggers"
PLUGIN = "cerbos-skills"
NONE = "none"

SKILL_MD = re.compile(r"skills/([a-z0-9-]+)/SKILL\.md")


def skill_names() -> list[str]:
    return sorted(p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md"))


def load_prompts(path: Path = PROMPTS, skills: list[str] | None = None,
                 workspaces: Path = WORKSPACES) -> list[dict]:
    skills = skill_names() if skills is None else skills
    prompts, seen = [], set()
    for n, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        p = json.loads(line)
        where = f"{path.name}:{n} ({p.get('id')})"
        if p["id"] in seen:
            raise ValueError(f"{where}: duplicate id")
        seen.add(p["id"])
        for name in [p["expect"], *p.get("also_ok", []), *p.get("near", [])]:
            if name is not None and name not in skills:
                raise ValueError(f"{where}: unknown skill {name!r}")
        if p["expect"] in p.get("near", []):
            raise ValueError(f"{where}: expected skill is also listed as a near miss")
        ws = p.get("workspace")
        if ws is not None and (not re.fullmatch(r"[a-z0-9-]+", ws) or not (workspaces / ws).is_dir()):
            raise ValueError(f"{where}: unknown workspace {ws!r}")
        p.setdefault("also_ok", [])
        p.setdefault("near", [])
        prompts.append(p)
    return prompts


def _ordered(names, skills):
    out = []
    for name in names:
        if name in skills and name not in out:
            out.append(name)
    return out


def claude_loaded(events: list[dict], skills: list[str]) -> list[str]:
    """Skills loaded through the Skill tool, or by reading a SKILL.md directly."""
    names = []
    for e in events:
        if e.get("type") != "assistant":
            continue
        for c in e.get("message", {}).get("content", []):
            if c.get("type") != "tool_use":
                continue
            args = c.get("input", {})
            if c.get("name") == "Skill":
                names.append(str(args.get("skill", "")).split(":")[-1].lstrip("/"))
            elif c.get("name") == "Read":
                names += SKILL_MD.findall(str(args.get("file_path", "")))
    return _ordered(names, skills)


def codex_loaded(events: list[dict], skills: list[str]) -> list[str]:
    """Codex loads a skill by reading its SKILL.md with a shell command."""
    names = []
    for e in events:
        item = e.get("item", {})
        if e.get("type") == "item.started" or item.get("type") != "command_execution":
            continue
        names += SKILL_MD.findall(item.get("command", ""))
    return _ordered(names, skills)


def parse_jsonl(text: str) -> list[dict]:
    events = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return events


class Claude:
    name = "claude"

    def __init__(self, args):
        self.args = args

    def setup(self, tmp: Path):
        pass

    def version(self) -> str:
        return subprocess.run(["claude", "--version"], capture_output=True, text=True).stdout.strip()

    def command(self, prompt: str) -> list[str]:
        cmd = [
            "claude", "-p", prompt,
            "--plugin-dir", str(ROOT),
            # Skip user settings so the user's own plugins and MCP servers do not compete.
            "--setting-sources", "",
            "--strict-mcp-config",
            "--no-session-persistence",
            "--output-format", "stream-json", "--verbose",
            "--max-turns", str(self.args.max_turns),
            # Read-only tools: enough to load a skill and its references, nothing that changes the machine.
            "--tools", "Skill,Read,Glob,Grep",
        ]
        if self.args.model:
            cmd += ["--model", self.args.model]
        return cmd

    def env(self):
        return None

    def loaded(self, events, skills):
        return claude_loaded(events, skills)

    def meta(self, events) -> dict:
        out = {}
        for e in events:
            if e.get("type") == "system" and e.get("subtype") == "init":
                out["model"] = e.get("model")
                out["plugin_skills"] = sorted(s for s in e.get("skills", []) if s.startswith(PLUGIN + ":"))
            if e.get("type") == "result":
                out["cost_usd"] = e.get("total_cost_usd")
                out["turns"] = e.get("num_turns")
        return out


class Codex:
    name = "codex"

    def __init__(self, args):
        self.args = args
        self.home = None

    def setup(self, tmp: Path):
        """Install the plugin into a throwaway CODEX_HOME from a local marketplace.

        The repository's own Codex marketplace points at GitHub, which would test
        the published skills rather than this checkout.
        """
        self.home = tmp / "codex-home"
        market = tmp / "marketplace"
        plugin = market / "plugins" / PLUGIN
        self.home.mkdir(parents=True)
        plugin.mkdir(parents=True)
        for part in (".codex-plugin", "skills", "assets"):
            shutil.copytree(ROOT / part, plugin / part)
        (market / ".agents" / "plugins").mkdir(parents=True)
        (market / ".agents" / "plugins" / "marketplace.json").write_text(json.dumps({
            "name": "cerbos-skills-trigger-eval",
            "plugins": [{
                "name": PLUGIN,
                "source": {"source": "local", "path": f"./plugins/{PLUGIN}"},
                "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                "category": "Coding",
            }],
        }))
        auth = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "auth.json"
        if auth.exists() and not os.environ.get("OPENAI_API_KEY"):
            (self.home / "auth.json").symlink_to(auth)
        env = self.env()
        for cmd in (["codex", "plugin", "marketplace", "add", str(market)],
                    ["codex", "plugin", "add", f"{PLUGIN}@cerbos-skills-trigger-eval"]):
            subprocess.run(cmd, env=env, check=True, capture_output=True, text=True)

    def version(self) -> str:
        return subprocess.run(["codex", "--version"], capture_output=True, text=True).stdout.strip()

    def command(self, prompt: str) -> list[str]:
        cmd = [
            "codex", "exec", "--json", "--skip-git-repo-check", "--ephemeral",
            "-s", "read-only",
            "-c", 'web_search="disabled"',
        ]
        if self.args.model:
            cmd += ["-m", self.args.model]
        return cmd + ["--", prompt]

    def env(self):
        return {**os.environ, "CODEX_HOME": str(self.home)}

    def loaded(self, events, skills):
        return codex_loaded(events, skills)

    def meta(self, events) -> dict:
        usage = [e.get("usage", {}) for e in events if e.get("type") == "turn.completed"]
        return {"model": self.args.model or "default",
                "output_tokens": sum(u.get("output_tokens", 0) for u in usage)}


AGENTS = {"claude": Claude, "codex": Codex}


def prepare_workspace(prompt: dict, ws: Path, workspaces: Path = WORKSPACES):
    """Copy the prompt's stub project, if any, into the empty workspace."""
    if prompt.get("workspace"):
        shutil.copytree(workspaces / prompt["workspace"], ws, dirs_exist_ok=True)


def run_one(agent, prompt: dict, rep: int, raw_dir: Path, skills: list[str], timeout: int) -> dict:
    with tempfile.TemporaryDirectory(prefix="trigger-ws-") as ws:
        prepare_workspace(prompt, Path(ws))
        error = None
        try:
            proc = subprocess.run(agent.command(prompt["prompt"]), cwd=ws, env=agent.env(),
                                  stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                  timeout=timeout)
            out, err = proc.stdout, proc.stderr
            if proc.returncode:
                error = f"exit {proc.returncode}: {err.strip()[-300:]}"
        except subprocess.TimeoutExpired as exc:
            out = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            error = f"timeout after {timeout}s"
    (raw_dir / f"{prompt['id']}.{rep}.jsonl").write_text(out)
    events = parse_jsonl(out)
    if not events and not error:
        error = "no events"
    return {
        "id": prompt["id"], "rep": rep, "expect": prompt["expect"], "workspace": prompt.get("workspace"),
        "also_ok": prompt["also_ok"], "near": prompt["near"],
        "loaded": agent.loaded(events, skills), "error": error, **agent.meta(events),
    }


# ---------------------------------------------------------------- scoring


def _label(name):
    return name or NONE


def score(results: list[dict], skills: list[str]) -> dict:
    rows = [r for r in results if not r.get("error")]
    per_skill = {}
    for s in skills:
        pos = [r for r in rows if r["expect"] == s]
        hit = [r for r in pos if s in r["loaded"]]
        first = [r for r in pos if r["loaded"][:1] == [s]]
        fired = [r for r in rows if s in r["loaded"]]
        ok = [r for r in fired if r["expect"] == s or s in r["also_ok"]]
        near = [r for r in rows if s in r["near"]]
        near_fired = [r for r in near if s in r["loaded"]]
        per_skill[s] = {
            "positives": len(pos), "recall": _ratio(len(hit), len(pos)),
            "first_pick": _ratio(len(first), len(pos)),
            "fired": len(fired), "precision": _ratio(len(ok), len(fired)),
            "near_misses": len(near), "near_miss_fired": _ratio(len(near_fired), len(near)),
        }
    negatives = [r for r in rows if r["expect"] is None]
    labels = skills + [NONE]
    matrix = {e: {p: 0 for p in labels} for e in labels}
    for r in rows:
        matrix[_label(r["expect"])][_label((r["loaded"] or [None])[0])] += 1
    positives = [r for r in rows if r["expect"]]
    return {
        "runs": len(results), "errors": len(results) - len(rows),
        "per_skill": per_skill,
        "overall": {
            "recall": _ratio(sum(r["expect"] in r["loaded"] for r in positives), len(positives)),
            "first_pick": _ratio(sum(r["loaded"][:1] == [r["expect"]] for r in positives), len(positives)),
            "any_cerbos_skill": _ratio(sum(bool(r["loaded"]) for r in positives), len(positives)),
            "false_trigger_on_none": _ratio(sum(bool(r["loaded"]) for r in negatives), len(negatives)),
        },
        "confusion": matrix,
    }


def _ratio(n, d):
    return {"n": n, "of": d, "rate": round(n / d, 3) if d else None}


def _pct(x):
    if x["rate"] is None:
        return "–"
    return f"{round(100 * x['rate'])}% ({x['n']}/{x['of']})"


def _short(name):
    return {"cerbos": "router", NONE: "none"}.get(name, name.removeprefix("cerbos-"))


def render(meta: dict, results: list[dict], skills: list[str]) -> str:
    s = score(results, skills)
    o = s["overall"]
    lines = [
        f"# Trigger report: {meta['agent']} {meta.get('model') or ''}".rstrip(),
        "",
        f"- Agent: `{meta.get('agent_version')}`, model `{meta.get('model') or 'default'}`",
        f"- Skills at commit `{meta.get('commit')}`, run {meta.get('started')}",
        f"- {s['runs']} runs ({meta.get('prompts')} prompts × {meta.get('repeats')} repeats), {s['errors']} errored and excluded",
    ]
    if meta.get("cost_usd") is not None:
        lines.append(f"- Cost: ${meta['cost_usd']:.2f}")
    lines += [
        "",
        "| Overall | |",
        "| --- | --- |",
        f"| Expected skill loaded (recall) | {_pct(o['recall'])} |",
        f"| Expected skill loaded first | {_pct(o['first_pick'])} |",
        f"| Any Cerbos skill loaded on a Cerbos prompt | {_pct(o['any_cerbos_skill'])} |",
        f"| Any Cerbos skill loaded on an unrelated prompt | {_pct(o['false_trigger_on_none'])} |",
        "",
        "Recall: the expected skill loaded at any point. First pick: it was the first Cerbos skill loaded.",
        "Precision: of the runs where the skill loaded, the share where it was expected or listed in `also_ok`.",
        "Near-miss fired: how often it loaded on prompts listing it under `near` (lower is better).",
        "",
        "| Skill | Recall | First pick | Precision | Near-miss fired |",
        "| --- | --- | --- | --- | --- |",
    ]
    for name, m in s["per_skill"].items():
        lines.append(f"| `{name}` | {_pct(m['recall'])} | {_pct(m['first_pick'])} | "
                     f"{_pct(m['precision'])} | {_pct(m['near_miss_fired'])} |")
    labels = skills + [NONE]
    lines += [
        "",
        "## Confusion matrix",
        "",
        "Rows are the expected skill; columns are the first Cerbos skill loaded.",
        "",
        "| expected ↓ / loaded → | " + " | ".join(_short(c) for c in labels) + " |",
        "| --- |" + " --- |" * len(labels),
    ]
    for e in labels:
        cells = [str(s["confusion"][e][p] or "·") for p in labels]
        cells = [f"**{c}**" if p == e and c != "·" else c for c, p in zip(cells, labels)]
        lines.append(f"| {_short(e)} | " + " | ".join(cells) + " |")
    misses = [r for r in results if not r.get("error") and (
        (r["expect"] and r["expect"] not in r["loaded"])
        or any(x != r["expect"] and x not in r["also_ok"] for x in r["loaded"]))]
    lines += ["", "## Misses", "",
              "Runs where the expected skill did not load, or an unexpected skill did.", "",
              "| Prompt | Rep | Expected | Loaded |", "| --- | --- | --- | --- |"]
    for r in sorted(misses, key=lambda r: (r["id"], r["rep"])):
        loaded = ", ".join(_short(x) for x in r["loaded"]) or "none"
        lines.append(f"| `{r['id']}` | {r['rep']} | {_short(_label(r['expect']))} | {loaded} |")
    errors = [r for r in results if r.get("error")]
    if errors:
        lines += ["", "## Errors", ""]
        lines += [f"- `{r['id']}` rep {r['rep']}: {r['error']}" for r in errors]
    return "\n".join(lines) + "\n"


def relabel(results: list[dict], prompts: list[dict]) -> list[dict]:
    """Score against the current labels, so a label fix does not need a rerun."""
    labels = {p["id"]: {k: p[k] for k in ("expect", "also_ok", "near")} for p in prompts}
    return [{**r, **labels.get(r["id"], {})} for r in results]


def write_report(job: Path, skills: list[str], prompts: list[dict] | None = None):
    meta = json.loads((job / "meta.json").read_text())
    results = [json.loads(l) for l in (job / "results.jsonl").read_text().splitlines() if l]
    results = relabel(results, load_prompts(skills=skills) if prompts is None else prompts)
    costs = [r["cost_usd"] for r in results if r.get("cost_usd") is not None]
    if costs:
        meta["cost_usd"] = sum(costs)
    (job / "report.md").write_text(render(meta, results, skills))
    (job / "score.json").write_text(json.dumps(score(results, skills), indent=2) + "\n")
    return job / "report.md"


# ---------------------------------------------------------------- CLI


def cmd_run(args):
    skills = skill_names()
    prompts = load_prompts(Path(args.prompts), skills)
    if args.only:
        prompts = [p for p in prompts if re.search(args.only, p["id"])]
    agent = AGENTS[args.agent](args)
    started = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    job = Path(args.jobs_dir) / (args.job_name or f"{args.agent}-{args.model or 'default'}-{started[:16].replace(':', '')}")
    raw = job / "raw"
    raw.mkdir(parents=True, exist_ok=False)
    commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
                            capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "skills"],
                           capture_output=True, text=True).stdout.strip()
    meta = {"agent": args.agent, "agent_version": agent.version(), "model": args.model,
            "commit": commit + ("+dirty" if dirty else ""), "started": started,
            "prompts": len(prompts), "repeats": args.repeats, "max_turns": args.max_turns}
    (job / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    lock = threading.Lock()
    with tempfile.TemporaryDirectory(prefix="trigger-eval-") as tmp, \
            open(job / "results.jsonl", "w") as out:
        agent.setup(Path(tmp))
        tasks = [(p, rep) for rep in range(args.repeats) for p in prompts]
        with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
            futures = [pool.submit(run_one, agent, p, rep, raw, skills, args.timeout) for p, rep in tasks]
            for i, f in enumerate(concurrent.futures.as_completed(futures), 1):
                r = f.result()
                with lock:
                    out.write(json.dumps(r) + "\n")
                    out.flush()
                status = r["error"] or (", ".join(r["loaded"]) or "none")
                print(f"[{i}/{len(tasks)}] {r['id']}#{r['rep']} expect={_label(r['expect'])} -> {status}",
                      flush=True)
    print(f"report: {write_report(job, skills, prompts)}")


def cmd_report(args):
    print(write_report(Path(args.job), skill_names()).read_text())


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="send every prompt to an agent and score it")
    r.add_argument("--agent", choices=sorted(AGENTS), required=True)
    r.add_argument("--model", help="model passed to the agent (default: the agent's own default)")
    r.add_argument("--repeats", type=int, default=1, help="runs per prompt")
    r.add_argument("--jobs", type=int, default=4, help="prompts run concurrently")
    r.add_argument("--max-turns", type=int, default=8, help="Claude Code turn limit per prompt")
    r.add_argument("--timeout", type=int, default=300, help="seconds per prompt")
    r.add_argument("--only", help="regex on prompt ids, for a quick subset")
    r.add_argument("--prompts", default=str(PROMPTS))
    r.add_argument("--jobs-dir", default=str(JOBS))
    r.add_argument("--job-name")
    r.set_defaults(func=cmd_run)
    p = sub.add_parser("report", help="re-score an existing job directory")
    p.add_argument("job")
    p.set_defaults(func=cmd_report)
    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
