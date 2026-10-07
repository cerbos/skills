"""Move the evals and skill to a new Cerbos PDP release, then prove the tasks still hold.

Run from the repository root with Docker running:

    uv run --no-project --with PyYAML==6.0.2 python evals/update_cerbos_version.py [VERSION]

VERSION defaults to the latest GitHub release (for example 0.56.0). The script:

1. Resolves the multi-arch image digest for ghcr.io/cerbos/cerbos:VERSION.
2. Repins every task Dockerfile, updates the version named in task instructions,
   task READMEs, the skill's targetsCerbosVersion and the cerbos/cerbosctl image
   tags in the skill's Markdown, and bumps each task's patch version and the
   skill's minor version. Feature minimums such as "0.55+" in the skill
   references are left alone.
3. Runs the verifier regression tests, then Harbor's oracle (expected reward 1) and
   nop (expected reward 0) agents on every task. The oracle run is the real check:
   it replays each task's contract-derived decisions against the new PDP.

Options:
    --dry-run      Show what would change; edit nothing and run nothing.
    --skip-checks  Edit files only.
    --live         Also run the skill with Codex (one attempt per task) and report
                   rewards; this uses model credentials.

A failing oracle usually means the new PDP changed behaviour that a task's
contract.py encodes. Inspect the named stage's log and check-resources.json under
the printed job directory, confirm the change in the release notes, then update
that task's contract, cases.json and reference solution.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TASKS = ROOT / "evals" / "tasks"
SKILL = ROOT / "skills" / "cerbos-policy" / "SKILL.md"
IMAGE = "ghcr.io/cerbos/cerbos"
HARBOR = ["uvx", "--from", "harbor==0.23.0", "harbor"]
# Only the policy tasks run on the Cerbos PDP; Synapse tasks follow Synapse releases.
POLICY_TASKS = "cerbos-policy-*"
PIN = re.compile(rf"{re.escape(IMAGE)}:(\d+\.\d+\.\d+)@sha256:[0-9a-f]{{64}}")


def latest_release():
    url = "https://api.github.com/repos/cerbos/cerbos/releases/latest"
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.load(response)["tag_name"].lstrip("v")


def resolve_digest(version):
    result = subprocess.run(
        ["docker", "buildx", "imagetools", "inspect", f"{IMAGE}:{version}"],
        capture_output=True,
        text=True,
    )
    match = re.search(r"^Digest:\s+(sha256:[0-9a-f]{64})", result.stdout, re.MULTILINE)
    if result.returncode or not match:
        sys.exit(f"Could not resolve {IMAGE}:{version}: {result.stderr.strip() or result.stdout.strip()}")
    return match.group(1)


def current_version():
    versions = set()
    for dockerfile in TASKS.glob(f"{POLICY_TASKS}/environment/Dockerfile"):
        versions.update(PIN.findall(dockerfile.read_text()))
    if len(versions) != 1:
        sys.exit(f"Expected one pinned Cerbos version across tasks, found {sorted(versions)}")
    return versions.pop()


def bump_patch(text):
    def bump(match):
        major, minor, patch = match.group(2).split(".")
        return f'{match.group(1)}"{major}.{minor}.{int(patch) + 1}"'

    # Only the [task] table's version; schema_version and other tables are untouched.
    head, sep, rest = text.partition("[task]")
    body, next_table, tail = rest.partition("\n[")
    body = re.sub(r'^(version\s*=\s*)"(\d+\.\d+\.\d+)"', bump, body, count=1, flags=re.MULTILINE)
    return head + sep + body + next_table + tail


def planned_edits(old, new, digest):
    """Return {path: new_text} for every file whose content changes."""
    version = re.compile(rf"(?<![\d.]){re.escape(old)}(?![\d.])")
    edits = {}
    for task in sorted(p for p in TASKS.glob(POLICY_TASKS) if (p / "task.toml").is_file()):
        changed = False
        dockerfile = task / "environment" / "Dockerfile"
        if dockerfile.is_file():
            text = dockerfile.read_text()
            edits[dockerfile] = PIN.sub(f"{IMAGE}:{new}@{digest}", text)
            changed |= edits[dockerfile] != text
        for name in ("instruction.md", "README.md"):
            path = task / name
            if path.is_file():
                text = path.read_text()
                edits[path] = version.sub(new, text)
                changed |= edits[path] != text
        if changed:
            # A new runtime changes the task, so its version moves too.
            edits[task / "task.toml"] = bump_patch((task / "task.toml").read_text())
    skill = SKILL.read_text()
    edits[SKILL] = re.sub(
        r'(targetsCerbosVersion:\s*)"[^"]*"', rf'\g<1>"{new}"', skill, count=1
    )
    # Tags only: prose such as "requires v0.55.0 or later" keeps its version.
    tag = re.compile(rf"({re.escape(IMAGE)}(?:ctl)?):{re.escape(old)}(?![\d.])")
    for path in sorted(SKILL.parent.rglob("*.md")):
        edits[path] = tag.sub(rf"\g<1>:{new}", edits.get(path, path.read_text()))
    if edits[SKILL] != skill:
        # CI requires a skill version bump whenever the skill's files change.
        edits[SKILL] = re.sub(
            r'(\n  version:\s*)"(\d+)\.(\d+)"',
            lambda m: f'{m.group(1)}"{m.group(2)}.{int(m.group(3)) + 1}"',
            edits[SKILL], count=1,
        )
    return {path: text for path, text in edits.items() if text != path.read_text()}


def run(command, **kwargs):
    print("$", " ".join(command), flush=True)
    return subprocess.run(command, cwd=ROOT, **kwargs)


def harbor_job(name, agent_args, env=None):
    jobs = ROOT / "evals" / "jobs"
    command = HARBOR + ["run", "-p", "evals/tasks", "-i", f"*{POLICY_TASKS}", *agent_args, "-q",
                        "--jobs-dir", str(jobs), "--job-name", name]
    run(command, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    rewards = {}
    for result_path in sorted((jobs / name).glob("*/result.json")):
        result = json.loads(result_path.read_text())
        task = result_path.parent.name.rsplit("__", 1)[0]
        scores = (result.get("verifier_result") or {}).get("rewards") or {}
        error = (result.get("exception_info") or {}).get("exception_type")
        failed = sorted(k for k, v in scores.items() if k != "reward" and not v)
        rewards.setdefault(task, []).append((scores.get("reward", 0), failed, error))
    return jobs / name, rewards


def report(title, rewards, expected, job_dir):
    print(f"\n{title} (expected reward {expected}) — {job_dir}")
    ok = bool(rewards)
    for task, trials in sorted(rewards.items()):
        for reward, failed, error in trials:
            good = reward == expected and not error
            ok &= good
            detail = f" error={error}" if error else (f" failed={failed}" if failed and expected else "")
            print(f"  {'PASS' if good else 'FAIL'} {task}: reward={reward}{detail}")
    return ok


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("version", nargs="?", help="Cerbos version, e.g. 0.56.0 (default: latest release)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-checks", action="store_true")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()

    new = (args.version or latest_release()).lstrip("v")
    old = current_version()
    digest = resolve_digest(new)
    print(f"Cerbos {old} -> {new} ({IMAGE}@{digest})")

    edits = planned_edits(old, new, digest)
    for path in edits:
        print(f"  update {path.relative_to(ROOT)}")
    if not edits:
        print("  nothing to change; pins, docs and skill already match")
    if args.dry_run:
        return
    for path, text in edits.items():
        path.write_text(text)
    if args.skip_checks:
        return

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    ok = run([sys.executable, "-m", "unittest", "discover", "-s", "evals",
              "-p", "test_*verifier.py"], stdout=subprocess.DEVNULL).returncode == 0
    print(f"verifier regression tests: {'PASS' if ok else 'FAIL'}")
    job, rewards = harbor_job(f"cerbos-{new}-oracle-{stamp}", ["-a", "oracle"])
    ok &= report("Oracle", rewards, 1, job)
    job, rewards = harbor_job(f"cerbos-{new}-nop-{stamp}", ["-a", "nop"])
    ok &= report("Nop", rewards, 0, job)

    if args.live:
        env = dict(os.environ)
        if "OPENAI_API_KEY" not in env and (Path.home() / ".codex" / "auth.json").is_file():
            env["CODEX_FORCE_AUTH_JSON"] = "1"
        job, rewards = harbor_job(
            f"cerbos-{new}-live-{stamp}",
            ["--skill", "./skills/cerbos-policy", "-a", "codex", "--agent-kwarg", "version=0.154.0",
             "-m", "openai/gpt-5.6-luna", "-n", "4", "--agent-setup-timeout-multiplier", "4"],
            env=env,
        )
        report("Live skill run (informational)", rewards, 1, job)

    print(f"\nReview the release notes for skill updates: "
          f"https://docs.cerbos.dev/cerbos/latest/releases/v{new}.html")
    if not ok:
        sys.exit("Checks failed: see the job directories above. Files were updated; "
                 "use git diff / git checkout to review or revert.")
    print("All checks passed. Review git diff, then commit.")


if __name__ == "__main__":
    main()
