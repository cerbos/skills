"""A small GitHub Actions runner emulator for the CI upload task.

It decides which workflows and jobs a simulated event triggers, evaluates `if:`
conditions and `${{ }}` expressions, and runs `run:` steps with bash the way a
Linux runner does (`bash --noprofile --norc -eo pipefail`), honouring `env`,
`working-directory`, `continue-on-error`, `GITHUB_ENV`, `GITHUB_PATH` and
`GITHUB_OUTPUT`. A few well-known actions are emulated; any other `uses:` step
is recorded and treated as a successful no-op.

Only the features a CI workflow for policy validation and upload plausibly
uses are modelled. Unsupported constructs are reported in the run log so a
failure can be traced to the emulator rather than the workflow.
"""

import fnmatch
import json
import os
import re
import shlex
import subprocess
import tempfile
from pathlib import Path

import yaml

STEP_TIMEOUT = 120


# --------------------------------------------------------------------------
# Expressions


class ExprError(Exception):
    pass


_TOKEN = re.compile(
    r"\s*(?:(?P<num>-?\d+(?:\.\d+)?)|(?P<str>'(?:[^']|'')*')|(?P<op>==|!=|<=|>=|&&|\|\||[!<>()\[\],.*])"
    r"|(?P<ident>[A-Za-z_][A-Za-z0-9_-]*))"
)


def _tokens(text):
    pos, out = 0, []
    text = text.strip()
    while pos < len(text):
        match = _TOKEN.match(text, pos)
        if not match or match.end() == pos:
            raise ExprError(f"cannot parse expression near {text[pos:]!r}")
        pos = match.end()
        kind = match.lastgroup
        out.append((kind, match.group(kind)))
    return out


def _truthy(value):
    if value is None or value is False:
        return False
    if value == 0 or value == "":
        return False
    return True


def _coerce(value):
    if isinstance(value, bool):
        return float(value)
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value) if value.strip() else 0.0
        except ValueError:
            return float("nan")
    return float("nan")


def _equal(a, b):
    if isinstance(a, str) and isinstance(b, str):
        return a.lower() == b.lower()
    if type(a) is type(b) and not isinstance(a, (int, float, bool)):
        return a == b
    if isinstance(a, (dict, list)) or isinstance(b, (dict, list)):
        return a is b
    return _coerce(a) == _coerce(b)


