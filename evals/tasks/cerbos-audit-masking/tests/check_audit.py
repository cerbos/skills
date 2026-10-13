"""Grade the audit file captured by collect.py. Usage: check_audit.py <stage>."""

import hashlib
import json
import sys
from pathlib import Path

LOGS = Path("/logs/verifier")
SEED_HASHES = Path("/tests/seed_hashes.json")
CHECK_METHOD = "/cerbos.svc.v1.CerbosService/CheckResources"
PLAN_METHOD = "/cerbos.svc.v1.CerbosService/PlanResources"
KEPT_HEADERS = ("x-request-id", "x-tenant-id", "x-edge-trace")
DROPPED_HEADERS = ("authorization", "x-api-key")
problems: list[str] = []


def fail(message: str) -> None:
    problems.append(message)


def load():
    calls_path, audit_path = LOGS / "calls.json", LOGS / "audit.log"
    if not calls_path.exists():
        raise SystemExit("No captured calls: the PDP stage did not complete")
    data = json.loads(calls_path.read_text())
    if not audit_path.exists():
        raise SystemExit("/var/log/cerbos/audit.log was not written")
    raw = audit_path.read_text(errors="replace")
    entries = []
    for number, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            raise SystemExit(f"audit.log line {number} is not JSON")
        entries.append(entry)
    if not entries:
        raise SystemExit("/var/log/cerbos/audit.log has no entries")
    return data["calls"], data["sensitive"], raw, entries


def kind(entry: dict) -> str | None:
    if "checkResources" in entry or "planResources" in entry:
        return "decision"
    if "method" in entry:
        return "access"
    return entry.get("log.kind")


def by_call(entries, call_id, wanted_kind):
    return [e for e in entries if e.get("callId") == call_id and kind(e) == wanted_kind]


def walk(value, path=""):
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk(child, f"{path}.{key}" if path else key)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, f"{path}[{index}]")


def stage_policies_unchanged() -> None:
    expected = json.loads(SEED_HASHES.read_text())
    for name, digest in expected.items():
        path = Path("/workspace") / name
        if not path.is_file():
            fail(f"{name} is missing")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            fail(f"{name} was modified")
    policy_files = sorted(
        str(p.relative_to("/workspace"))
        for p in Path("/workspace/policies").rglob("*")
        if p.is_file()
    )
    extra = [p for p in policy_files if p not in expected]
    if extra:
        fail(f"unexpected files in /workspace/policies: {extra}")


def stage_entries_recorded() -> None:
    calls, _, _, entries = load()
    for call in calls:
        cid = call.get("callId")
        if not cid:
            fail(f"{call['name']}: PDP returned no call ID")
            continue
        access = by_call(entries, cid, "access")
        method = CHECK_METHOD if call["api"] == "check" else PLAN_METHOD
        if len(access) != 1 or access[0].get("method") != method:
            fail(f"{call['name']}: expected one access entry for {method}, found {len(access)}")
        if call["decision_expected"] and call["note"] in ("mixed", "KIND_CONDITIONAL"):
            decisions = by_call(entries, cid, "decision")
            section = "checkResources" if call["api"] == "check" else "planResources"
            if len(decisions) != 1 or section not in decisions[0]:
                fail(f"{call['name']}: expected one {section} decision entry, found {len(decisions)}")


def stage_decision_filters() -> None:
    calls, _, _, entries = load()
    for call in calls:
        cid = call.get("callId")
        if not cid:
            fail(f"{call['name']}: PDP returned no call ID")
            continue
        decisions = by_call(entries, cid, "decision")
        if call["decision_expected"] and len(decisions) != 1:
            fail(f"{call['name']} ({call['note']}): decision entry missing")
        if not call["decision_expected"] and decisions:
            fail(f"{call['name']} ({call['note']}): noise plan decision was recorded")
        if not call["decision_expected"] and not by_call(entries, cid, "access"):
            fail(f"{call['name']}: the API call itself must still be recorded")


