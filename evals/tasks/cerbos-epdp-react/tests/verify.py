"""Deterministic checks for cerbos-epdp-react, one score and log per check.

Writes /logs/verifier/deterministic.json; tests/merge.py folds it together with
the judge's scores into reward.json.
"""

import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import time
import traceback
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path

APP = Path("/workspace/app")
BUILD = Path("/tmp/verify-app")
LOGS = Path("/logs/verifier")
TESTS = Path("/tests")
RULE_ID = "B7XK2M9QPL4R"
DEPLOYMENT_ID = "F5D3RW8KJ2HQ"
HUB_CLIENT_ID = "ZB9C4N7Y2W1Q"
HUB_CLIENT_SECRET = "hubsecret_7f3a9c2e5b1d4086a9e2c7b4f1d3e8a6"
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))

LOGS.mkdir(parents=True, exist_ok=True)
(LOGS / "reward.txt").unlink(missing_ok=True)
(LOGS / "reward.json").write_text('{"reward": 0}\n')
scores: dict[str, int] = {}
(LOGS / "checks.tsv").write_text("")


class CheckFailed(Exception):
    pass


def check(name, function):
    lines: list[str] = []
    try:
        function(lines.append)
        passed = True
    except CheckFailed as error:
        lines.append(f"FAIL: {error}")
        passed = False
    except Exception:  # noqa: BLE001 - any crash fails the check, with a trace
        lines.append(traceback.format_exc())
        passed = False
    output = "\n".join(lines) + "\n"
    (LOGS / f"{name}.log").write_text(output)
    print(f"== {name}: {'PASS' if passed else 'FAIL'}\n{output}", flush=True)
    scores[name] = int(passed)
    with (LOGS / "checks.tsv").open("a") as log:
        log.write(f"{name}\t{scores[name]}\n")


def run(command, log, cwd=BUILD, env=None, timeout=240):
    result = subprocess.run(
        command,
        cwd=cwd,
        env={**os.environ, **(env or {})},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=timeout,
        check=False,
    )
    log(f"$ {' '.join(command)} (exit {result.returncode})\n{result.stdout[-6000:]}")
    return result


def prepare_copy():
    """Copy the app without node_modules or a stale dist, and link the image's
    node_modules, so the build reflects the source as left by the agent."""
    shutil.rmtree(BUILD, ignore_errors=True)
    shutil.copytree(
        APP,
        BUILD,
        symlinks=True,
        ignore=shutil.ignore_patterns("node_modules", "dist", ".vite"),
    )
    (BUILD / "node_modules").symlink_to(APP / "node_modules")


# --- build ---------------------------------------------------------------------------


def typecheck(log):
    if run(["npx", "--no-install", "tsc", "-b", "--force"], log).returncode != 0:
        raise CheckFailed("tsc -b reported errors")


def build(log):
    scripts = json.loads((BUILD / "package.json").read_text()).get("scripts", {})
    log(f"build script: {scripts.get('build')!r}")
    if "tsc" not in scripts.get("build", ""):
        raise CheckFailed("the build script no longer type-checks with tsc")
    if run(["npm", "run", "build"], log).returncode != 0:
        raise CheckFailed("npm run build failed")
    if not (BUILD / "dist" / "index.html").is_file():
        raise CheckFailed("npm run build produced no dist/index.html")


def dist_files(suffixes):
    dist = BUILD / "dist"
    return [p for p in dist.rglob("*") if p.is_file() and p.suffix in suffixes] if dist.is_dir() else []


