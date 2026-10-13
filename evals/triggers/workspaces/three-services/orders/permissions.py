PERMISSIONS = {
    "admin": {"order:read", "order:create", "order:cancel", "order:refund"},
    "support": {"order:read", "order:cancel"},
    "customer": {"order:read", "order:create"},
}


def can(user, action, order=None):
    if action not in PERMISSIONS.get(user["role"], set()):
        return False
    if user["role"] == "customer" and order is not None:
        return order["customer_id"] == user["id"]
    return True