def stage_sensitive_removed() -> None:
    calls, sensitive, raw, entries = load()
    # Only meaningful if the entries that carried the data were actually written.
    carriers = [c for c in calls if c["name"] in ("check-manager-batch", "plan-manager-approve")]
    for call in carriers:
        if not call.get("callId") or not by_call(entries, call["callId"], "decision"):
            fail(f"{call['name']}: decision entry missing, so masking cannot be confirmed")
    for label, value in sensitive.items():
        if value in raw:
            fail(f"sensitive value {label} appears in the audit log")
    for index, entry in enumerate(entries):
        for path, value in walk(entry):
            leaf = path.rsplit(".", 1)[-1]
            if leaf in ("ssn", "email", "bank_account") and ".attr." in f".{path}":
                fail(f"entry {index}: attribute {path} is present")
            if leaf == "auxData" and value:
                fail(f"entry {index}: identity token claims present at {path}")
        metadata = entry.get("metadata") or {}
        for header in DROPPED_HEADERS:
            if any(key.lower() == header for key in metadata):
                fail(f"entry {index}: header {header} recorded")


def stage_investigation_fields() -> None:
    calls, _, _, entries = load()
    for call in calls:
        cid = call.get("callId")
        if not cid:
            fail(f"{call['name']}: PDP returned no call ID")
            continue
        recorded = by_call(entries, cid, "access") + by_call(entries, cid, "decision")
        if not recorded:
            fail(f"{call['name']}: nothing recorded")
        for entry in recorded:
            metadata = {k.lower(): v for k, v in (entry.get("metadata") or {}).items()}
            for header in KEPT_HEADERS:
                values = (metadata.get(header) or {}).get("values") or []
                sent = {k.lower(): v for k, v in call["headers"].items()}[header]
                if sent not in values:
                    fail(f"{call['name']} {kind(entry)} entry: header {header} not recorded")
        decisions = by_call(entries, cid, "decision")
        if not decisions:
            continue
        decision = decisions[0]
        body = call["body"]
        principal = body["principal"]
        if call["api"] == "check":
            section = decision.get("checkResources") or {}
            inputs = section.get("inputs") or []
            outputs = section.get("outputs") or []
            if len(inputs) != len(body["resources"]):
                fail(f"{call['name']}: expected {len(body['resources'])} inputs, found {len(inputs)}")
                continue
            for item, sent in zip(inputs, body["resources"]):
                check_principal(call["name"], item.get("principal") or {}, principal)
                resource = item.get("resource") or {}
                want = sent["resource"]
                if resource.get("kind") != want["kind"] or resource.get("id") != want["id"]:
                    fail(f"{call['name']}: resource kind/id not recorded for {want['id']}")
                attr = resource.get("attr") or {}
                for key in ("amount", "department", "status", "owner"):
                    if attr.get(key) != want["attr"][key]:
                        fail(f"{call['name']}: resource attribute {key} missing for {want['id']}")
            effects = {}
            for output in outputs:
                effects[output.get("resourceId")] = {
                    action: (detail or {}).get("effect")
                    for action, detail in (output.get("actions") or {}).items()
                }
            if effects != call["expected"]:
                fail(f"{call['name']}: per-action effects not recorded as decided")
        else:
            section = decision.get("planResources") or {}
            check_principal(call["name"], (section.get("input") or {}).get("principal") or {}, principal)
            output = section.get("output") or {}
            if (output.get("filter") or {}).get("kind") != call["expected_kind"]:
                fail(f"{call['name']}: plan filter kind not recorded")
            if (section.get("input") or {}).get("action") != body["action"]:
                fail(f"{call['name']}: plan action not recorded")


def check_principal(name: str, recorded: dict, sent: dict) -> None:
    if recorded.get("id") != sent["id"] or recorded.get("roles") != sent["roles"]:
        fail(f"{name}: principal ID or roles not recorded")
    attr = recorded.get("attr") or {}
    for key in ("department", "approval_limit"):
        if attr.get(key) != sent["attr"][key]:
            fail(f"{name}: principal attribute {key} not recorded")


STAGES = {
    "policies_unchanged": stage_policies_unchanged,
    "entries_recorded": stage_entries_recorded,
    "decision_filters": stage_decision_filters,
    "sensitive_removed": stage_sensitive_removed,
    "investigation_fields": stage_investigation_fields,
}


if __name__ == "__main__":
    STAGES[sys.argv[1]]()
    for problem in problems:
        print(f"FAIL: {problem}")
    if problems:
        raise SystemExit(f"{sys.argv[1]}: {len(problems)} problem(s)")
    print(f"PASS: {sys.argv[1]}")
