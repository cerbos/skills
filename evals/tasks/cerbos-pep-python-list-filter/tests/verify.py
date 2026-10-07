"""Run the agent's expenses API against a real PDP and score each check.

Writes /logs/verifier/<check>.log, checks.tsv and reward.json (one key per
check plus "reward", which is 1 only when every check passes).
"""

import io
import json
import re
import sqlite3
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
STATUSES = ["draft", "submitted", "approved", "rejected"]
PAGE = 7
SCHEMA = """
CREATE TABLE users (
	id VARCHAR NOT NULL, name VARCHAR NOT NULL, roles VARCHAR NOT NULL,
	department VARCHAR NOT NULL, region VARCHAR NOT NULL, review_threshold FLOAT,
	PRIMARY KEY (id)
);
CREATE TABLE expenses (
	id INTEGER NOT NULL, owner_id VARCHAR NOT NULL, department VARCHAR NOT NULL,
	region VARCHAR NOT NULL, amount FLOAT NOT NULL, status VARCHAR NOT NULL,
	archived BOOLEAN NOT NULL, description VARCHAR NOT NULL,
	PRIMARY KEY (id)
);
CREATE INDEX ix_expenses_owner_id ON expenses (owner_id);
"""

LOGS.mkdir(parents=True, exist_ok=True)
(LOGS / "reward.txt").unlink(missing_ok=True)
(LOGS / "reward.json").write_text('{"reward": 0}\n')
(LOGS / "checks.tsv").write_text("")
scores = {}
ROWS = {row["id"]: row for row in SUITE["expenses"]}


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


def seed_database(path: Path) -> None:
    path.unlink(missing_ok=True)
    with sqlite3.connect(path) as db:
        db.executescript(SCHEMA)
        db.executemany(
            "INSERT INTO users VALUES (:id, :name, :roles, :department, :region, :review_threshold)",
            SUITE["users"],
        )
        # Insert in a shuffled ID order so physical order differs from ID order.
        db.executemany(
            "INSERT INTO expenses VALUES (:id, :owner_id, :department, :region, :amount, :status, :archived, :description)",
            SUITE["expenses"],
        )


def list_ids(app, user, **params):
    query = "&".join(f"{k}={v}" for k, v in params.items())
    status, body = app.call("GET", f"/expenses?{query}", user)
    if status != 200 or not isinstance(body, dict) or not isinstance(body.get("items"), list):
        return status, None, None, body
    return status, [item.get("id") for item in body["items"]], body.get("total"), body


def describe(ids):
    return [(i, ROWS[i]["owner_id"], ROWS[i]["status"], ROWS[i]["amount"], ROWS[i]["archived"]) if i in ROWS else i for i in ids]


def uses_sdk():
    pattern = re.compile(r"^\s*(from\s+cerbos\.sdk[\w.]*\s+import|import\s+cerbos\.sdk)", re.M)
    hits = [p for p in APP_DIR.rglob("*.py") if ".venv" not in p.parts and pattern.search(p.read_text(errors="ignore"))]
    print("Modules importing the Cerbos SDK:", [str(p) for p in hits] or "none")
    return bool(hits)


def preserved_contract(app):
    ok = True
    for label, user in (("no header", None), ("unknown user", "h-nobody")):
        status, _ = app.call("GET", "/expenses", user)
        ok &= status == 401
        print(f"{'PASS' if status == 401 else 'FAIL'}: {label} -> {status} (expected 401)")
    return ok


def list_visibility(app):
    ok = True
    for user in SUITE["users"]:
        expected = SUITE["expected"][user["id"]]
        status, ids, total, body = list_ids(app, user["id"], limit=1000)
        passed = ids == expected and total == len(expected)
        ok &= passed
        print(f"{'PASS' if passed else 'FAIL'}: {user['id']} ({user['roles']}) -> HTTP {status}, {None if ids is None else len(ids)} items, total {total}; expected {len(expected)}")
        if not passed:
            if ids is None:
                print(f"    response: {str(body)[:300]}")
            else:
                print(f"    leaked: {describe(sorted(set(ids) - set(expected)))[:10]}")
                print(f"    missing: {describe(sorted(set(expected) - set(ids)))[:10]}")
    return ok


def filters_and_paging(app):
    ok = True
    for user in SUITE["users"]:
        expected = SUITE["expected"][user["id"]]
        for status_filter in STATUSES:
            want = [i for i in expected if ROWS[i]["status"] == status_filter]
            status, ids, total, _ = list_ids(app, user["id"], status=status_filter, limit=1000)
            passed = ids == want and total == len(want)
            ok &= passed
            if not passed:
                print(f"FAIL: {user['id']} status={status_filter} -> HTTP {status}, ids {ids}, total {total}; expected {want}")
        pages, totals, offset = [], set(), 0
        while offset <= len(ROWS):
            status, ids, total, _ = list_ids(app, user["id"], limit=PAGE, offset=offset)
            if ids is None:
                pages = None
                break
            pages.extend(ids)
            totals.add(total)
            if len(ids) < PAGE:
                break
            offset += PAGE
        passed = pages == expected and totals == {len(expected)}
        ok &= passed
        print(f"{'PASS' if passed else 'FAIL'}: {user['id']} paged by {PAGE}: {None if pages is None else len(pages)} items, totals {sorted(totals, key=str)}; expected {len(expected)}")
    return ok


def fail_closed(app, pdp):
    ok = True
    pdp.stop()
    for user_id in ("h-auditor", "h-mgr-sales", "h-contractor"):
        start = time.monotonic()
        status, body = app.call("GET", "/expenses?limit=1000", user_id, timeout=15)
        elapsed = time.monotonic() - start
        passed = status is not None and status >= 400 and status not in (401, 404, 422)
        ok &= passed
        print(f"{'PASS' if passed else 'FAIL'}: PDP down, {user_id} -> {status} in {elapsed:.1f}s {str(body)[:160]}")
    return ok


def uses_query_plan(audit: Path):
    """The PDP must have been asked for a query plan for every hidden caller."""
    planned = set()
    if audit.exists():
        for line in audit.read_text().splitlines():
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            plan = entry.get("planResources")
            if plan:
                planned.add(plan.get("input", {}).get("principal", {}).get("id"))
    users = {user["id"] for user in SUITE["users"]}
    missing = sorted(users - planned)
    print(f"PlanResources requests seen for {len(users & planned)}/{len(users)} hidden users")
    if missing:
        print(f"No PlanResources request for: {missing}")
    return not missing


def main():
    check("uses_sdk", uses_sdk)
    database = LOGS / "hidden.db"
    seed_database(database)
    audit = LOGS / "pdp-audit.log"
    pdp = PDP(POLICIES, audit=audit)
    app = App(
        APP_DIR,
        {"DATABASE_URL": f"sqlite:///{database}", "CERBOS_GRPC_ADDR": pdp.grpc_addr, "CERBOS_HTTP_ADDR": pdp.http_url},
    )
    names = ["preserved_contract", "list_visibility", "filters_and_paging", "uses_query_plan", "fail_closed"]
    try:
        pdp.start()
        check("app_starts", lambda: app.start() or True)
        if scores["app_starts"]:
            check("preserved_contract", lambda: preserved_contract(app))
            check("list_visibility", lambda: list_visibility(app))
            check("filters_and_paging", lambda: filters_and_paging(app))
            pdp.stop()  # flushes the audit log
            time.sleep(0.5)
            check("uses_query_plan", lambda: uses_query_plan(audit))
            pdp.start()
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
