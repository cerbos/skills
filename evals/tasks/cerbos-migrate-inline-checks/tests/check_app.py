"""Replay the hidden request matrix against the migrated app backed by a real PDP.

Modes:
  normal  PDP loads /workspace/policies; every status code must equal the original app's.
  strict  The same with engine.strictEvaluation enabled.
  empty   PDP loads no policies; no request the original app answered with 2xx may
          still succeed, which proves every guard now asks Cerbos.
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from contract import send  # noqa: E402

POLICIES = Path("/workspace/policies")
APP = Path("/workspace/app/server.py")
LOGS = Path("/logs/verifier")
TESTS = Path(__file__).parent
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for(url, process, what, ok):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise SystemExit(f"{what} exited during startup with {process.returncode}")
        try:
            with HTTP.open(url, timeout=1) as response:
                if ok(response):
                    return
        except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError):
            pass
        time.sleep(0.2)
    raise SystemExit(f"{what} did not become ready within 30 seconds")


def stop(process):
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


@contextmanager
def pdp(mode):
    http_port, grpc_port = free_port(), free_port()
    empty = tempfile.mkdtemp(prefix="empty-policies-")
    config = {
        "server": {"httpListenAddr": f"127.0.0.1:{http_port}", "grpcListenAddr": f"127.0.0.1:{grpc_port}"},
        "storage": {
            "driver": "disk",
            "disk": {"directory": empty if mode == "empty" else str(POLICIES), "watchForChanges": False},
        },
        "engine": {"strictEvaluation": mode == "strict"},
    }
    config_path = LOGS / f"pdp-{mode}-config.json"
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    with (LOGS / f"pdp-{mode}.log").open("w") as log:
        process = subprocess.Popen(
            ["cerbos", "server", "--config", str(config_path), "--debug-listen-addr=127.0.0.1:0"],
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            wait_for(
                f"http://127.0.0.1:{http_port}/_cerbos/health?service=cerbos.svc.v1.CerbosService",
                process,
                "PDP",
                lambda r: json.load(r).get("status") == "SERVING",
            )
            yield f"127.0.0.1:{grpc_port}", f"http://127.0.0.1:{http_port}"
        finally:
            stop(process)
            shutil.rmtree(empty, ignore_errors=True)


@contextmanager
def app(mode, grpc_addr, http_url):
    port = free_port()
    data = Path(tempfile.mkdtemp(prefix="app-data-")) / "data.json"
    shutil.copy(TESTS / "hidden-data.json", data)
    env = {
        **os.environ,
        "PORT": str(port),
        "APP_DATA": str(data),
        "CERBOS_GRPC_ADDR": grpc_addr,
        "CERBOS_HTTP_ADDR": http_url,
        "NO_PROXY": "*",
        "no_proxy": "*",
    }
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
        env.pop(key, None)
    with (LOGS / f"app-{mode}.log").open("w") as log:
        process = subprocess.Popen(
            [sys.executable, str(APP)], cwd="/workspace", env=env, stdout=log, stderr=subprocess.STDOUT
        )
        try:
            wait_for(f"http://127.0.0.1:{port}/health", process, "App", lambda r: r.status == 200)
            yield f"http://127.0.0.1:{port}"
        finally:
            stop(process)
            shutil.rmtree(data.parent, ignore_errors=True)


def main():
    mode = sys.argv[1]
    LOGS.mkdir(parents=True, exist_ok=True)
    cases = json.loads((TESTS / "cases.json").read_text())
    if mode == "empty":
        # Only requests the original service allowed can show a guard that skips the PDP.
        cases = [c for c in cases if c["path"] != "/health" and 200 <= c["expected"] < 300]
    records = []
    with pdp(mode) as (grpc_addr, http_url), app(mode, grpc_addr, http_url) as base_url:
        for case in cases:
            try:
                actual = send(base_url, case)
            except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
                actual = f"error: {error}"
            if mode == "empty":
                passed = not (isinstance(actual, int) and 200 <= actual < 300)
            else:
                passed = actual == case["expected"]
            records.append({"case": case["name"], "method": case["method"], "path": case["path"],
                            "user": case["user"], "expected": case["expected"], "actual": actual,
                            "passed": passed})
    (LOGS / f"app-{mode}-results.json").write_text(json.dumps(records, indent=2) + "\n")
    failed = [r for r in records if not r["passed"]]
    for record in failed[:40]:
        want = "a refusal" if mode == "empty" else record["expected"]
        print(f"FAIL: {record['case']}: {record['method']} {record['path']} as {record['user']} "
              f"expected {want}, got {record['actual']}")
    print(f"{len(records) - len(failed)}/{len(records)} requests passed ({mode})")
    if failed:
        what = "succeeded with no policies loaded" if mode == "empty" else "differ from the original service"
        raise SystemExit(f"{len(failed)} requests {what}")


if __name__ == "__main__":
    main()
