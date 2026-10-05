"""Expected report decisions for the confirmed scope hierarchy."""

SCOPES = ("", "acme", "acme.eu", "globex")
ACTIONS = ("view", "edit", "delete")
BASE = {
    "viewer": {"view"},
    "editor": {"view", "edit"},
    "admin": {"view", "edit", "delete"},
}


def role_allows(role, principal_attr, scope, resource_attr, action):
    base = action in BASE.get(role, set())
    if scope == "":
        return base
    if scope == "globex":
        if action == "delete":
            return False
        if role == "contractor" and action == "view":
            return resource_attr.get("contractor_visible", False) is True
        return base
    allowed = base and not (
        role == "editor" and action == "edit" and resource_attr.get("status") != "draft"
    )
    if scope == "acme.eu":
        allowed = allowed and principal_attr.get("region") == "eu"
    return allowed


def allows(principal, resource, action):
    """A principal receives the union of its roles' permissions in the scope."""
    scope = resource.get("scope", "")
    attr = resource.get("attr", {})
    return any(
        role_allows(role, principal.get("attr", {}), scope, attr, action)
        for role in principal["roles"]
    )
