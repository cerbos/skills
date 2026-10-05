"""Python model of opa/expenses.rego + opa/data.json.

The verifier builds its decision matrix from build_cases() at run time (the
matrix is too large to check in). Run as a script for a summary;
`--rego-inputs` writes the matrix as OPA inputs so the model can be checked
against real `opa eval` at build time (see README).
"""

import json
import sys

ACTIONS = ["view", "create", "edit", "submit", "approve", "delete", "export"]
ROLE_GRANTS = {
    "employee": ["create"],
    "contractor": ["create"],
    "manager": ["view", "create"],
    "director": ["view", "create", "export"],
    "finance": ["view", "export"],
    "auditor": ["view"],
}
APPROVAL_LIMITS = {"manager": 5000, "director": 50000}
MISSING = object()


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def decide(user, action, resource):
    """Rego semantics: an undefined reference makes that body fail, not error."""
    roles = list(user.get("roles") or [])
    get_r = lambda key: resource.get(key, MISSING)  # noqa: E731
    get_u = lambda key: user.get(key, MISSING)  # noqa: E731

    if get_r("legal_hold") is True and action != "view":
        return False
    if "admin" in roles:
        return True
    dept_r, dept_u = get_r("department"), get_u("department")
    if "contractor" in roles and dept_r is not MISSING and dept_u is not MISSING and dept_r != dept_u:
        return False
    if any(action in ROLE_GRANTS.get(role, []) for role in roles):
        return True
    owner = get_r("owner")
    if owner is not MISSING and get_u("id") is not MISSING and owner == user["id"]:
        if action == "view":
            return True
        if action in {"edit", "submit", "delete"} and get_r("status") == "draft":
            return True
    if action == "approve" and get_r("status") == "submitted":
        if owner is not MISSING and owner != user.get("id"):
            amount = get_r("amount")
            for role in roles:
                limit = APPROVAL_LIMITS.get(role)
                # Rego compares numbers to numbers only; a mismatched type is undefined.
                if limit is not None and is_number(amount) and amount <= limit:
                    return True
    return False


def rego_input(principal, resource, action):
    """Translate a Cerbos principal/resource pair to the Rego input document."""
    user = {"id": principal["id"], "roles": principal["roles"]}
    if "department" in (principal.get("attr") or {}):
        user["department"] = principal["attr"]["department"]
    return {"user": user, "action": action, "resource": {"id": resource["id"], **(resource.get("attr") or {})}}


def decide_cerbos(principal, resource, action):
    data = rego_input(principal, resource, action)
    return decide(data["user"], action, data["resource"])


PRINCIPALS = {
    "admin": ("u-admin", ["admin"], "sales"),
    "admin_contractor": ("u-admin-con", ["admin", "contractor"], "sales"),
    "employee": ("u-emp", ["employee"], "sales"),
    "contractor": ("u-con", ["contractor"], "sales"),
    "contractor_finance": ("u-con-fin", ["contractor", "finance"], "sales"),
    "contractor_manager": ("u-con-mgr", ["contractor", "manager"], "sales"),
    "manager": ("u-mgr", ["manager"], "sales"),
    "manager_director": ("u-mgr-dir", ["manager", "director"], "sales"),
    "director": ("u-dir", ["director"], "engineering"),
    "finance": ("u-fin", ["finance"], "finance"),
    "auditor": ("u-aud", ["auditor"], "audit"),
    "intern": ("u-int", ["intern"], "sales"),
}
OWNERS = ["u-emp", "u-con", "u-mgr", "u-con-mgr", "u-other"]
DEPARTMENTS = ["sales", "engineering"]
AMOUNTS = [5000, 5001, 50001]
STATUSES = ["draft", "submitted", "approved"]
HOLDS = {"nohold": MISSING, "holdfalse": False, "hold": True}


def build_cases():
    principals = {
        name: {"id": pid, "roles": roles, "attr": {"department": dept}}
        for name, (pid, roles, dept) in PRINCIPALS.items()
    }
    resources = {}
    for owner in OWNERS:
        for dept in DEPARTMENTS:
            for amount in AMOUNTS:
                for status in STATUSES:
                    for hold_name, hold in HOLDS.items():
                        name = f"{owner}_{dept}_{amount}_{status}_{hold_name}"
                        attr = {"owner": owner, "department": dept, "amount": amount, "status": status}
                        if hold is not MISSING:
                            attr["legal_hold"] = hold
                        resources[name] = {"kind": "expense", "id": f"hidden-{name}", "attr": attr}
    # Approve boundary for the higher limit.
    for owner in ("u-other", "u-mgr"):
        name = f"{owner}_sales_50000_submitted_nohold"
        resources[name] = {
            "kind": "expense",
            "id": f"hidden-{name}",
            "attr": {"owner": owner, "department": "sales", "amount": 50000, "status": "submitted"},
        }
    cases = []
    for p_name, principal in principals.items():
        for r_name, resource in resources.items():
            expected = {
                action: "EFFECT_ALLOW" if decide_cerbos(principal, resource, action) else "EFFECT_DENY"
                for action in ACTIONS
            }
            cases.append({"name": f"{p_name} {r_name}", "principal": p_name, "resource": r_name, "expected": expected})
    return {"principals": principals, "resources": resources, "cases": cases}


if __name__ == "__main__":
    suite = build_cases()
    if len(sys.argv) > 1 and sys.argv[1] == "--rego-inputs":
        # One JSON line per decision, for `opa eval` replay at build time.
        for case in suite["cases"]:
            principal, resource = suite["principals"][case["principal"]], suite["resources"][case["resource"]]
            for action, effect in case["expected"].items():
                print(json.dumps({"input": rego_input(principal, resource, action), "expected": effect == "EFFECT_ALLOW"}))
        raise SystemExit(0)
    allow = sum(v == "EFFECT_ALLOW" for c in suite["cases"] for v in c["expected"].values())
    total = sum(len(c["expected"]) for c in suite["cases"])
    print(f"{len(suite['cases'])} requests, {total} decisions, {allow} allow")
