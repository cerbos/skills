# Envoy ext_authz extension: lets GET /documents/<id> through only when the PDP allows view.

# Principal directory: the authoritative source of each principal's department.
DEPARTMENTS = {
    "alice": "engineering",
    "bob": "sales",
}

# Document catalogue: owning department and tenant of each document.
DOCUMENTS = {
    "eng-acme": {"department": "engineering", "tenant": "acme"},
    "sales-acme": {"department": "sales", "tenant": "acme"},
    "eng-globex": {"department": "engineering", "tenant": "globex"},
}

PREFIX = "/documents/"

def denied(body):
    return struct(status = struct(code = 7), denied_response = struct(status = struct(code = 403), body = body))

def header(headers, key):
    # Envoy lowercases header names; headers is a proto map, so use `in` and index.
    return headers[key] if key in headers else ""

def envoy_check(req):
    http = req.attributes.request.http
    document_id = http.path[len(PREFIX):] if http.path.startswith(PREFIX) else ""
    if document_id not in DOCUMENTS:
        return struct(envoy_check_response = denied("unknown document"))

    user_id = header(http.headers, "x-user-id")
    attr = {"tenant": header(http.headers, "x-tenant")}
    if user_id in DEPARTMENTS:
        attr["department"] = DEPARTMENTS[user_id]

    return struct(cerbos_mapping = struct(
        check_request = struct(
            principal = struct(id = user_id, roles = ["employee"], attr = attr),
            resources = [struct(
                resource = struct(id = document_id, kind = "document", attr = DOCUMENTS[document_id]),
                actions = ["view"],
            )],
        ),
        allow_response = struct(status = struct(code = 0)),
        deny_response = denied("access denied"),
    ))
