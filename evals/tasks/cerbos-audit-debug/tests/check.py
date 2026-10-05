"""Grade the replay captured by replay.py. Usage: check.py <stage>."""

import hashlib
import json
import re
import sys
from pathlib import Path

LOGS = Path("/logs/verifier")
SEED_HASHES = Path("/tests/seed_hashes.json")
FINDINGS = Path("/workspace/FINDINGS.md")
API_KEYS = {"id", "owner", "costCenter", "amount", "status", "description"}
problems: list[str] = []


def fail(message: str) -> None:
    problems.append(message)


def load():
    path = LOGS / "replay.json"
    if not path.exists():
        raise SystemExit("No replay captured: the app stage did not complete")
    data = json.loads(path.read_text())
    if not data["records"]:
        raise SystemExit("No requests were replayed")
    invoices = {inv["id"]: inv for inv in data["suite"]["invoices"]}
    return data["records"], invoices


def stage_policies_unchanged() -> None:
    expected = json.loads(SEED_HASHES.read_text())
    root = Path("/workspace/policies")
    actual = {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }
    for name, digest in expected.items():
        if name not in actual:
            fail(f"policies/{name} is missing")
        elif actual[name] != digest:
            fail(f"policies/{name} was modified")
    for name in sorted(set(actual) - set(expected)):
        fail(f"policies/{name} was added")


def decisions_match(action: str) -> None:
    records, _ = load()
    selected = [r for r in records if r["action"] == action]
    if not selected:
        fail(f"no {action} cases replayed")
    for record in selected:
        status = record["response"]["status"]
        if status != record["expected_status"]:
            fail(f"{record['name']}: expected HTTP {record['expected_status']}, got {status}")


def stage_api_shape() -> None:
    records, invoices = load()
    shown = [r for r in records if r["response"]["status"] == 200]
    if not shown:
        fail("no successful responses to inspect")
    for record in shown:
        body = record["response"]["body"]
        invoice = invoices[record["invoice"]]
        if not isinstance(body, dict) or set(body) != API_KEYS:
            fail(f"{record['name']}: response keys changed: {sorted(body) if isinstance(body, dict) else body!r}")
            continue
        if body["id"] != invoice["id"] or body["costCenter"] != invoice["cost_center"]:
            fail(f"{record['name']}: response does not describe {invoice['id']}")
        if record["action"] == "approve" and body["status"] != "approved":
            fail(f"{record['name']}: approved invoice reports status {body['status']!r}")


def stage_pdp_consulted() -> None:
    records, invoices = load()
    path = LOGS / "pdp-audit.log"
    entries = []
    if path.exists():
        for line in path.read_text(errors="replace").splitlines():
            try:
                entries.append(json.loads(line))
            except ValueError:
                continue
    seen = {}
    for entry in entries:
        for item in (entry.get("checkResources") or {}).get("inputs") or []:
            resource = item.get("resource") or {}
            for action in item.get("actions") or []:
                seen.setdefault((resource.get("id"), action), []).append(resource.get("attr") or {})
    for record in records:
        invoice = invoices[record["invoice"]]
        attrs = seen.get((invoice["id"], record["action"]))
        if not attrs:
            fail(f"{record['name']}: the app did not ask the PDP")
            continue
        if not any(a.get("cost_center") == invoice["cost_center"] for a in attrs):
            fail(f"{record['name']}: PDP never received cost_center for {invoice['id']}")


def stage_findings() -> None:
    if not FINDINGS.is_file():
        fail("/workspace/FINDINGS.md is missing")
        return
    text = FINDINGS.read_text(errors="replace")
    if not re.search(r"cost_?center", text, re.IGNORECASE):
        fail("FINDINGS.md does not name the cost centre attribute that was mis-sent")


STAGES = {
    "policies_unchanged": stage_policies_unchanged,
    "approvals": lambda: decisions_match("approve"),
    "views": lambda: decisions_match("view"),
    "api_shape": stage_api_shape,
    "pdp_consulted": stage_pdp_consulted,
    "findings": stage_findings,
}


if __name__ == "__main__":
    STAGES[sys.argv[1]]()
    for problem in problems:
        print(f"FAIL: {problem}")
    if problems:
        raise SystemExit(f"{sys.argv[1]}: {len(problems)} problem(s)")
    print(f"PASS: {sys.argv[1]}")
