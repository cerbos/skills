# Envoy ext_authz extension (Starlark).
#
# The denied response must carry a message and status that come from the Cerbos
# policy OUTPUTS, which aren't known until the PDP responds. A single-shot
# cerbos_mapping can only return fixed allow/deny responses, so this uses the
# "Cerbos check request" mode: envoy_check returns a cerbos_check_request and a
# second map_cerbos_response function builds the Envoy response from the Cerbos
# response.
def envoy_check(req):
    http_req = req.attributes.request.http
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

def map_cerbos_response(input):
    # input is struct(envoy_request=..., cerbos_request=..., cerbos_response=...).
    result = input.cerbos_response.results[0]
    action = input.cerbos_request.resources[0].actions[0]

    if result.actions[action] == "EFFECT_ALLOW":
        # Allowed requests pass through unchanged.
        return struct(status = struct(code = 0))

    # Build the denial body from the matched rule's policy output.
    message = "Access denied"
    for output in result.outputs:
        message = output.val
    return struct(
        status = struct(code = 7),
        denied_response = struct(body = message),
    )
