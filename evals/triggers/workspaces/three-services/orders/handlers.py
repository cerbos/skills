from permissions import can


def cancel_order(user, order):
    if not can(user, "order:cancel", order):
        raise PermissionError("forbidden")
    order["status"] = "cancelled"
    return order
