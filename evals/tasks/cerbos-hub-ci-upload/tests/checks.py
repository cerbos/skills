"""Checks for the Hub CI upload task.

`checks.py simulate` runs the repository's workflows for each simulated event
and writes /logs/verifier/simulation.json; every other subcommand is a check
that reads it.
"""

import json
import os
import random
import shutil
import socket
import string
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
import gha  # noqa: E402

WORKSPACE = Path("/workspace")
LOGS = Path("/logs/verifier")
SIMULATION = LOGS / "simulation.json"
SEED_APP_WORKFLOW = Path("/tests/seed/app.yaml")
STORE_ID = "S7NQ4KDZ2WXM"
INVOICE = Path("policies/resource_policies/invoice.yaml")
PROXY_VARS = {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
              "http_proxy", "https_proxy", "all_proxy", "no_proxy"}

# Hidden policy breakages, each applied to a pull request's copy of the repo.
MUTATIONS = {
    "compile_error": (
        'derivedRoles: ["account_member"]',
        'derivedRoles: ["account_owner"]',
    ),
    "test_failure": (
        'actions: ["view", "download", "refund", "void"]',
        'actions: ["view", "download", "void"]',
    ),
    "strict_only_failure": (
        "expr: has(R.attr.archived) && R.attr.archived == true",
        "expr: R.attr.archived == true",
    ),
}

EVENTS = {
    "pr": {"name": "pull_request", "action": "synchronize", "branch": "main",
           "head": "feature/invoice-rules"},
    "push_main": {"name": "push", "branch": "main"},
    "push_feature": {"name": "push", "branch": "feature/invoice-rules"},
}


class Fail(Exception):
    pass


def ensure(condition, message):
    if not condition:
        raise Fail(message)


def ident(n=12):
    return "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(n))


WRAPPER = """#!/usr/bin/env python3
import json, os, subprocess, sys
real = {real!r}
code = subprocess.call([real, *sys.argv[1:]])
entry = {{"tool": {tool!r}, "argv": sys.argv[1:], "cwd": os.getcwd(), "exit": code,
         "step": os.environ.get("GHA_EMULATOR_STEP", ""),
         "env": {{k: v for k, v in os.environ.items() if k.startswith("CERBOS_HUB_")}}}}
with open({log!r}, "a") as f:
    f.write(json.dumps(entry) + "\\n")
sys.exit(code)
"""


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def prepare_repo(root: Path, mutation: str | None) -> Path:
    repo = root / "repo"
    shutil.copytree(WORKSPACE, repo, symlinks=True)
    if mutation:
        old, new = MUTATIONS[mutation]
        path = repo / INVOICE
        text = path.read_text()
        if old not in text:
            raise Fail(f"cannot apply mutation {mutation}: {INVOICE} no longer contains {old!r}")
        path.write_text(text.replace(old, new))
    git = ["git", "-C", str(repo)]
    if not (repo / ".git").exists():
        subprocess.run(git + ["init", "-q", "-b", "main"], check=True)
    subprocess.run(git + ["add", "-A"], check=True)
    subprocess.run(git + ["-c", "user.name=ci", "-c", "user.email=ci@example.com", "commit",
                          "-q", "--allow-empty", "-m", f"simulated change ({mutation or 'none'})"],
                   check=True)
    return repo


def changed_files(mutation):
    files = [str(INVOICE)]
    return files


