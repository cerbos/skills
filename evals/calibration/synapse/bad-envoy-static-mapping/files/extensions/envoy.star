# Envoy ext_authz extension (Starlark).
def envoy_check(req):
    http_req = req.attributes.request.http
    # WRONG MODE: this uses the single-shot cerbos_mapping with a hard-coded deny
    # body, so the per-rule denial message from the Cerbos policy outputs can
    # never be injected into the response. This task needs the cerbos_check_request
    # + map_cerbos_response mode instead.
    return struct(cerbos_mapping = struct(
        check_request = struct(
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
        ),
        allow_response = struct(status = struct(code = 0)),
        deny_response = struct(
            status = struct(code = 7),
            denied_response = struct(body = "Forbidden"),
        ),
    ))
