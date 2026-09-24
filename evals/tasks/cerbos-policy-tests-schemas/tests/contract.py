"""Expected decisions for the seeded policies under reject-mode schema enforcement."""

DEPARTMENTS = {"finance", "hr", "sales"}
RESOURCE_STATUS = {"draft", "submitted", "approved"}
DEFAULT_LIMIT = 1000


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def is_string(value):
    return isinstance(value, str)


PRINCIPAL = {
    "required": {"department"},
    "checks": {
        "department": lambda v: v in DEPARTMENTS,
        "approval_limit": lambda v: is_number(v) and v >= 0,
    },
}
RESOURCES = {
    "expense": {
        "required": {"owner", "department", "amount", "status"},
        "checks": {
            "owner": is_string,
            "department": lambda v: v in DEPARTMENTS,
            "amount": lambda v: is_number(v) and v >= 0,
            "status": lambda v: v in RESOURCE_STATUS,
        },
    },
    "leave_request": {
        "required": {"owner", "department", "days"},
        "checks": {
            "owner": is_string,
            "department": lambda v: v in DEPARTMENTS,
            "days": lambda v: isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 30,
        },
    },
}


def issues(schema, attr):
    """Classify schema violations as missing, invalid-value, or unknown attributes."""
    found = set()
    if schema["required"] - set(attr):
        found.add("missing")
    if set(attr) - set(schema["checks"]):
        found.add("unknown")
    for key, check in schema["checks"].items():
        if key in attr and not check(attr[key]):
            found.add("invalid-value")
    return found


def principal_issues(principal):
    return issues(PRINCIPAL, principal.get("attr", {}))


def resource_issues(resource):
    return issues(RESOURCES[resource["kind"]], resource.get("attr", {}))


def policy_allows(principal, resource, action):
    """Seeded policy decision, ignoring schemas; missing attributes fail conditions."""
    roles = set(principal["roles"])
    p = principal.get("attr", {})
    r = resource.get("attr", {})
    pid = principal["id"]
    own = r.get("owner") == pid
    same_department = "department" in r and r.get("department") == p.get("department")
    if action == "create" and "employee" in roles:
        return True
    if resource["kind"] == "expense":
        if "employee" in roles:
            if action == "view" and own:
                return True
            if action == "edit" and own and r.get("status") == "draft":
                return True
        if "manager" in roles:
            if action == "view" and same_department:
                return True
            limit = p.get("approval_limit", DEFAULT_LIMIT)
            if (
                action == "approve"
                and same_department
                and r.get("status") == "submitted"
                and "owner" in r
                and not own
                and is_number(r.get("amount"))
                and is_number(limit)
                and r["amount"] <= limit
            ):
                return True
        return False
    if "employee" in roles and action == "view" and own:
        return True
    return (
        "manager" in roles
        and action in {"view", "approve"}
        and same_department
        and "owner" in r
        and not own
    )


def decide(principal, resource, actions):
    """Return (effects, validation_errors_expected) for one CheckResources entry."""
    rejected = bool(principal_issues(principal)) or (
        bool(resource_issues(resource)) and not all(a == "create" for a in actions)
    )
    if rejected:
        return {a: False for a in actions}, True
    return {a: policy_allows(principal, resource, a) for a in actions}, False