def simulate():
    secrets = {
        "HUB_DEPLOY_CLIENT_ID": ident(),
        "HUB_DEPLOY_CLIENT_SECRET": "deploy-" + ident(24),
        "HUB_POLICIES_CLIENT_ID": ident(),
        "HUB_POLICIES_CLIENT_SECRET": "store-" + ident(24),
        "GITHUB_TOKEN": "ghs_" + ident(30),
    }
    creds = {
        secrets["HUB_DEPLOY_CLIENT_ID"]: {"secret": secrets["HUB_DEPLOY_CLIENT_SECRET"], "kind": "deployment"},
        secrets["HUB_POLICIES_CLIENT_ID"]: {"secret": secrets["HUB_POLICIES_CLIENT_SECRET"], "kind": "store"},
    }
    runs = [("pr", None), ("pr", "compile_error"), ("pr", "test_failure"),
            ("pr", "strict_only_failure"), ("push_main", None), ("push_feature", None)]
    out = {"secrets": secrets, "runs": {}}
    text_log = []

    def log(line):
        text_log.append(line)

    for event_key, mutation in runs:
        label = f"{event_key}:{mutation or 'valid'}"
        log(f"===== {label}")
        root = Path(tempfile.mkdtemp(prefix="sim-"))
        record = {"event": event_key, "mutation": mutation}
        try:
            repo = prepare_repo(root, mutation)
            calls_log = root / "calls.jsonl"
            hub_log = root / "hub.jsonl"
            wrappers = root / "bin"
            wrappers.mkdir()
            for tool in ("cerbos", "cerbosctl"):
                path = wrappers / tool
                path.write_text(WRAPPER.format(real=f"/usr/local/bin/{tool}", tool=tool, log=str(calls_log)))
                path.chmod(0o755)
            (root / "creds.json").write_text(json.dumps(creds))
            port = free_port()
            hub = subprocess.Popen([sys.executable, "/tests/fake_hub.py", "--port", str(port),
                                    "--log", str(hub_log), "--credentials", str(root / "creds.json")])
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                try:
                    socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                    break
                except OSError:
                    time.sleep(0.1)
            home = root / "home"
            home.mkdir()
            base_env = {k: v for k, v in os.environ.items()
                        if k not in PROXY_VARS and not k.startswith(("CERBOS_", "GITHUB_"))}
            base_env.update(
                PATH=f"{wrappers}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                HOME=str(home),
                CERBOS_HUB_API_ENDPOINT=f"http://127.0.0.1:{port}",
                GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="safe.directory", GIT_CONFIG_VALUE_0="*",
            )
            event = dict(EVENTS[event_key], changed=changed_files(mutation))
            try:
                runner = gha.Runner(repo, event, base_env, secrets, {}, log)
                record["jobs"] = runner.run_workflows(gha.load_workflows(repo))
            finally:
                hub.terminate()
                hub.wait()
            record["calls"] = [json.loads(l) for l in calls_log.read_text().splitlines()] if calls_log.exists() else []
            record["hub"] = [json.loads(l) for l in hub_log.read_text().splitlines()] if hub_log.exists() else []
            policies = repo / "policies"
            record["expected_files"] = sorted(
                str(p.relative_to(policies)) for p in policies.rglob("*")
                if p.is_file() and p.suffix in (".yaml", ".yml", ".json")
                and not any(part.startswith(".") for part in p.relative_to(policies).parts)
            )
            record["repo"] = str(repo)
        except Exception as error:  # noqa: BLE001 - recorded for the checks
            record["error"] = f"{type(error).__name__}: {error}"
            log(f"[simulator] {record['error']}")
        out["runs"][label] = record
    SIMULATION.write_text(json.dumps(out, indent=2))
    (LOGS / "simulation.log").write_text("\n".join(text_log) + "\n")
    print("\n".join(text_log))


def load():
    ensure(SIMULATION.exists(), "simulation did not run")
    return json.loads(SIMULATION.read_text())


def run(sim, label):
    record = sim["runs"][label]
    ensure("error" not in record, f"{label}: {record.get('error')}")
    return record


def compile_calls(record):
    return [c for c in record["calls"] if c["tool"] == "cerbos" and c["argv"][:1] == ["compile"]]


def failed_steps_with_cerbos(record):
    """Steps that invoked `cerbos` and failed the job."""
    steps_with_cerbos = {c["step"] for c in record["calls"] if c["tool"] == "cerbos"}
    failed = []
    for job in record["jobs"]:
        for step in job["steps"]:
            marker = f"{job['workflow']}:{job['job']}#{step['index']}"
            if marker in steps_with_cerbos and step.get("exit_code") not in (0, None) \
                    and not step.get("continue_on_error"):
                failed.append(marker)
    return failed


def store_keeps(path):
    parts = path.split("/")
    return path.endswith((".yaml", ".yml", ".json")) and not any(p.startswith(".") for p in parts)


def store_writes(record):
    return [h for h in record["hub"] if h.get("rpc") in ("ReplaceFiles", "ModifyFiles")]


def describe_jobs(record):
    lines = []
    for job in record["jobs"]:
        lines.append(f"  {job['workflow']}:{job['job']} -> {job['result']}")
        for step in job["steps"]:
            if step.get("skipped"):
                continue
            lines.append(f"    step {step['index']} {step.get('name') or step.get('uses') or ''}: exit {step.get('exit_code')}")
    return "\n".join(lines) or "  (no jobs ran)"


def check_workflows_valid():
    folder = WORKSPACE / ".github" / "workflows"
    ensure(folder.is_dir(), "no .github/workflows directory")
    workflows = gha.load_workflows(WORKSPACE)
    for wf in workflows:
        ensure(wf["on"], f"{wf['file']} has no `on` trigger")
        ensure(isinstance(wf["data"].get("jobs"), dict) and wf["data"]["jobs"], f"{wf['file']} has no jobs")
    app = [wf for wf in workflows if wf["file"] == "app.yaml"]
    ensure(app, "the app workflow was removed or renamed")
    seed = yaml.safe_load(SEED_APP_WORKFLOW.read_text())
    ensure(app[0]["data"] == seed, "the app workflow was changed")
    ensure(len(workflows) > 1 or len(app[0]["data"]["jobs"]) > 1, "no policy workflow was added")
    print("workflows:", ", ".join(wf["file"] for wf in workflows))


