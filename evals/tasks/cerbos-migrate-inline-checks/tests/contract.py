"""Model of the ORIGINAL invoice service's status codes.

Run as a script to regenerate hidden-data.json and cases.json. Run with
`--check-original URL` against the seed app (started with
APP_DATA=hidden-data.json) to confirm the model matches the real seed code.
"""

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
WRITERS = {"manager", "accountant", "admin"}
VIEWERS = {"manager", "accountant", "viewer"}
APPROVERS = {"manager", "admin"}
EXPORT_PLANS = {"pro", "enterprise"}
APPROVAL_LIMIT = 10000

TENANTS = {
    "t-north": {"name": "North", "plan": "pro"},
    "t-south": {"name": "South", "plan": "free"},
    "t-east": {"name": "East", "plan": "enterprise"},
}

# Requesting users. A user with status None has no status key at all.
USERS = {
    "n-admin": ("admin", "t-north", "active"),
    "n-manager": ("manager", "t-north", "active"),
    "n-accountant": ("accountant", "t-north", "active"),
    "n-viewer": ("viewer", "t-north", "active"),
    "n-auditor": ("auditor", "t-north", "active"),
    "n-bot": ("accountant", "t-north", None),
    "n-admin-susp": ("admin", "t-north", "suspended"),
    "n-manager-susp": ("manager", "t-north", "suspended"),
    "n-viewer-susp": ("viewer", "t-north", "suspended"),
    "n-auditor-susp": ("auditor", "t-north", "suspended"),
    "n-manager-pending": ("manager", "t-north", "pending"),
    "s-admin": ("admin", "t-south", "active"),
    "s-manager": ("manager", "t-south", "active"),
    "s-accountant": ("accountant", "t-south", "active"),
    "s-auditor": ("auditor", "t-south", "active"),
    "e-manager": ("manager", "t-east", "active"),
    "e-viewer": ("viewer", "t-east", "active"),
    "e-auditor": ("auditor", "t-east", "active"),
}
# Owners of "someone else's" invoices; never send requests.
STAFF = {"t-north": "n-staff", "t-south": "s-staff", "t-east": "e-staff"}
OTHER_TENANT = {"t-north": "t-south", "t-south": "t-north", "t-east": "t-north"}

STATUSES = ("draft", "submitted", "approved")
VALID = {"amount": 250}
INVALID = {"amount": "lots"}


def user_record(user_id):
    role, tenant, status = USERS[user_id]
    record = {"name": user_id, "role": role, "tenant_id": tenant}
    if status is not None:
        record["status"] = status
    return record


def build():
    users = {uid: user_record(uid) for uid in USERS}
    for tenant, uid in STAFF.items():
        users[uid] = {"name": uid, "role": "accountant", "tenant_id": tenant, "status": "active"}
    invoices = {}
    cases = []

    def invoice(inv_id, tenant, owner, amount, status):
        invoices[inv_id] = {"tenant_id": tenant, "owner_id": owner, "amount": amount, "status": status}
        return inv_id

    def case(name, method, path, user, body=None):
        cases.append({"name": name, "method": method, "path": path, "user": user, "body": body})

    # Shared read targets, one per tenant.
    for tenant in TENANTS:
        invoice(f"read-{tenant}", tenant, STAFF[tenant], 700, "submitted")

    case("health", "GET", "/health", None)
    case("no user header", "GET", f"/invoices/read-t-north", None)
    case("unknown user", "GET", f"/invoices/read-t-north", "nobody")
    case("unknown user writes", "DELETE", f"/invoices/read-t-north", "nobody")

    for uid, (_, tenant, _) in USERS.items():
        other = OTHER_TENANT[tenant]
        for label, path in (("view", ""), ("export", "/export")):
            case(f"{uid} {label} own-tenant", "GET", f"/invoices/read-{tenant}{path}", uid)
            case(f"{uid} {label} other-tenant", "GET", f"/invoices/read-{other}{path}", uid)
            case(f"{uid} {label} missing", "GET", f"/invoices/missing{path}", uid)
        own_invoice = invoice(f"view-own-{uid}", tenant, uid, 100, "draft")
        case(f"{uid} view own invoice", "GET", f"/invoices/{own_invoice}", uid)

    for uid, (_, tenant, _) in USERS.items():
        case(f"{uid} create", "POST", "/invoices", uid, VALID)
        case(f"{uid} create invalid body", "POST", "/invoices", uid, INVALID)
        other = OTHER_TENANT[tenant]
        for action, method, suffix in (
            ("edit", "PUT", ""),
            ("delete", "DELETE", ""),
            ("approve", "POST", "/approve"),
        ):
            body = VALID if action == "edit" else None
            amounts = (APPROVAL_LIMIT, APPROVAL_LIMIT + 1) if action == "approve" else (500,)
            for owner_label, owner in (("own", uid), ("other", STAFF[tenant])):
                for status in STATUSES:
                    for amount in amounts:
                        inv = invoice(f"{action}-{uid}-{owner_label}-{status}-{amount}", tenant, owner, amount, status)
                        case(f"{uid} {action} {owner_label} {status} {amount}", method, f"/invoices/{inv}{suffix}", uid, body)
            inv = invoice(f"{action}-{uid}-xtenant", other, STAFF[other], 500, "draft" if action != "approve" else "submitted")
            case(f"{uid} {action} other-tenant", method, f"/invoices/{inv}{suffix}", uid, body)
            case(f"{uid} {action} missing", method, f"/invoices/missing-{action}{suffix}", uid, body)
        for owner_label, owner in (("own", uid), ("other", STAFF[tenant])):
            inv = invoice(f"edit-invalid-{uid}-{owner_label}", tenant, owner, 500, "draft")
            case(f"{uid} edit invalid body {owner_label}", "PUT", f"/invoices/{inv}", uid, INVALID)

    data = {"tenants": TENANTS, "users": users, "invoices": invoices}
    for item in cases:
        item["expected"] = expected(data, item)
    return data, cases


