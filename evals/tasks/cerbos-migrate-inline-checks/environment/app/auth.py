"""Request authentication.

Our gateway terminates SSO and forwards the signed-in user's ID in the
X-User-Id header; this module resolves it to a user record for the handlers.
"""

from flask import abort, g, request

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

    # Accounts under review are kept read-only until billing clears them.
    if user.get("status") == "suspended" and request.method not in READ_METHODS:
        abort(403)
    return None


def init_app(app):
    app.before_request(load_current_user)