def check_pr_passes_valid_policies():
    record = run(load(), "pr:valid")
    print(describe_jobs(record))
    calls = compile_calls(record)
    for call in calls:
        print(f"  cerbos {' '.join(call['argv'])} (cwd {call['cwd']}) -> exit {call['exit']}")
    ensure(calls, "a pull request into main never ran `cerbos compile`")
    failed = failed_steps_with_cerbos(record)
    ensure(not failed, f"the PR check fails on the valid policies: {failed}")
    print("valid policies pass the PR check")


def _check_mutation(name):
    record = run(load(), f"pr:{name}")
    print(describe_jobs(record))
    for call in compile_calls(record):
        print(f"  cerbos {' '.join(call['argv'])} -> exit {call['exit']}")
    failed = failed_steps_with_cerbos(record)
    ensure(failed, f"the PR check passed a pull request with a hidden {name.replace('_', ' ')}")
    print(f"PR check failed at {failed}")


def check_pr_catches_compile_error():
    _check_mutation("compile_error")


def check_pr_catches_test_failure():
    _check_mutation("test_failure")


def check_pr_catches_strict_only_failure():
    _check_mutation("strict_only_failure")


def check_no_upload_outside_main():
    sim = load()
    offenders = []
    for label, record in sim["runs"].items():
        if record["event"] == "push_main":
            continue
        ensure("error" not in record, f"{label}: {record.get('error')}")
        if store_writes(record):
            offenders.append(label)
    ensure(not offenders, f"the store was written to by: {offenders}")
    print("no store writes from pull requests or other branches")


def check_main_uploads_policies():
    record = run(load(), "push_main:valid")
    print(describe_jobs(record))
    for call in record["calls"]:
        if call["tool"] == "cerbosctl":
            print(f"  cerbosctl {' '.join(call['argv'])} (cwd {call['cwd']}) -> exit {call['exit']}")
    writes = [w for w in store_writes(record) if w.get("result") == "ok"]
    ensure(writes, "a push to main did not upload to the store "
           f"(hub saw: {[(h.get('rpc'), h.get('result')) for h in record['hub']]})")
    stores = {w["store_id"] for w in writes}
    ensure(stores == {STORE_ID}, f"uploads went to store(s) {sorted(stores)}, expected {STORE_ID}")
    last = writes[-1]
    ensure(last["rpc"] == "ReplaceFiles", f"final write was {last['rpc']}")
    # Hub skips files its rules reject (other extensions, dot-prefixed paths),
    # so only what it would keep has to match.
    uploaded = sorted(p for p in last["files"] if store_keeps(p))
    expected = record["expected_files"]
    shown = uploaded if len(uploaded) <= 15 else uploaded[:15] + [f"... {len(uploaded) - 15} more"]
    ensure(uploaded == expected,
           "the store would not match policies/:\n"
           f"  uploaded: {shown}\n  expected: {expected}")
    print(f"store {STORE_ID} replaced with the {len(expected)} files of policies/")


def check_main_uses_store_credential():
    sim = load()
    record = run(sim, "push_main:valid")
    secrets = sim["secrets"]
    tokens = [h for h in record["hub"] if h.get("rpc") == "IssueAccessToken"]
    ensure(tokens, "nothing authenticated to Hub on a push to main")
    for token in tokens:
        ensure(token["client_id"] == secrets["HUB_POLICIES_CLIENT_ID"]
               and token["client_secret"] == secrets["HUB_POLICIES_CLIENT_SECRET"],
               "authenticated with something other than the store credential "
               f"(client id {'deployment credential' if token['client_id'] == secrets['HUB_DEPLOY_CLIENT_ID'] else token['client_id']!r})")
    secret_values = [v for k, v in secrets.items() if "SECRET" in k]
    for label, rec in sim["runs"].items():
        for call in rec.get("calls", []):
            ensure(not any(s in arg for s in secret_values for arg in call["argv"]),
                   f"{label}: a client secret was passed on the {call['tool']} command line")
    print("uploads authenticate with the store credential from the environment")


CHECKS = {
    "simulate": simulate,
    "workflows_valid": check_workflows_valid,
    "pr_passes_valid_policies": check_pr_passes_valid_policies,
    "pr_catches_compile_error": check_pr_catches_compile_error,
    "pr_catches_test_failure": check_pr_catches_test_failure,
    "pr_catches_strict_only_failure": check_pr_catches_strict_only_failure,
    "no_upload_outside_main": check_no_upload_outside_main,
    "main_uploads_policies": check_main_uploads_policies,
    "main_uses_store_credential": check_main_uses_store_credential,
}

if __name__ == "__main__":
    try:
        CHECKS[sys.argv[1]]()
    except Fail as error:
        print(f"FAIL: {error}")
        raise SystemExit(1)
    except Exception as error:  # noqa: BLE001 - any crash is a failed check
        print(f"FAIL: {type(error).__name__}: {error}")
        raise SystemExit(1)
