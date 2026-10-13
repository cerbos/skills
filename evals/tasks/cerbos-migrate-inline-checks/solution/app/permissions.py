"""Shared permission helper for invoice handlers, backed by Cerbos."""

import authz


def can(user, action, invoice_id, invoice):
    """Return True when the PDP allows `user` to perform `action` on `invoice`."""
    return authz.is_allowed(user, action, authz.invoice_resource(invoice_id, invoice))
