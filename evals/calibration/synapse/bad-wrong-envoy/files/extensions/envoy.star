def envoy_check(req):
    # Turn an Envoy check request into a Cerbos check.
    return cerbos.check(
        principal = {"id": req.principal_id, "roles": req.roles},
        resource = {"kind": req.resource_kind, "id": req.resource_id},
        actions = [req.action],
    )

# WRONG: the callback must be named `map_cerbos_response`, not this.
def envoy_map_cerbos_response(resp):
    headers = {"x-cerbos-decision": "allow" if resp.allowed else "deny"}
    return {"allowed": resp.allowed, "headers": headers}
