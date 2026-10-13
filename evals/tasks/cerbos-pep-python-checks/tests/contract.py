"""Hidden users, expense reports and expected decisions; run to regenerate cases.json.

decide() restates the expense_report policy in tests/policies as plain Python.
Every case gets its own copy of a report so approve/delete side effects never
leak between cases.
"""

import itertools
import json
from pathlib import Path

ACTIONS = ["view", "approve", "delete"]

USERS = [
    {"id": "h-emp-sales", "name": "Hidden Emp Sales", "roles": ["employee"], "department": "sales", "region": "emea"},
    {"id": "h-emp-eng", "name": "Hidden Emp Eng", "roles": ["employee"], "department": "engineering", "region": "amer"},
    {"id": "h-mgr-sales", "name": "Hidden Mgr Sales", "roles": ["manager"], "department": "sales", "region": "emea", "approval_limit": 1500},
    {"id": "h-mgr-eng", "name": "Hidden Mgr Eng", "roles": ["manager"], "department": "engineering", "region": "amer", "approval_limit": 500},
    {"id": "h-fin-amer", "name": "Hidden Fin Amer", "roles": ["finance"], "department": "finance", "region": "amer"},
    {"id": "h-emp-fin", "name": "Hidden Emp+Fin", "roles": ["employee", "finance"], "department": "sales", "region": "emea"},
    {"id": "h-admin", "name": "Hidden Admin", "roles": ["admin"], "department": "it", "region": "amer"},
    {"id": "h-contractor", "name": "Hidden Contractor", "roles": ["contractor"], "department": "sales", "region": "emea"},
]

OWNERS = [
    ("h-emp-sales", "sales", "emea"),
    ("h-emp-eng", "engineering", "amer"),
    ("h-mgr-sales", "sales", "emea"),
    ("h-emp-fin", "sales", "emea"),
    ("h-departed", "engineering", "emea"),
]
STATUSES = ["draft", "submitted", "approved"]
AMOUNTS = [500.0, 1500.0, 2000.5]


def decide(user: dict, report: dict, action: str) -> bool:
    roles = set(user["roles"])
    owner = report["employee_id"] == user["id"] and bool(roles & {"employee", "manager", "finance"})
    dept_manager = (
        "manager" in roles
        and report["department"] == user["department"]
        and report["employee_id"] != user["id"]
    )
    finance = "finance" in roles
    submitted = report["status"] == "submitted"
    if action == "view":
        return owner or dept_manager or (finance and report["region"] == user["region"]) or "admin" in roles
    if action == "approve":
        limit = user.get("approval_limit")
        return (dept_manager and submitted and limit is not None and report["amount"] <= limit) or (
            finance and submitted and report["region"] == user["region"] and report["employee_id"] != user["id"]
        )
    if action == "delete":
        return (owner and report["status"] == "draft") or "admin" in roles
    raise ValueError(action)


def build():
    expenses, cases = [], []
    serial = itertools.count(1)
    bases = list(itertools.product(OWNERS, STATUSES, AMOUNTS))
    for user in USERS:
        for (owner, department, region), status, amount in bases:
            for action in ACTIONS:
                report = {
                    "id": f"rpt-{next(serial):05d}",
                    "employee_id": owner,
                    "department": department,
                    "region": region,
                    "amount": amount,
                    "status": status,
                    "description": f"{status} {amount} filed by {owner}",
                }
                expenses.append(report)
                cases.append(
                    {"user": user["id"], "action": action, "expense": report["id"], "allow": decide(user, report, action)}
                )
    # Reports reserved for the PDP-outage check: each pairing is allowed by policy.
    outage = [
        ("h-emp-sales", "view", {"employee_id": "h-emp-sales", "department": "sales", "region": "emea", "amount": 90.0, "status": "submitted"}),
        ("h-mgr-sales", "approve", {"employee_id": "h-emp-sales", "department": "sales", "region": "emea", "amount": 300.0, "status": "submitted"}),
        ("h-emp-sales", "delete", {"employee_id": "h-emp-sales", "department": "sales", "region": "emea", "amount": 45.0, "status": "draft"}),
    ]
    outage_cases = []
    for user_id, action, attrs in outage:
        report = {"id": f"rpt-{next(serial):05d}", **attrs, "description": "outage probe"}
        user = next(u for u in USERS if u["id"] == user_id)
        assert decide(user, report, action), (user_id, action)
        expenses.append(report)
        outage_cases.append({"user": user_id, "action": action, "expense": report["id"], "allow": True})
    return {"users": USERS, "expenses": expenses}, cases, outage_cases


if __name__ == "__main__":
    data, cases, outage_cases = build()
    target = Path(__file__).with_name("cases.json")
    target.write_text(json.dumps({"data": data, "cases": cases, "outage_cases": outage_cases}, indent=1) + "\n")
    allowed = sum(c["allow"] for c in cases)
    print(f"Wrote {target}: {len(cases)} cases, {allowed} allowed")
