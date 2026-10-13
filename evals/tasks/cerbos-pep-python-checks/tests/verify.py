"""Run the agent's expenses API against a real PDP and score each check.

Writes /logs/verifier/<check>.log, checks.tsv and reward.json (one key per
check plus "reward", which is 1 only when every check passes).
"""

import io
import json
import re
import sys
import time
import traceback
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, "/tests")
from harness import LOGS, PDP, App  # noqa: E402

APP_DIR = Path("/workspace/app")
POLICIES = Path("/tests/policies")
SUITE = json.loads(Path("/tests/cases.json").read_text())
METHODS = {"view": ("GET", "/expenses/{}"), "approve": ("POST", "/expenses/{}/approve"), "delete": ("DELETE", "/expenses/{}")}
ALLOWED_STATUS = {"view": {200}, "approve": {200}, "delete": {200, 204}}

LOGS.mkdir(parents=True, exist_ok=True)
(LOGS / "reward.txt").unlink(missing_ok=True)
(LOGS / "reward.json").write_text('{"reward": 0}\n')
(LOGS / "checks.tsv").write_text("")
scores = {}
records = []


def check(name, fn):
    buffer = io.StringIO()
    try:
        with redirect_stdout(buffer):
            passed = bool(fn())
    except Exception:
        buffer.write(traceback.format_exc())
        passed = False
    output = buffer.getvalue() + f"{'PASS' if passed else 'FAIL'}: {name}\n"
    (LOGS / f"{name}.log").write_text(output)
    print(output, end="", flush=True)
    scores[name] = int(passed)
    with (LOGS / "checks.tsv").open("a") as log:
        log.write(f"{name}\t{scores[name]}\n")


def call(app, action, expense_id, user, timeout=10):
    method, path = METHODS[action]
    return app.call(method, path.format(expense_id), user, timeout=timeout)


def uses_sdk():
    pattern = re.compile(r"^\s*(from\s+cerbos\.sdk[\w.]*\s+import|import\s+cerbos\.sdk)", re.M)
    hits = [p for p in APP_DIR.rglob("*.py") if ".venv" not in p.parts and pattern.search(p.read_text(errors="ignore"))]
    print("Modules importing the Cerbos SDK:", [str(p) for p in hits] or "none")
    return bool(hits)


def preserved_contract(app):
    ok = True
    probes = [("no header", None, "rpt-00001", 401), ("unknown user", "h-nobody", "rpt-00001", 401), ("missing report", "h-admin", "rpt-missing", 404)]
    for label, user, expense_id, expected in probes:
        for action in METHODS:
            status, body = call(app, action, expense_id, user)
            passed = status == expected
            ok &= passed
            print(f"{'PASS' if passed else 'FAIL'}: {label} {action} -> {status} (expected {expected})")
    return ok


def decisions(app):
    failures = 0
    for case in SUITE["cases"]:
        status, body = call(app, case["action"], case["expense"], case["user"])
        expected = ALLOWED_STATUS[case["action"]] if case["allow"] else {403}
        passed = status in expected
        records.append({**case, "status": status, "passed": passed})
        if not passed:
            failures += 1
            if failures <= 40:
                print(f"FAIL: {case['user']} {case['action']} {case['expense']} -> {status}, expected {sorted(expected)}")
    print(f"{len(SUITE['cases']) - failures}/{len(SUITE['cases'])} decisions matched the contract")
    (LOGS / "decisions.json").write_text(json.dumps(records, indent=1) + "\n")
    return failures == 0 and len(records) == len(SUITE["cases"])


def denied_unchanged(app):
    """Denied approve/delete requests must leave the report as it was."""
    reports = {r["id"]: r for r in SUITE["data"]["expenses"]}
    failures = 0
    checked = 0
    for case in SUITE["cases"]:
        if case["allow"] or case["action"] == "view":
            continue
        checked += 1
        status, body = call(app, "view", case["expense"], "h-admin")
        original = reports[case["expense"]]
        passed = status == 200 and isinstance(body, dict) and body.get("status") == original["status"]
        if not passed:
            failures += 1
            if failures <= 40:
                print(f"FAIL: after denied {case['action']} by {case['user']}, admin view of {case['expense']} -> {status} {str(body)[:120]}")
    print(f"{checked - failures}/{checked} denied mutations left the report unchanged")
    return checked > 0 and failures == 0


def fail_closed(app, pdp):
    ok = True
    pdp.stop()
    for case in SUITE["outage_cases"]:
        start = time.monotonic()
        status, body = call(app, case["action"], case["expense"], case["user"], timeout=15)
        elapsed = time.monotonic() - start
        passed = status is not None and status >= 400 and status not in (401, 404)
        ok &= passed
        print(f"{'PASS' if passed else 'FAIL'}: PDP down, {case['user']} {case['action']} {case['expense']} -> {status} in {elapsed:.1f}s {str(body)[:120]}")
    pdp.start()
    # The report must be untouched once the PDP is back.
    reports = {r["id"]: r for r in SUITE["data"]["expenses"]}
    for case in SUITE["outage_cases"]:
        if case["action"] == "view":
            continue
        deadline = time.monotonic() + 20
        while True:
            status, body = call(app, "view", case["expense"], "h-admin")
            if status == 200 or time.monotonic() > deadline:
                break
            time.sleep(0.5)
        passed = status == 200 and isinstance(body, dict) and body.get("status") == reports[case["expense"]]["status"]
        ok &= passed
        print(f"{'PASS' if passed else 'FAIL'}: after outage, {case['expense']} unchanged ({status}, {str(body)[:120]})")
    return ok


def main():
    check("uses_sdk", uses_sdk)
    data_file = LOGS / "hidden-data.json"
    data_file.write_text(json.dumps(SUITE["data"]) + "\n")
    pdp = PDP(POLICIES)
    app = App(
        APP_DIR,
        {"EXPENSE_DATA": str(data_file), "CERBOS_GRPC_ADDR": pdp.grpc_addr, "CERBOS_HTTP_ADDR": pdp.http_url},
    )
    try:
        pdp.start()
        check("app_starts", lambda: app.start() or True)
        names = ["preserved_contract", "decisions", "denied_unchanged", "fail_closed"]
        if scores["app_starts"]:
            check("preserved_contract", lambda: preserved_contract(app))
            check("decisions", lambda: decisions(app))
            check("denied_unchanged", lambda: denied_unchanged(app))
            check("fail_closed", lambda: fail_closed(app, pdp))
        else:
            for name in names:
                check(name, lambda: print("App did not start; see app_starts.log and app.log") or False)
    finally:
        app.stop()
        pdp.stop()
    scores["reward"] = int(all(scores.values()))
    (LOGS / "reward.json").write_text(json.dumps(scores, indent=2) + "\n")
    raise SystemExit(0 if scores["reward"] else 1)


if __name__ == "__main__":
    main()