def wasm_bundled(log):
    resolved = subprocess.run(
        [
            "node",
            "--input-type=module",
            "-e",
            "console.log(new URL(import.meta.resolve('@cerbos/embedded-server/server.wasm')).pathname)",
        ],
        cwd=APP,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    engine = hashlib.sha256(Path(resolved).read_bytes()).hexdigest()
    log(f"engine {resolved} sha256 {engine}")
    emitted = [p for p in dist_files({".wasm"}) if hashlib.sha256(p.read_bytes()).hexdigest() == engine]
    if not emitted:
        raise CheckFailed("dist/ holds no copy of @cerbos/embedded-server's server.wasm")
    scripts = [p.read_text(errors="replace") for p in dist_files({".js", ".mjs"})]
    referenced = [p.name for p in emitted if any(p.name in s for s in scripts)]
    log(f"emitted: {[str(p.relative_to(BUILD)) for p in emitted]}; referenced by JS: {referenced}")
    if not referenced:
        raise CheckFailed("the emitted server.wasm is not referenced by any bundled script")


def epdp_rule(log):
    scripts = "\n".join(p.read_text(errors="replace") for p in dist_files({".js", ".mjs"}))
    if RULE_ID not in scripts:
        raise CheckFailed(f"the bundled scripts do not contain the ePDP rule ID {RULE_ID}")
    if DEPLOYMENT_ID in scripts:
        raise CheckFailed(f"the bundled scripts contain the deployment ID {DEPLOYMENT_ID}; the ePDP needs the rule ID")
    if "@cerbos/embedded-client" not in "\n".join(
        p.read_text(errors="replace") for p in (BUILD / "src").rglob("*") if p.is_file()
    ):
        raise CheckFailed("src/ does not import @cerbos/embedded-client")
    log(f"rule ID {RULE_ID} found in the bundle; deployment ID absent")


def no_secrets_in_bundle(log):
    candidates = [p for p in (BUILD / "dist").rglob("*") if p.is_file() and p.suffix != ".wasm"]
    candidates += [p for p in (BUILD / "src").rglob("*") if p.is_file()]
    candidates += [BUILD / name for name in ("index.html", "vite.config.ts", "vite.config.js") if (BUILD / name).is_file()]
    candidates += [p for p in BUILD.iterdir() if p.is_file() and p.name.startswith(".env")]
    leaks = []
    for path in candidates:
        text = path.read_text(errors="replace")
        for secret in (HUB_CLIENT_ID, HUB_CLIENT_SECRET):
            if secret in text:
                leaks.append(f"{path.relative_to(BUILD)} contains {secret[:6]}...")
        if path.name.startswith(".env") or path.parent.name == "src":
            for match in re.finditer(r"VITE_[A-Z0-9_]*(SECRET|CLIENT_ID|CREDENTIAL)[A-Z0-9_]*", text):
                leaks.append(f"{path.relative_to(BUILD)} exposes {match.group(0)} to the browser")
    log(f"scanned {len(candidates)} files")
    if leaks:
        raise CheckFailed("; ".join(sorted(set(leaks))))


def dependencies_declared(log):
    package = json.loads((BUILD / "package.json").read_text())
    declared = {**package.get("dependencies", {}), **package.get("devDependencies", {})}
    imported = set()
    for path in (BUILD / "src").rglob("*"):
        if path.is_file() and path.suffix in {".ts", ".tsx", ".js", ".jsx", ".mts"}:
            for match in re.finditer(r"""(?:from|import)\s*\(?\s*["'](@cerbos/[a-z-]+)""", path.read_text()):
                imported.add(match.group(1))
    log(f"@cerbos packages imported by src/: {sorted(imported)}")
    missing = sorted(imported - set(declared))
    if missing:
        raise CheckFailed(f"imported but not declared in package.json: {missing}")


# --- API enforcement -----------------------------------------------------------------


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for(url, process, what, ok=lambda status, body: status < 500):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise CheckFailed(f"{what} exited during startup ({process.returncode})")
        try:
            with HTTP.open(url, timeout=1) as response:
                if ok(response.status, response.read()):
                    return
        except urllib.error.HTTPError as error:
            if ok(error.code, b""):
                return
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(0.2)
    raise CheckFailed(f"{what} did not become ready within 30 seconds")


def stop(process):
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


@contextmanager
def service_pdp(policies: Path, name: str):
    http, grpc = free_port(), free_port()
    config = {
        "server": {"httpListenAddr": f"127.0.0.1:{http}", "grpcListenAddr": f"127.0.0.1:{grpc}"},
        "storage": {"driver": "disk", "disk": {"directory": str(policies), "watchForChanges": False}},
    }
    path = LOGS / f"pdp-{name}.json"
    path.write_text(json.dumps(config, indent=2))
    with (LOGS / f"pdp-{name}.log").open("a") as out:
        process = subprocess.Popen(
            ["cerbos", "server", "--config", str(path), "--debug-listen-addr=127.0.0.1:0"],
            stdout=out,
            stderr=subprocess.STDOUT,
        )
        try:
            wait_for(
                f"http://127.0.0.1:{http}/_cerbos/health?service=cerbos.svc.v1.CerbosService",
                process,
                "PDP",
                ok=lambda status, body: status == 200 and b"SERVING" in body,
            )
            yield f"http://127.0.0.1:{http}"
        finally:
            stop(process)


@contextmanager
def api_server(cerbos_url: str, name: str):
    port = free_port()
    with (LOGS / f"api-{name}.log").open("a") as out:
        process = subprocess.Popen(
            ["npm", "run", "--silent", "server"],
            cwd=APP,
            env={**os.environ, "PORT": str(port), "CERBOS_URL": cerbos_url, "NODE_ENV": "production"},
            stdout=out,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            wait_for(f"http://127.0.0.1:{port}/api/users", process, "npm run server")
            yield f"http://127.0.0.1:{port}"
        finally:
            try:
                os.killpg(process.pid, 15)
            except ProcessLookupError:
                pass
            stop(process)


def call(base, method, path, user=None, body=None):
    headers = {"Content-Type": "application/json"}
    if user:
        headers["X-User-Id"] = user
    request = urllib.request.Request(
        base + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers=headers,
        method=method,
    )
    try:
        with HTTP.open(request, timeout=10) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as error:
        return error.code, None


def run_cases(base, cases, log):
    """Each case names a document by (owner, status); the verifier finds its ID
    through the API as the admin so it does not depend on seed IDs."""
    status, documents = call(base, "GET", "/api/documents", "carol")
    if status != 200 or not isinstance(documents, list):
        raise CheckFailed(f"GET /api/documents as carol returned {status}")
    failures = []
    for user, method, owner, doc_status, expected in cases:
        doc = next((d for d in documents if d.get("owner") == owner and d.get("status") == doc_status), None)
        if doc is None:
            raise CheckFailed(f"no {doc_status} document owned by {owner} in the API's data")
        body = {"title": f"renamed by {user}"} if method == "PUT" else None
        got, _ = call(base, method, f"/api/documents/{doc['id']}", user, body)
        allowed = 200 <= got < 300
        ok = allowed == (expected == "allow") and (allowed or got == 403)
        log(f"{'PASS' if ok else 'FAIL'}: {user} {method} {owner}'s {doc_status} {doc['id']} -> {got} (want {expected})")
        if not ok:
            failures.append(f"{user} {method} {doc['id']}")
        if allowed and method == "DELETE":
            documents = [d for d in documents if d["id"] != doc["id"]]
    unauthenticated, _ = call(base, "DELETE", f"/api/documents/{documents[0]['id']}")
    log(f"{'PASS' if unauthenticated in (401, 403) else 'FAIL'}: unauthenticated DELETE -> {unauthenticated}")
    if unauthenticated not in (401, 403):
        failures.append("unauthenticated DELETE")
    return failures


# The shipped policy: members edit their own documents and delete their own
# drafts; admins edit and delete anything.
SHIPPED_CASES = [
    ("alice", "PUT", "bob", "published", "deny"),
    ("bob", "DELETE", "alice", "draft", "deny"),
    ("alice", "DELETE", "alice", "published", "deny"),
    ("alice", "PUT", "alice", "published", "allow"),
    ("alice", "DELETE", "alice", "draft", "allow"),
    ("carol", "DELETE", "bob", "published", "allow"),
]

# A verifier-only policy change: members may edit any document in their own
# department, and only admins delete. The API must follow the PDP, not code.
CHANGED_CASES = [
    ("alice", "PUT", "carol", "published", "allow"),
    ("alice", "PUT", "bob", "published", "deny"),
    ("bob", "DELETE", "bob", "draft", "deny"),
    ("carol", "DELETE", "bob", "draft", "allow"),
]


def api_enforcement(log):
    failures = []
    for name, policies, cases in (
        ("shipped", TESTS / "policies" / "shipped", SHIPPED_CASES),
        ("changed", TESTS / "policies" / "changed", CHANGED_CASES),
    ):
        log(f"-- policy set: {name}")
        with service_pdp(policies, name) as pdp, api_server(pdp, name) as api:
            failures += [f"{name}: {f}" for f in run_cases(api, cases, log)]
    if failures:
        raise CheckFailed(", ".join(failures))


CHECKS = [
    "typecheck",
    "build",
    "wasm_bundled",
    "epdp_rule",
    "no_secrets_in_bundle",
    "dependencies_declared",
    "api_enforcement",
]


def main():
    (LOGS / "deterministic.json").write_text(json.dumps(dict.fromkeys(CHECKS, 0), indent=2) + "\n")
    try:
        prepare_copy()
    except Exception:  # noqa: BLE001
        (LOGS / "prepare.log").write_text(traceback.format_exc())
    for name in CHECKS:
        check(name, globals()[name])
    (LOGS / "deterministic.json").write_text(json.dumps(scores, indent=2) + "\n")


if __name__ == "__main__":
    main()
