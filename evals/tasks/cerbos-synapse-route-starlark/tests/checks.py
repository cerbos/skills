"""Smoke checks shared by every Synapse task. Usage: checks.py <check>.

/tests/task.json names the extension kind (proxy, route, envoy) and runtime
(starlark, wasm-go, wasm-js, wasm-python); the checks adapt to both.
"""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

import yaml

WORKSPACE = Path("/workspace")
CONFIG = WORKSPACE / "config.yaml"
EXTENSIONS = WORKSPACE / "extensions"
POLICY = WORKSPACE / "policies" / "document.yaml"
LOGS = Path("/logs/verifier")
TESTS = Path("/tests")
TASK = json.loads((TESTS / "task.json").read_text())
KIND, RUNTIME = TASK["kind"], TASK["runtime"]
SKIP_DIRS = {"node_modules", "dist", ".cache", "__pycache__"}
SOURCES = {
    "starlark": ("*.star",),
    "wasm-go": ("*.go",),
    "wasm-js": ("*.ts", "*.js"),
    "wasm-python": ("*.py",),
}
# Loopback requests must not be routed through a provider/proxy configuration.
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def fail(message):
    print(f"FAIL: {message}")
    raise SystemExit(1)


def workspace_files(pattern):
    return sorted(
        p for p in EXTENSIONS.rglob(pattern)
        if not SKIP_DIRS.intersection(p.relative_to(EXTENSIONS).parts)
    )


def extension_sources():
    files = [p for pattern in SOURCES[RUNTIME] for p in workspace_files(pattern)]
    if RUNTIME == "wasm-js":
        files = [p for p in files if p.name not in {"esbuild.js"} and not p.name.endswith(".d.ts")]
    return sorted(p for p in files if not p.name.endswith("_test.star"))


def extension_urls(config):
    extensions = config.get("extensions") or {}
    if KIND == "proxy":
        entries = (extensions.get("proxyExtensions") or {}).values()
        return [str((entry or {}).get("extensionURL", "")) for entry in entries]
    if KIND == "route":
        entries = (extensions.get("routeExtensions") or {}).values()
        return [str(((entry or {}).get("extension") or {}).get("extensionURL", "")) for entry in entries]
    envoy = extensions.get("envoyExternalAuthz") or {}
    return [str((envoy.get("extension") or {}).get("extensionURL", ""))] if envoy else []


def check_files():
    if not CONFIG.is_file():
        fail(f"{CONFIG} is missing")
    sources = extension_sources()
    if not sources:
        fail(f"no {RUNTIME} extension source ({', '.join(SOURCES[RUNTIME])}) under {EXTENSIONS}")
    if not workspace_files("*_test.star"):
        fail(f"no Synapse test suite (*_test.star) under {EXTENSIONS}")
    if POLICY.read_bytes() != (TESTS / "document.yaml").read_bytes():
        fail(f"{POLICY} was modified; the task requires it unchanged")
    config = yaml.safe_load(CONFIG.read_text()) or {}
    urls = extension_urls(config)
    suffix = ".star" if RUNTIME == "starlark" else ".wasm"
    loaded = [Path(url) for url in urls if url.endswith(suffix)]
    if not loaded:
        fail(f"config.yaml loads no {suffix} {KIND} extension; extension URLs: {urls}")
    missing = [str(p) for p in loaded if not p.is_file()]
    if missing:
        fail(f"{KIND} extension files do not exist: {missing}")
    if suffix == ".wasm":
        newest = max(p.stat().st_mtime for p in sources)
        stale = [str(p) for p in loaded if p.stat().st_mtime < newest]
        if stale:
            fail(f"{stale} is older than its source; rebuild after the last source change")
    print(f"PASS: config loads {[str(p) for p in loaded]}; {len(sources)} source file(s)")


def go_module():
    modules = sorted(p.parent for p in workspace_files("go.mod"))
    if len(modules) != 1:
        fail(f"expected one Go module (go.mod) under {EXTENSIONS}, found {[str(m) for m in modules]}")
    return modules[0]


def check_build():
    module = go_module()
    result = subprocess.run(
        ["go", "build", "-buildmode=c-shared", "-o", "/tmp/verify-build.wasm", "."],
        cwd=module, env={**os.environ, "GOOS": "wasip1", "GOARCH": "wasm"},
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=80,
    )
    print(result.stdout, end="")
    if result.returncode != 0:
        fail(f"go build of {module} failed")
    print(f"PASS: {module} builds to a WASM module")


def free_address():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return f"127.0.0.1:{sock.getsockname()[1]}"


@contextmanager
def synapse_server():
    address = free_address()
    log = (LOGS / "synapse-server.log").open("w")
    process = subprocess.Popen(
        ["synapse", "server", f"--conf.path={CONFIG}",
         f"--conf.set=server.listenAddress={address}"],
        stdout=log, stderr=subprocess.STDOUT,
    )
    base_url = f"http://{address}"
    try:
        deadline = time.monotonic() + 60
        while True:
            if process.poll() is not None:
                fail(f"Synapse exited during startup with {process.returncode}; see synapse-server.log")
            try:
                with HTTP.open(f"{base_url}/_cerbos/ready", timeout=1) as response:
                    if response.status == 200:
                        break
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                pass
            if time.monotonic() > deadline:
                fail("Synapse did not become ready within 60 seconds; see synapse-server.log")
            time.sleep(0.2)
        yield base_url
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        log.close()


def check_server_starts():
    with synapse_server() as base_url:
        print(f"PASS: Synapse started from {CONFIG} and is ready at {base_url}")


