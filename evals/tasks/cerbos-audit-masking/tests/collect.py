"""Start the agent's PDP, send hidden requests, and capture the audit file it writes.

Writes /logs/verifier/calls.json (requests, responses, expected effects) and a
copy of /var/log/cerbos/audit.log. Exits non-zero when the PDP does not start
from /workspace/config.yaml or does not answer the requests as the unchanged
policies require.
"""

import json
import os
import secrets
import shutil
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

CONFIG = Path("/workspace/config.yaml")
AUDIT_LOG = Path("/var/log/cerbos/audit.log")
LOGS = Path("/logs/verifier")
TOKENS = json.loads(Path("/tests/tokens.json").read_text())
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def rand(prefix: str) -> str:
    return f"{prefix}{secrets.token_hex(6)}"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def stop_stray_pdps() -> None:
    """An agent may leave its own PDP running; it would hold the ports and the file."""
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            exe = os.readlink(proc / "exe")
        except OSError:
            continue
        if os.path.basename(exe) == "cerbos":
            try:
                os.kill(int(proc.name), signal.SIGKILL)
            except OSError:
                pass
    time.sleep(0.5)


def build_calls() -> tuple[list[dict], dict]:
    sensitive = {}

    def principal(pid, roles, department, limit):
        ssn = rand("SSN-")
        email = f"{rand('pii-')}@people.acme.test"
        sensitive[f"{pid}.ssn"] = ssn
        sensitive[f"{pid}.email"] = email
        return {
            "id": pid,
            "roles": roles,
            "attr": {
                "department": department,
                "approval_limit": limit,
                "ssn": ssn,
                "email": email,
            },
        }

    def invoice(iid, department, amount, status, owner):
        account = f"GB{secrets.randbelow(90) + 10}ACME{secrets.randbelow(10**10):010d}"
        sensitive[f"{iid}.bank_account"] = account
        return {
            "kind": "invoice",
            "id": iid,
            "attr": {
                "department": department,
                "amount": amount,
                "status": status,
                "owner": owner,
                "bank_account": account,
            },
        }

    suffix = secrets.token_hex(3)
    mgr1 = principal("hidden-mgr-1", ["manager"], "finance", 5000)
    mgr2 = principal("hidden-mgr-2", ["manager"], "finance", 5000)
    emp = principal("hidden-emp-1", ["employee"], "sales", 0)
    aud = principal("hidden-aud-1", ["auditor"], "compliance", 0)
    adm = principal("hidden-adm-1", ["admin"], "it", 0)
    inv_a = invoice(f"inv-a-{suffix}", "finance", 1200, "submitted", "hidden-emp-1")
    inv_b = invoice(f"inv-b-{suffix}", "finance", 9000, "submitted", "hidden-emp-2")
    inv_c = invoice(f"inv-c-{suffix}", "sales", 300, "approved", "hidden-emp-1")

    for name, token in TOKENS.items():
        sensitive[f"jwt.{name}.token"] = token["token"]
        for claim in ("email", "phone_number", "employee_number"):
            sensitive[f"jwt.{name}.{claim}"] = token["claims"][claim]

    A, D = "EFFECT_ALLOW", "EFFECT_DENY"

    def check(name, prin, token, resources, expected, kind_note):
        body = {
            "requestId": name,
            "principal": prin,
            "resources": [
                {"resource": res, "actions": list(expected[res["id"]])} for res in resources
            ],
        }
        if token:
            body["auxData"] = {"jwt": {"token": TOKENS[token]["token"]}}
        return {
            "name": name,
            "api": "check",
            "path": "/api/check/resources",
            "body": body,
            "expected": expected,
            "decision_expected": True,
            "note": kind_note,
        }

    def plan(name, prin, token, action, expected_kind, decision_expected):
        body = {
            "requestId": name,
            "principal": prin,
            "resource": {"kind": "invoice"},
            "action": action,
        }
        if token:
            body["auxData"] = {"jwt": {"token": TOKENS[token]["token"]}}
        return {
            "name": name,
            "api": "plan",
            "path": "/api/plan/resources",
            "body": body,
            "expected_kind": expected_kind,
            "decision_expected": decision_expected,
            "note": expected_kind,
        }

    calls = [
        check(
            "check-manager-batch",
            mgr1,
            "manager_mfa",
            [inv_a, inv_b, inv_c],
            {
                inv_a["id"]: {"view": A, "approve": A, "pay": D},
                inv_b["id"]: {"view": A, "approve": D, "pay": D},
                inv_c["id"]: {"view": D, "approve": D, "pay": D},
            },
            "mixed",
        ),
        check(
            "check-manager-no-mfa",
            mgr2,
            "manager_nomfa",
            [inv_a],
            {inv_a["id"]: {"view": A, "approve": D}},
            "mixed",
        ),
        check(
            "check-employee-allow-only",
            emp,
            None,
            [inv_c],
            {inv_c["id"]: {"view": A}},
            "allow-only",
        ),
        check(
            "check-auditor",
            aud,
            "auditor",
            [inv_a, inv_c],
            {inv_a["id"]: {"view": A, "pay": D}, inv_c["id"]: {"view": A, "pay": D}},
            "mixed",
        ),
        check(
            "check-admin-allow-only",
            adm,
            None,
            [inv_c],
            {inv_c["id"]: {"view": A, "pay": A}},
            "allow-only",
        ),
        plan("plan-auditor-view", aud, "auditor", "view", "KIND_ALWAYS_ALLOWED", False),
        plan("plan-admin-view", adm, None, "view", "KIND_ALWAYS_ALLOWED", False),
        plan("plan-manager-approve", mgr1, "manager_mfa", "approve", "KIND_CONDITIONAL", True),
        plan("plan-manager-view", mgr2, "manager_nomfa", "view", "KIND_CONDITIONAL", True),
        plan("plan-employee-approve", emp, None, "approve", "KIND_ALWAYS_DENIED", True),
    ]
    for call in calls:
        auth = rand("atk_live_")
        api_key = rand("ak_live_")
        sensitive[f"{call['name']}.authorization"] = auth
        sensitive[f"{call['name']}.x-api-key"] = api_key
        call["headers"] = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {auth}",
            "X-Api-Key": api_key,
            "X-Request-Id": rand("req-"),
            "X-Tenant-Id": rand("tenant-"),
            "X-Edge-Trace": rand("edge-"),
        }
    return calls, sensitive


