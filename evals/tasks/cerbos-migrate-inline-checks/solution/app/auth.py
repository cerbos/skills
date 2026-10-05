"""Request authentication.

Our gateway terminates SSO and forwards the signed-in user's ID in the
X-User-Id header; this module resolves it to a user record for the handlers.
"""

from flask import abort, g, request

import authz
import store

PUBLIC_PATHS = {"/health"}
READ_METHODS = {"GET", "HEAD", "OPTIONS"}


def load_current_user():
    if request.path in PUBLIC_PATHS:
        return None
    user_id = request.headers.get("X-User-Id")
    user = store.get_user(user_id) if user_id else None
    if user is None:
        abort(401)
    g.user = {"id": user_id, **user}

    # Writes are gated before any resource is loaded (Cerbos `api` policy:
    # suspended accounts are read-only).
    if request.method not in READ_METHODS and not authz.is_allowed(g.user, "write", authz.api_resource(request.path)):
        abort(403)
    return None


def init_app(app):
    app.before_request(load_current_user)
