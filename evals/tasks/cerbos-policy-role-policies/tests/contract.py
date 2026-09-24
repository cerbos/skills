"""Expected single-role decisions for the base policies and Acme role policies."""

BASE = {
    "document": {
        "viewer": {"view"},
        "editor": {"view", "edit", "comment"},
        "admin": {"view", "edit", "comment", "delete", "share"},
    },
    "invoice": {
        "accountant": {"view", "approve"},
        "admin": {"view", "approve", "void"},
    },
}
ACTIONS = {
    "document": ["view", "edit", "comment", "delete", "share", "export"],
    "invoice": ["view", "approve", "void", "edit", "export"],
}
ACME_ROLES = {"contractor", "auditor", "editor"}


def base_allows(role, kind, action):
    return action in BASE[kind].get(role, set())


def acme_allowlist(role, principal, resource, action):
    kind = resource["kind"]
    attr = resource.get("attr", {})
    if role == "contractor":
        if kind != "document":
            return False
        if action in {"view", "comment"}:
            return True
        return action == "edit" and attr.get("contractor_editable", False) is True
    if role == "auditor":
        return action == "view"
    if kind != "document":
        return False
    if action in {"view", "comment"}:
        return True
    return action == "edit" and attr.get("department") == principal.get("attr", {}).get(
        "department"
    )


# Parent roles resolve recursively: in Acme, contractor's parent is Acme's
# narrowed editor role policy, which in turn defers to the base editor grants.
PARENTS = {"contractor": ["editor"], "auditor": ["viewer", "accountant"], "editor": []}


def role_allows(role, principal, resource, action):
    kind = resource["kind"]
    if resource.get("scope", "") == "acme" and role in ACME_ROLES:
        if not acme_allowlist(role, principal, resource, action):
            return False
        parents = PARENTS[role]
        if not parents:
            return base_allows(role, kind, action)
        return any(role_allows(parent, principal, resource, action) for parent in parents)
    return base_allows(role, kind, action)


def allows(principal, resource, action):
    """Decision for a principal with exactly one role."""
    (role,) = principal["roles"]
    return role_allows(role, principal, resource, action)