def wait_ready(process, base_url: str) -> None:
    deadline = time.monotonic() + 30
    url = f"{base_url}/_cerbos/health?service=cerbos.svc.v1.CerbosService"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise SystemExit(f"PDP exited during startup with code {process.returncode}")
        try:
            with HTTP.open(url, timeout=1) as response:
                if json.load(response).get("status") == "SERVING":
                    return
        except (urllib.error.URLError, TimeoutError, ValueError, ConnectionError):
            time.sleep(0.2)
    raise SystemExit("PDP did not become ready within 30 seconds")


def send(base_url: str, call: dict) -> dict:
    request = urllib.request.Request(
        base_url + call["path"],
        data=json.dumps(call["body"]).encode(),
        headers=call["headers"],
        method="POST",
    )
    try:
        with HTTP.open(request, timeout=10) as response:
            return {"status": response.status, "body": json.load(response)}
    except urllib.error.HTTPError as error:
        return {"status": error.code, "body": error.read().decode(errors="replace")}
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        return {"status": None, "body": str(error)}


def answered_correctly(call: dict) -> bool:
    response = call["response"]
    if response["status"] != 200 or not isinstance(response["body"], dict):
        return False
    body = response["body"]
    if call["api"] == "check":
        actual = {r["resource"]["id"]: r.get("actions") for r in body.get("results", [])}
        return actual == call["expected"]
    return body.get("filter", {}).get("kind") == call["expected_kind"]


def audit_call_ids() -> set:
    ids = set()
    if not AUDIT_LOG.exists():
        return ids
    for line in AUDIT_LOG.read_text(errors="replace").splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if isinstance(entry, dict) and entry.get("callId"):
            ids.add(entry["callId"])
    return ids


def main() -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    if not CONFIG.is_file():
        raise SystemExit(f"{CONFIG} is missing")
    stop_stray_pdps()
    # Only entries written for the verifier's own requests are graded.
    AUDIT_LOG.unlink(missing_ok=True)
    calls, sensitive = build_calls()
    http_port, grpc_port = free_port(), free_port()
    base_url = f"http://127.0.0.1:{http_port}"
    failures = []
    with (LOGS / "pdp.log").open("w") as log:
        process = subprocess.Popen(
            [
                "cerbos",
                "server",
                "--config",
                str(CONFIG),
                f"--set=server.httpListenAddr=127.0.0.1:{http_port}",
                f"--set=server.grpcListenAddr=127.0.0.1:{grpc_port}",
                "--debug-listen-addr=127.0.0.1:0",
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            wait_ready(process, base_url)
            for call in calls:
                call["response"] = send(base_url, call)
                call["answered_correctly"] = answered_correctly(call)
                body = call["response"]["body"]
                call["callId"] = body.get("cerbosCallId") if isinstance(body, dict) else None
                print(f"{'PASS' if call['answered_correctly'] else 'FAIL'}: {call['name']}")
                if not call["answered_correctly"]:
                    failures.append(call["name"])
            wanted = {c["callId"] for c in calls if c.get("callId")}
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline and not wanted <= audit_call_ids():
                time.sleep(0.25)
            time.sleep(1)
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    if AUDIT_LOG.exists():
        shutil.copyfile(AUDIT_LOG, LOGS / "audit.log")
    (LOGS / "calls.json").write_text(
        json.dumps({"calls": calls, "sensitive": sensitive}, indent=2) + "\n"
    )
    if failures:
        raise SystemExit(f"PDP answered incorrectly: {', '.join(failures)}")
    print(f"PDP served {len(calls)} hidden requests from {CONFIG}")


if __name__ == "__main__":
    main()
