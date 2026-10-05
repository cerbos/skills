"""Start a fresh PDP on the unchanged policies and the agent's app, replay hidden requests.

Writes /logs/verifier/replay.json and copies the PDP's own audit log to
/logs/verifier/pdp-audit.log. Exits non-zero only when the PDP or the app
cannot be started; the decision stages are graded by check.py.
"""

import json
import os
import secrets
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import jwt

sys.path.insert(0, "/tests")
from contract import build_cases  # noqa: E402

LOGS = Path("/logs/verifier")
WORK = Path("/tmp/verifier")
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))
PDP_URL = "http://127.0.0.1:3592"
APP_URL = "http://127.0.0.1:8000"


def stop_strays() -> None:
    """The agent may have left its own PDP or app running on the standard ports."""
    me = os.getpid()
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit() or int(proc.name) == me:
            continue
        try:
            exe = os.path.basename(os.readlink(proc / "exe"))
            cmdline = (proc / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
        except OSError:
            continue
        if exe == "cerbos" or ("python" in exe and "app.py" in cmdline):
            try:
                os.kill(int(proc.name), signal.SIGKILL)
            except OSError:
                pass
    time.sleep(1)


def wait(process, url: str, what: str) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise SystemExit(f"{what} exited during startup with code {process.returncode}")
        try:
            with HTTP.open(url, timeout=1) as response:
                if response.status < 500:
                    return
        except urllib.error.HTTPError as error:
            if error.code < 500:
                return
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            pass
        time.sleep(0.2)
    raise SystemExit(f"{what} did not become ready within 30 seconds")


def call(method: str, path: str, token: str) -> dict:
    request = urllib.request.Request(
        APP_URL + path,
        method=method,
        headers={"Authorization": f"Bearer {token}"},
        data=b"" if method == "POST" else None,
    )
    try:
        with HTTP.open(request, timeout=10) as response:
            raw = response.read().decode(errors="replace")
            status = response.status
    except urllib.error.HTTPError as error:
        raw = error.read().decode(errors="replace")
        status = error.code
    except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
        return {"status": None, "body": str(error)}
    try:
        body = json.loads(raw)
    except ValueError:
        body = raw
    return {"status": status, "body": body}


def main() -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    stop_strays()
    suite = build_cases()
    secret = secrets.token_hex(16)
    invoices_file = WORK / "invoices.json"
    invoices_file.write_text(json.dumps(suite["invoices"], indent=2))
    audit_log = WORK / "pdp-audit.log"
    audit_log.unlink(missing_ok=True)
    config = {
        "server": {"httpListenAddr": "127.0.0.1:3592", "grpcListenAddr": "127.0.0.1:3593"},
        "storage": {"driver": "disk", "disk": {"directory": "/workspace/policies", "watchForChanges": False}},
        "audit": {"enabled": True, "backend": "file", "file": {"path": str(audit_log)}},
    }
    config_path = LOGS / "pdp-config.json"
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    env = {
        **os.environ,
        "PORT": "8000",
        "CERBOS_URL": PDP_URL,
        "INVOICES_FILE": str(invoices_file),
        "APP_JWT_SECRET": secret,
        "PYTHONUNBUFFERED": "1",
    }
    records = []
    pdp_log = (LOGS / "pdp.log").open("w")
    app_log = (LOGS / "app.log").open("w")
    pdp = subprocess.Popen(
        ["cerbos", "server", "--config", str(config_path), "--debug-listen-addr=127.0.0.1:0"],
        stdout=pdp_log,
        stderr=subprocess.STDOUT,
    )
    app = None
    try:
        wait(pdp, f"{PDP_URL}/_cerbos/health", "PDP")
        app = subprocess.Popen(
            [sys.executable, "/workspace/app/app.py"],
            cwd="/workspace/app",
            env=env,
            stdout=app_log,
            stderr=subprocess.STDOUT,
        )
        wait(app, f"{APP_URL}/invoices/__readiness__", "App")
        for case in suite["cases"]:
            claims = {"aud": "invoices", **suite["principals"][case["principal"]]}
            token = jwt.encode(claims, secret, algorithm="HS256")
            path = f"/invoices/{case['invoice']}" + ("/approve" if case["action"] == "approve" else "")
            method = "POST" if case["action"] == "approve" else "GET"
            result = call(method, path, token)
            record = {**case, "response": result}
            records.append(record)
            ok = result["status"] == case["expected_status"]
            print(f"{'PASS' if ok else 'FAIL'}: {case['name']} -> {result['status']}")
        time.sleep(1)
    finally:
        for process in (app, pdp):
            if process is None:
                continue
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        pdp_log.close()
        app_log.close()
        if audit_log.exists():
            shutil.copyfile(audit_log, LOGS / "pdp-audit.log")
        (LOGS / "replay.json").write_text(json.dumps({"suite": suite, "records": records}, indent=2) + "\n")
    print(f"Replayed {len(records)} hidden requests through the app")


if __name__ == "__main__":
    main()