def _to_str(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return str(value)


class _Parser:
    def __init__(self, tokens, contexts, functions):
        self.tokens, self.pos = tokens, 0
        self.contexts, self.functions = contexts, functions

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else (None, None)

    def take(self, value=None):
        tok = self.peek()
        if value is not None and tok[1] != value:
            raise ExprError(f"expected {value!r}, got {tok[1]!r}")
        self.pos += 1
        return tok

    def parse(self):
        value = self.or_()
        if self.pos != len(self.tokens):
            raise ExprError(f"trailing tokens {self.tokens[self.pos:]}")
        return value

    def or_(self):
        left = self.and_()
        while self.peek()[1] == "||":
            self.take()
            right = self.and_()
            left = left if _truthy(left) else right
        return left

    def and_(self):
        left = self.cmp()
        while self.peek()[1] == "&&":
            self.take()
            right = self.cmp()
            left = right if _truthy(left) else left
        return left

    def cmp(self):
        left = self.unary()
        while self.peek()[1] in ("==", "!=", "<", ">", "<=", ">="):
            op = self.take()[1]
            right = self.unary()
            if op == "==":
                left = _equal(left, right)
            elif op == "!=":
                left = not _equal(left, right)
            else:
                a, b = _coerce(left), _coerce(right)
                left = {"<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b}[op]
        return left

    def unary(self):
        if self.peek()[1] == "!":
            self.take()
            return not _truthy(self.unary())
        return self.postfix()

    def postfix(self):
        value = self.primary()
        while True:
            tok = self.peek()
            if tok[1] == ".":
                self.take()
                kind, name = self.take()
                if name == "*":
                    value = list(value.values()) if isinstance(value, dict) else []
                    continue
                value = _index(value, name)
            elif tok[1] == "[":
                self.take()
                key = self.or_()
                self.take("]")
                value = _index(value, key)
            else:
                return value

    def primary(self):
        kind, text = self.take()
        if kind == "num":
            return float(text)
        if kind == "str":
            return text[1:-1].replace("''", "'")
        if text == "(":
            value = self.or_()
            self.take(")")
            return value
        if kind == "ident":
            low = text.lower()
            if low == "true":
                return True
            if low == "false":
                return False
            if low == "null":
                return None
            if self.peek()[1] == "(":
                self.take()
                args = []
                while self.peek()[1] != ")":
                    args.append(self.or_())
                    if self.peek()[1] == ",":
                        self.take()
                self.take(")")
                func = self.functions.get(low)
                if func is None:
                    raise ExprError(f"unsupported function {text}")
                return func(*args)
            return self.contexts.get(text, self.contexts.get(low))
        raise ExprError(f"unexpected token {text!r}")


def _index(value, key):
    if isinstance(value, dict):
        if isinstance(key, str):
            for k, v in value.items():
                if str(k).lower() == key.lower():
                    return v
        return value.get(key)
    if isinstance(value, list) and isinstance(key, (int, float)):
        i = int(key)
        return value[i] if 0 <= i < len(value) else None
    return None


def _contains(search, item):
    if isinstance(search, list):
        return any(_equal(x, item) for x in search)
    return _to_str(item).lower() in _to_str(search).lower()


def _format(fmt, *args):
    out = _to_str(fmt)
    for i, arg in enumerate(args):
        out = out.replace("{" + str(i) + "}", _to_str(arg))
    return out.replace("{{", "{").replace("}}", "}")


BASE_FUNCTIONS = {
    "contains": _contains,
    "startswith": lambda a, b: _to_str(a).lower().startswith(_to_str(b).lower()),
    "endswith": lambda a, b: _to_str(a).lower().endswith(_to_str(b).lower()),
    "format": _format,
    "join": lambda a, sep=",": _to_str(sep).join(_to_str(x) for x in a) if isinstance(a, list) else _to_str(a),
    "tojson": lambda a: json.dumps(a, indent=2),
    "fromjson": lambda a: json.loads(a),
    "hashfiles": lambda *a: "0" * 64,
}


def evaluate(expr, contexts, status):
    functions = dict(BASE_FUNCTIONS)
    functions.update(
        success=lambda: status == "success",
        failure=lambda: status == "failure",
        always=lambda: True,
        cancelled=lambda: False,
    )
    return _Parser(_tokens(expr), contexts, functions).parse()


_EMBED = re.compile(r"\$\{\{(.*?)\}\}", re.S)


def substitute(value, contexts, status="success"):
    if isinstance(value, dict):
        return {k: substitute(v, contexts, status) for k, v in value.items()}
    if isinstance(value, list):
        return [substitute(v, contexts, status) for v in value]
    if not isinstance(value, str):
        return value
    whole = _EMBED.fullmatch(value.strip())
    if whole and value.strip() == value:
        return evaluate(whole.group(1), contexts, status)
    return _EMBED.sub(lambda m: _to_str(evaluate(m.group(1), contexts, status)), value)


def condition(expr, contexts, status):
    """Evaluate an `if:`; returns (run?, used_status_function?)."""
    if expr is None:
        return status == "success"
    if isinstance(expr, bool):
        return expr and status == "success"
    text = str(expr).strip()
    match = _EMBED.fullmatch(text)
    if match:
        text = match.group(1).strip()
    elif "${{" in text:
        text = _to_str(substitute(text, contexts, status))
    has_status = re.search(r"\b(success|failure|always|cancelled)\s*\(", text) is not None
    if not has_status:
        text = f"success() && ({text})"
    return _truthy(evaluate(text, contexts, status))


# --------------------------------------------------------------------------
# Triggers


def _glob_regex(pattern):
    out, i = "", 0
    while i < len(pattern):
        c = pattern[i]
        if pattern.startswith("**", i):
            out += ".*"
            i += 2
            continue
        if c == "*":
            out += "[^/]*"
        elif c == "?":
            out += "."
        elif c in "+":
            out += "+"
        else:
            out += re.escape(c)
        i += 1
    return re.compile(out + r"\Z")


def _filter(patterns, value):
    """GitHub filter semantics: later patterns win, `!` negates."""
    matched = False
    for pattern in patterns:
        pattern = str(pattern)
        negate = pattern.startswith("!")
        if negate:
            pattern = pattern[1:]
        if _glob_regex(pattern).match(value):
            matched = not negate
    return matched


def _paths_ok(cfg, changed):
    if "paths" in cfg:
        return any(_filter(cfg["paths"], f) for f in changed)
    if "paths-ignore" in cfg:
        return not all(_filter(cfg["paths-ignore"], f) for f in changed)
    return True


def triggers(on, event):
    """event: {'name': 'push'|'pull_request', 'branch': ..., 'changed': [...]}."""
    if isinstance(on, str):
        on = {on: None}
    elif isinstance(on, list):
        on = {name: None for name in on}
    if not isinstance(on, dict) or event["name"] not in on:
        return False
    cfg = on[event["name"]] or {}
    if event["name"] == "pull_request":
        types = cfg.get("types")
        if types and event["action"] not in types:
            return False
    if event["name"] == "push":
        has_branch = "branches" in cfg or "branches-ignore" in cfg
        has_tag = "tags" in cfg or "tags-ignore" in cfg
        if has_tag and not has_branch:
            return False
    if "branches" in cfg and not _filter(cfg["branches"], event["branch"]):
        return False
    if "branches-ignore" in cfg and _filter(cfg["branches-ignore"], event["branch"]):
        return False
    return _paths_ok(cfg, event["changed"])


def load_workflows(repo: Path):
    workflows = []
    folder = repo / ".github" / "workflows"
    for path in sorted(list(folder.glob("*.yml")) + list(folder.glob("*.yaml"))):
        data = yaml.safe_load(path.read_text())
        if not isinstance(data, dict):
            raise ValueError(f"{path.name} is not a mapping")
        on = data.get("on", data.get(True))
        workflows.append({"file": path.name, "on": on, "data": data})
    return workflows


# --------------------------------------------------------------------------
# Running


def _read_kv_file(path: Path):
    values, lines, i = {}, path.read_text().splitlines() if path.exists() else [], 0
    while i < len(lines):
        line = lines[i]
        if "<<" in line and "=" not in line.split("<<", 1)[0]:
            key, delim = line.split("<<", 1)
            body = []
            i += 1
            while i < len(lines) and lines[i] != delim:
                body.append(lines[i])
                i += 1
            values[key] = "\n".join(body)
        elif "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
        i += 1
    return values


def _matrix(job):
    matrix = (job.get("strategy") or {}).get("matrix") or {}
    if not isinstance(matrix, dict):
        return {}
    first = {}
    for key, value in matrix.items():
        if key in ("include", "exclude"):
            continue
        if isinstance(value, list) and value:
            first[key] = value[0]
    for extra in matrix.get("include") or []:
        if isinstance(extra, dict):
            for k, v in extra.items():
                first.setdefault(k, v)
    return first


def _order(jobs):
    done, order = set(), []
    pending = dict(jobs)
    while pending:
        progressed = False
        for name, job in list(pending.items()):
            needs = job.get("needs") or []
            needs = [needs] if isinstance(needs, str) else needs
            if all(n in done for n in needs):
                order.append(name)
                done.add(name)
                del pending[name]
                progressed = True
        if not progressed:
            raise ValueError(f"cyclic or missing needs: {sorted(pending)}")
    return order


class Runner:
    def __init__(self, repo: Path, event: dict, base_env: dict, secrets: dict, variables: dict, log):
        self.repo, self.event, self.base_env = repo, event, base_env
        self.secrets, self.vars, self.log = secrets, variables, log
        self.temp = Path(tempfile.mkdtemp(prefix="runner-temp-"))
        self.steps_run = []

    def github_context(self):
        e = self.event
        sha = subprocess.run(["git", "-C", str(self.repo), "rev-parse", "HEAD"],
                             capture_output=True, text=True).stdout.strip()
        ctx = {
            "event_name": e["name"],
            "sha": sha,
            "repository": "acme/billing",
            "repository_owner": "acme",
            "workspace": str(self.repo),
            "actor": "dev",
            "run_id": "1001",
            "run_number": "7",
            "server_url": "https://github.com",
            "token": self.secrets.get("GITHUB_TOKEN", ""),
            "job": "",
        }
        if e["name"] == "pull_request":
            ctx.update(ref="refs/pull/42/merge", ref_name="42/merge", base_ref=e["branch"],
                       head_ref=e["head"], ref_type="branch")
            ctx["event"] = {"action": e["action"], "number": 42, "pull_request": {
                "number": 42, "merged": False, "draft": False,
                "base": {"ref": e["branch"], "sha": sha}, "head": {"ref": e["head"], "sha": sha}}}
        else:
            ctx.update(ref=f"refs/heads/{e['branch']}", ref_name=e["branch"], base_ref="",
                       head_ref="", ref_type="branch")
            ctx["event"] = {"ref": f"refs/heads/{e['branch']}", "before": "0" * 40, "after": sha,
                            "head_commit": {"id": sha, "message": "change"}, "forced": False}
        return ctx

    def run_workflows(self, workflows):
        results = []
        for wf in workflows:
            if not triggers(wf["on"], self.event):
                self.log(f"[{wf['file']}] not triggered by {self.event['name']} on {self.event['branch']}")
                continue
            results.extend(self.run_workflow(wf))
        return results

    def run_workflow(self, wf):
        data = wf["data"]
        jobs = data.get("jobs") or {}
        results, needs_ctx = [], {}
        github = self.github_context()
        for name in _order(jobs):
            job = jobs[name] or {}
            needs = job.get("needs") or []
            needs = [needs] if isinstance(needs, str) else needs
            status = "success" if all(needs_ctx[n]["result"] == "success" for n in needs) else "failure"
            contexts = self.contexts(github | {"job": name}, data, job, {n: needs_ctx[n] for n in needs}, {})
            try:
                run = condition(job.get("if"), contexts, status)
            except ExprError as error:
                self.log(f"[{wf['file']}:{name}] cannot evaluate if: {error}")
                run = False
            if not run:
                self.log(f"[{wf['file']}:{name}] skipped")
                needs_ctx[name] = {"result": "skipped", "outputs": {}}
                results.append({"workflow": wf["file"], "job": name, "result": "skipped", "steps": []})
                continue
            if "uses" in job:
                self.log(f"[{wf['file']}:{name}] reusable workflow {job['uses']} not emulated")
                needs_ctx[name] = {"result": "failure", "outputs": {}}
                results.append({"workflow": wf["file"], "job": name, "result": "failure", "steps": []})
                continue
            outcome = self.run_job(wf, name, job, github | {"job": name}, {n: needs_ctx[n] for n in needs})
            needs_ctx[name] = {"result": outcome["result"], "outputs": outcome["outputs"]}
            results.append({"workflow": wf["file"], "job": name, **outcome})
        return results

    def contexts(self, github, data, job, needs, steps, env=None):
        merged_env = {}
        merged_env.update({k: _to_str(v) for k, v in (data.get("env") or {}).items()})
        merged_env.update({k: _to_str(v) for k, v in (job.get("env") or {}).items()})
        if env:
            merged_env.update(env)
        return {
            "github": github,
            "secrets": self.secrets,
            "vars": self.vars,
            "env": merged_env,
            "needs": needs,
            "steps": steps,
            "matrix": _matrix(job),
            "strategy": {"fail-fast": True, "job-index": 0, "job-total": 1},
            "inputs": {},
            "job": {"status": "success"},
            "runner": {"os": "Linux", "arch": "X64", "temp": str(self.temp), "name": "self-hosted-1",
                       "tool_cache": "/opt/hostedtoolcache"},
        }

    def run_job(self, wf, name, job, github, needs):
        label = f"{wf['file']}:{name}"
        data = wf["data"]
        steps_ctx, step_results, status = {}, [], "success"
        extra_env, extra_path = {}, []
        base_ctx = self.contexts(github, data, job, needs, steps_ctx)

        def expand_env(mapping, ctx):
            return {k: _to_str(substitute(v, ctx)) for k, v in (mapping or {}).items()}

        try:
            wf_env = expand_env(data.get("env"), base_ctx)
            job_env = expand_env(job.get("env"), self.contexts(github, data, job, needs, steps_ctx, wf_env))
        except ExprError as error:
            self.log(f"[{label}] cannot evaluate env: {error}")
            return {"result": "failure", "steps": [], "outputs": {}}

        defaults = ((data.get("defaults") or {}).get("run") or {}) | ((job.get("defaults") or {}).get("run") or {})
        for index, step in enumerate(job.get("steps") or []):
            step_id = step.get("id") or f"__step{index}"
            env_now = wf_env | job_env | extra_env
            ctx = self.contexts(github, data, job, needs, steps_ctx, env_now)
            ctx["job"] = {"status": status}
            try:
                run = condition(step.get("if"), ctx, status)
                step_env = env_now | expand_env(step.get("env"), ctx)
            except ExprError as error:
                self.log(f"[{label}] step {index}: cannot evaluate: {error}")
                run, step_env = False, env_now
                status = "failure"
            if not run:
                steps_ctx[step_id] = {"outcome": "skipped", "conclusion": "skipped", "outputs": {}}
                step_results.append({"index": index, "name": step.get("name"), "skipped": True})
                continue
            ctx["env"] = step_env
            outcome, outputs, record = self.run_step(label, index, step, step_env, ctx, defaults, extra_env, extra_path)
            record["continue_on_error"] = bool(substitute(step.get("continue-on-error", False), ctx))
            step_results.append(record)
            conclusion = outcome
            if outcome == "failure" and record["continue_on_error"]:
                conclusion = "success"
            steps_ctx[step_id] = {"outcome": outcome, "conclusion": conclusion, "outputs": outputs}
            if conclusion == "failure":
                status = "failure"
        outputs = {}
        try:
            final_ctx = self.contexts(github, data, job, needs, steps_ctx, wf_env | job_env | extra_env)
            outputs = {k: _to_str(substitute(v, final_ctx)) for k, v in (job.get("outputs") or {}).items()}
        except ExprError:
            pass
        return {"result": status, "steps": step_results, "outputs": outputs}

    def run_step(self, label, index, step, env, ctx, defaults, extra_env, extra_path):
        record = {"index": index, "name": step.get("name"), "skipped": False}
        marker = f"{label}#{index}"
        if "uses" in step:
            uses = str(step["uses"])
            record["uses"] = uses
            action = uses.split("@", 1)[0].lower()
            with_ = substitute(step.get("with") or {}, ctx)
            if action == "cerbos/cerbos-compile-action":
                policy_dir = _to_str(with_.get("policyDir", "/policies"))
                argv = ["cerbos", "compile", policy_dir]
                if with_.get("testDir"):
                    argv.append(f"--tests={_to_str(with_['testDir'])}")
                script = shlex.join(argv)
                record["emulated"] = script
                return self._exec(label, index, record, script, env, ctx, defaults, step, extra_env, extra_path, marker)
            self.log(f"[{label}] step {index}: uses {uses} -> no-op")
            record["exit_code"] = 0
            return "success", {}, record
        if "run" not in step:
            self.log(f"[{label}] step {index}: neither run nor uses")
            record["exit_code"] = 0
            return "success", {}, record
        try:
            script = _to_str(substitute(str(step["run"]), ctx))
        except ExprError as error:
            self.log(f"[{label}] step {index}: cannot evaluate run: {error}")
            record["exit_code"] = 1
            return "failure", {}, record
        return self._exec(label, index, record, script, env, ctx, defaults, step, extra_env, extra_path, marker)

    def _exec(self, label, index, record, script, env, ctx, defaults, step, extra_env, extra_path, marker):
        shell = step.get("shell") or defaults.get("shell") or "bash"
        workdir = step.get("working-directory") or defaults.get("working-directory")
        cwd = self.repo
        if workdir:
            cwd = (self.repo / _to_str(substitute(workdir, ctx))).resolve()
        script_file = self.temp / f"step-{label.replace('/', '_').replace(':', '_')}-{index}.sh"
        script_file.write_text(script + "\n")
        files = {name: self.temp / f"{name.lower()}-{label.replace('/', '_').replace(':', '_')}-{index}"
                 for name in ("GITHUB_ENV", "GITHUB_PATH", "GITHUB_OUTPUT", "GITHUB_STEP_SUMMARY")}
        for f in files.values():
            f.write_text("")
        if shell == "bash":
            argv = ["bash", "--noprofile", "--norc", "-eo", "pipefail", str(script_file)]
        elif shell == "sh":
            argv = ["sh", "-e", str(script_file)]
        elif shell == "python":
            argv = ["python3", str(script_file)]
        else:
            argv = [part.replace("{0}", str(script_file)) for part in shlex.split(shell)]
            if str(script_file) not in argv:
                argv.append(str(script_file))
        proc_env = dict(self.base_env)
        proc_env.update(extra_env)
        proc_env.update(env)
        proc_env.update({k: str(v) for k, v in files.items()})
        proc_env["PATH"] = ":".join(extra_path + [self.base_env["PATH"]])
        proc_env.update(
            GITHUB_WORKSPACE=str(self.repo), GITHUB_EVENT_NAME=ctx["github"]["event_name"],
            GITHUB_REF=ctx["github"]["ref"], GITHUB_REF_NAME=ctx["github"]["ref_name"],
            GITHUB_BASE_REF=ctx["github"]["base_ref"], GITHUB_HEAD_REF=ctx["github"]["head_ref"],
            GITHUB_SHA=ctx["github"]["sha"], GITHUB_REPOSITORY=ctx["github"]["repository"],
            GITHUB_ACTIONS="true", CI="true", RUNNER_OS="Linux", RUNNER_TEMP=str(self.temp),
            GHA_EMULATOR_STEP=marker,
        )
        record["script"] = script
        record["cwd"] = str(cwd)
        try:
            result = subprocess.run(argv, cwd=cwd, env=proc_env, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, timeout=STEP_TIMEOUT)
            code, output = result.returncode, result.stdout
        except subprocess.TimeoutExpired as error:
            code = -1
            output = error.stdout.decode() if isinstance(error.stdout, bytes) else (error.stdout or "")
            output += f"\n[emulator] step timed out after {STEP_TIMEOUT}s"
        except OSError as error:
            code, output = -1, f"[emulator] {error}"
        record["exit_code"] = code
        self.log(f"[{label}] step {index} ({step.get('name') or 'run'}) exit {code} in {cwd}\n"
                 + "\n".join("    " + line for line in output.splitlines()[-40:]))
        extra_env.update(_read_kv_file(files["GITHUB_ENV"]))
        for line in files["GITHUB_PATH"].read_text().splitlines():
            if line.strip():
                extra_path.insert(0, line.strip())
        outputs = _read_kv_file(files["GITHUB_OUTPUT"])
        return ("success" if code == 0 else "failure"), outputs, record