def valid_body(body):
    amount = (body or {}).get("amount")
    return not isinstance(amount, bool) and isinstance(amount, (int, float)) and amount >= 0


def expected(data, case):
    """Status code the original service returns for a request on fresh data."""
    if case["path"] == "/health":
        return 200
    user = data["users"].get(case["user"]) if case["user"] else None
    if user is None:
        return 401
    uid, role, method = case["user"], user["role"], case["method"]
    if user.get("status") == "suspended" and method != "GET":
        return 403
    if case["path"] == "/invoices":
        if role not in WRITERS:
            return 403
        return 201 if valid_body(case["body"]) else 400
    parts = case["path"].split("/")
    invoice = data["invoices"].get(parts[2])
    if invoice is None or invoice["tenant_id"] != user["tenant_id"]:
        return 404
    action = parts[3] if len(parts) > 3 else {"GET": "view", "PUT": "edit", "DELETE": "delete"}[method]
    owner = invoice["owner_id"] == uid
    draft = invoice["status"] == "draft"
    if action == "view":
        return 200 if role == "admin" or role in VIEWERS else 403
    if action == "edit":
        allowed = role == "admin" or (draft if role == "manager" else owner and draft)
        if not allowed:
            return 403
        return 200 if valid_body(case["body"]) else 400
    if action == "delete":
        return 204 if role == "admin" or (owner and draft) else 403
    if action == "approve":
        if role not in APPROVERS or owner:
            return 403
        if invoice["amount"] > APPROVAL_LIMIT and role != "admin":
            return 403
        return 200 if invoice["status"] == "submitted" else 409
    if action == "export":
        if data["tenants"][user["tenant_id"]]["plan"] not in EXPORT_PLANS or role == "viewer":
            return 403
        return 200
    raise ValueError(case)


def send(base_url, case, timeout=10):
    """Send one case and return the status code (shared with the verifier)."""
    headers = {"Content-Type": "application/json"}
    if case["user"]:
        headers["X-User-Id"] = case["user"]
    data = json.dumps(case["body"]).encode() if case["body"] is not None else None
    request = urllib.request.Request(base_url + case["path"], data=data, headers=headers, method=case["method"])
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=timeout) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


def check_original(base_url):
    cases = json.loads((HERE / "cases.json").read_text())
    bad = [(c["name"], c["expected"], got) for c in cases if (got := send(base_url, c)) != c["expected"]]
    for item in bad:
        print("MISMATCH", item)
    print(f"{len(cases) - len(bad)}/{len(cases)} cases match the original app")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--check-original":
        check_original(sys.argv[2])
    data, cases = build()
    (HERE / "hidden-data.json").write_text(json.dumps(data, indent=2) + "\n")
    (HERE / "cases.json").write_text(json.dumps(cases, indent=2) + "\n")
    print(f"Wrote {len(cases)} cases, {len(data['invoices'])} invoices")
