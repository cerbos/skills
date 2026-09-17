# Envoy ext_authz extension (Starlark).
def envoy_check(req):
    http_req = req.attributes.request.http
    # This returns a cerbos_check_request (the dynamic-response mode), which
    # REQUIRES a second `map_cerbos_response` function to build the Envoy response
    # from the Cerbos response. That function is missing, so the extension can
    # never produce a response — the required second callback was never defined.
    return struct(cerbos_check_request = struct(
        principal = struct(
            id = http_req.headers["x-user-id"],
            roles = ["user"],
        ),
        resources = [struct(
            actions = [http_req.method],
            resource = struct(
                id = "route",
                kind = "request",
                attr = {"path": http_req.path},
            ),
        )],
    ))