def run_suites(path, log_name):
    """Run `synapse test` and return its per-suite JSON records."""
    result = subprocess.run(
        ["synapse", "test", "--output=jsonl", str(path)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120,
    )
    (LOGS / f"{log_name}.stderr.log").write_text(result.stderr)
    records = []
    for line in result.stdout.splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict) and "testCases" in record:
            record.pop("logOutput", None)
            records.append(record)
    return result.returncode, records


def check_generated_tests():
    code, records = run_suites(EXTENSIONS, "synapse-test")
    print(json.dumps(records, indent=2))
    if code != 0:
        fail(f"synapse test exited with {code}")
    if not records:
        fail("synapse test reported no suites")
    failing = [r["name"] for r in records if r.get("status") != "PASS"]
    if failing:
        fail(f"suites did not pass: {failing}")
    passed = sum(r.get("passed", 0) for r in records)
    if passed < 2:
        fail(f"expected at least 2 passing test cases (allow and deny), found {passed}")
    print(f"PASS: {len(records)} suite(s), {passed} passing test case(s)")


def proxy_decision(base_url, case):
    request = {
        "requestId": case["name"],
        "principal": {"id": case["principal"], "roles": ["employee"], "attr": case["attr"]},
        "resources": [{
            "actions": ["view"],
            "resource": {"kind": "document", "id": "doc-1", "attr": case["document"]},
        }],
    }
    http_request = urllib.request.Request(
        f"{base_url}/api/check/resources",
        data=json.dumps(request).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with HTTP.open(http_request, timeout=10) as response:
        body = json.load(response)
    return {"request": request, "response": body}, body["results"][0]["actions"]["view"], case["expected"]


def route_decision(base_url, case):
    url = f"{base_url}/ext/documents?{urllib.parse.urlencode({'id': case['document']})}"
    headers = {"X-User-Id": case["user"], "X-Tenant": case["tenant"]}
    try:
        with HTTP.open(urllib.request.Request(url, headers=headers), timeout=10) as response:
            status, raw = response.status, response.read()
    except urllib.error.HTTPError as error:
        status, raw = error.code, error.read()
    actual = {"status": status}
    if status in (200, 403):
        try:
            actual["allowed"] = json.loads(raw).get("allowed")
        except (ValueError, AttributeError):
            actual["allowed"] = f"unparseable body: {raw[:200]!r}"
    expected = {"status": case["status"]}
    if case["status"] in (200, 403):
        expected["allowed"] = case["status"] == 200
    return {"url": url, "headers": headers, "body": raw.decode(errors="replace")}, actual, expected


def envoy_decisions(cases):
    """Envoy ext_authz is gRPC; drive it through a verifier-owned `synapse test` suite."""
    lines = [
        "test_suite = struct(",
        '    name = "Verifier envoy decisions",',
        f'    synapse_config = testing.load_synapse_config("{CONFIG}"),',
        ")",
        "",
        "def check(context, user_id, tenant, path):",
        "    return context.envoy_check(struct(attributes = struct(request = struct(http = struct(",
        '        id = "verify", method = "GET", path = path,',
        '        headers = {"x-user-id": user_id, "x-tenant": tenant},',
        "    )))))",
    ]
    for case in cases:
        name = case["name"].replace("-", "_")
        allowed = case["status"] == 200
        condition = "have.status.code == 0" if allowed else \
            'have.status.code == 7 and have.denied_response.status.code in (403, "Forbidden")'
        lines += [
            "",
            f"def test_{name}(context):",
            f'    have = check(context, "{case["user"]}", "{case["tenant"]}", "/documents/{case["document"]}")',
            f'    return testing.assert({condition})',
        ]
    with tempfile.TemporaryDirectory() as tmp:
        suite = Path(tmp) / "verify_envoy_test.star"
        suite.write_text("\n".join(lines) + "\n")
        (LOGS / "verify_envoy_test.star").write_text(suite.read_text())
        code, records = run_suites(suite, "envoy-verify")
    results = {c["name"]: c["status"] for r in records for c in r.get("testCases", [])}
    return code, results


def check_decisions():
    cases = json.loads((TESTS / "cases.json").read_text())
    failures = []
    if KIND == "envoy":
        code, results = envoy_decisions(cases)
        for case in cases:
            status = results.get(case["name"].replace("-", "_"), "MISSING")
            print(f"{'PASS' if status == 'PASS' else 'FAIL'} {case['name']}: {status}")
            if status != "PASS":
                failures.append(case["name"])
    else:
        evidence = []
        decide = proxy_decision if KIND == "proxy" else route_decision
        with synapse_server() as base_url:
            for case in cases:
                try:
                    record, actual, expected = decide(base_url, case)
                except (urllib.error.URLError, TimeoutError, KeyError, IndexError, ValueError) as error:
                    record, actual, expected = {}, f"error: {error}", "a decision"
                evidence.append({"case": case["name"], **record, "expected": expected, "actual": actual})
                status = "PASS" if actual == expected else "FAIL"
                print(f"{status} {case['name']}: expected {expected}, got {actual}")
                if status == "FAIL":
                    failures.append(case["name"])
        (LOGS / "decisions.json").write_text(json.dumps(evidence, indent=2) + "\n")
    if failures:
        fail(f"{len(failures)} of {len(cases)} decisions wrong: {failures}")
    print(f"PASS: all {len(cases)} decisions match")


CHECKS = {
    "files": check_files,
    **({"build": check_build} if RUNTIME == "wasm-go" else {}),
    "server_starts": check_server_starts,
    "generated_tests": check_generated_tests,
    "decisions": check_decisions,
}

if __name__ == "__main__":
    CHECKS[sys.argv[1]]()
