"""Hidden principals, invoices and expected app responses, modelled on the unchanged policy."""

import secrets

PRINCIPALS = {
    "mgr_wide": {
        "sub": "hv-mgr-okoro",
        "roles": ["manager"],
        "department": "Operations",
        "managed_cost_centers": ["CC-410", "CC-420"],
        "approval_limit": 8000,
    },
    "mgr_narrow": {
        "sub": "hv-mgr-lindqvist",
        "roles": ["manager"],
        "department": "Facilities",
        "managed_cost_centers": ["CC-430"],
        "approval_limit": 1500,
    },
    "employee": {"sub": "hv-emp-tanaka", "roles": ["employee"], "department": "Operations"},
    "finance_admin": {"sub": "hv-fin-adeyemi", "roles": ["finance_admin"], "department": "Finance"},
}


def approve_allowed(principal: dict, invoice: dict) -> bool:
    return (
        "manager" in principal["roles"]
        and invoice["status"] == "submitted"
        and invoice["cost_center"] in principal.get("managed_cost_centers", [])
        and invoice["amount"] <= principal.get("approval_limit", 0)
        and invoice["owner"] != principal["sub"]
    )


def view_allowed(principal: dict, invoice: dict) -> bool:
    roles = set(principal["roles"])
    return bool(roles & {"manager", "finance_admin"}) or (
        "employee" in roles and invoice["owner"] == principal["sub"]
    )


def build_cases() -> dict:
    tag = secrets.token_hex(3)
    emp = PRINCIPALS["employee"]["sub"]
    wide = PRINCIPALS["mgr_wide"]["sub"]
    approvals = [
        ("mgr_wide", "CC-410", 7999.99, "submitted", emp, "within limit, managed centre"),
        ("mgr_wide", "CC-420", 8000, "submitted", emp, "exactly at limit"),
        ("mgr_wide", "CC-420", 8000.01, "submitted", emp, "over limit"),
        ("mgr_wide", "CC-430", 120, "submitted", emp, "centre not managed"),
        ("mgr_wide", "CC-410", 120, "draft", emp, "not submitted"),
        ("mgr_wide", "CC-410", 120, "approved", emp, "already approved"),
        ("mgr_wide", "CC-410", 120, "submitted", wide, "own invoice"),
        ("mgr_narrow", "CC-430", 1500, "submitted", emp, "narrow manager at limit"),
        ("mgr_narrow", "CC-430", 99.5, "submitted", wide, "narrow manager, another manager's invoice"),
        ("mgr_narrow", "CC-410", 99.5, "submitted", emp, "narrow manager, centre not managed"),
        ("employee", "CC-410", 99.5, "submitted", emp, "employee cannot approve"),
        ("finance_admin", "CC-410", 99.5, "submitted", emp, "finance admin cannot approve"),
    ]
    views = [
        ("employee", "CC-420", 300, "submitted", emp, "employee views own"),
        ("employee", "CC-420", 300, "submitted", wide, "employee views another's"),
        ("mgr_narrow", "CC-410", 300, "submitted", emp, "manager views outside centre"),
        ("finance_admin", "CC-430", 300, "approved", wide, "finance admin views"),
    ]
    invoices, cases = [], []
    for action, rows in (("approve", approvals), ("view", views)):
        for index, (who, centre, amount, status, owner, label) in enumerate(rows):
            invoice = {
                "id": f"HV-{tag}-{action[:2].upper()}{index:02d}",
                "owner": owner,
                "cost_center": centre,
                "amount": amount,
                "status": status,
                "description": f"Hidden case: {label}",
            }
            invoices.append(invoice)
            principal = PRINCIPALS[who]
            allowed = (approve_allowed if action == "approve" else view_allowed)(principal, invoice)
            cases.append(
                {
                    "name": f"{action}: {label}",
                    "principal": who,
                    "invoice": invoice["id"],
                    "action": action,
                    "expected_status": 200 if allowed else 403,
                }
            )
    return {"principals": PRINCIPALS, "invoices": invoices, "cases": cases}
