"""Shared permission helper for invoice handlers."""


def can(user, action, invoice):
    """Return True when `user` may perform `action` on `invoice`."""
    if user["role"] == "admin":
        return True

    if action == "view":
        return user["role"] in ("manager", "accountant", "viewer")

    if action == "edit":
        if user["role"] == "manager":
            return invoice["status"] == "draft"
        return invoice["owner_id"] == user["id"] and invoice["status"] == "draft"

    if action == "delete":
        return invoice["owner_id"] == user["id"] and invoice["status"] == "draft"

    return False
