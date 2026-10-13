"""Hidden users and reports and the IDs each user may view; run to regenerate cases.json.

role_allows() restates the expense_report policy in tests/policies. Cerbos
evaluates each role separately and any role's ALLOW wins; the archived DENY is
attached to the employee, manager and finance roles only.
"""

import itertools
import json
import random
from pathlib import Path

USERS = [
    {"id": "h-emp-sales", "name": "Hidden Emp", "roles": "employee", "department": "sales", "region": "emea", "review_threshold": None},
    {"id": "h-emp-idle", "name": "Hidden Idle", "roles": "employee", "department": "marketing", "region": "apac", "review_threshold": None},
    {"id": "h-mgr-sales", "name": "Hidden Mgr Sales", "roles": "manager", "department": "sales", "region": "emea", "review_threshold": None},
    {"id": "h-mgr-eng", "name": "Hidden Mgr Eng", "roles": "manager", "department": "engineering", "region": "amer", "review_threshold": None},
    {"id": "h-fin-emea", "name": "Hidden Fin EMEA", "roles": "finance", "department": "finance", "region": "emea", "review_threshold": 1000.0},
    {"id": "h-fin-amer", "name": "Hidden Fin AMER", "roles": "finance", "department": "finance", "region": "amer", "review_threshold": 0.0},
    {"id": "h-mgr-fin", "name": "Hidden Mgr+Fin", "roles": "manager,finance", "department": "engineering", "region": "emea", "review_threshold": 5000.0},
    {"id": "h-auditor", "name": "Hidden Auditor", "roles": "auditor", "department": "audit", "region": "amer", "review_threshold": None},
    {"id": "h-emp-auditor", "name": "Hidden Emp+Auditor", "roles": "employee,auditor", "department": "sales", "region": "emea", "review_threshold": None},
    {"id": "h-contractor", "name": "Hidden Contractor", "roles": "contractor", "department": "sales", "region": "emea", "review_threshold": None},
]

OWNERS = [
    ("h-emp-sales", "sales", "emea"),
    ("h-mgr-sales", "sales", "emea"),
    ("h-mgr-fin", "engineering", "emea"),
    ("h-dev", "engineering", "amer"),
    ("h-rep", "sales", "amer"),
]
STATUSES = ["draft", "submitted", "approved", "rejected"]
AMOUNTS = [200.0, 1000.0, 5000.0, 7200.5]


def role_allows(role: str, user: dict, row: dict) -> bool:
    if role in ("employee", "manager", "finance") and row["archived"]:
        return False
    if role in ("employee", "manager", "finance") and row["owner_id"] == user["id"]:
        return True
    if role == "manager":
        return row["department"] == user["department"] and row["status"] != "draft"
    if role == "finance":
        threshold = user["review_threshold"]
        return (
            row["region"] == user["region"]
            and row["status"] in ("submitted", "approved")
            and threshold is not None
            and row["amount"] >= threshold
        )
    return role == "auditor"


def viewable(user: dict, row: dict) -> bool:
    return any(role_allows(role, user, row) for role in user["roles"].split(","))


def build():
    rng = random.Random(20261005)
    shapes = list(itertools.product(OWNERS, STATUSES, AMOUNTS, (False, True)))
    ids = rng.sample(range(100, 100 + 4 * len(shapes)), len(shapes))
    rows = []
    for row_id, ((owner, department, region), status, amount, archived) in zip(ids, shapes):
        rows.append(
            {
                "id": row_id,
                "owner_id": owner,
                "department": department,
                "region": region,
                "amount": amount,
                "status": status,
                "archived": archived,
                "description": f"{status} {amount} by {owner}",
            }
        )
    expected = {
        user["id"]: sorted(row["id"] for row in rows if viewable(user, row)) for user in USERS
    }
    return {"users": USERS, "expenses": rows, "expected": expected}


if __name__ == "__main__":
    suite = build()
    target = Path(__file__).with_name("cases.json")
    target.write_text(json.dumps(suite, indent=1) + "\n")
    print(f"Wrote {target}: {len(suite['expenses'])} reports")
    for user_id, ids in suite["expected"].items():
        print(f"  {user_id}: {len(ids)} visible")
