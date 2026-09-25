# Route extension: answers whether a user may view a document, using the PDP.

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

JSON = {"content-type": struct(values = ["application/json"])}

def first(values, key):
    # Headers and query parameters are proto maps: use `in` and index, not .get().
    return values[key].values[0] if key in values else ""

def handle_http_route(req):
    document_id = first(req.query_params, "id")
    if document_id not in DOCUMENTS:
        return struct(http_response = struct(status = 404, headers = JSON, body = '{"error": "unknown document"}'))

    user_id = first(req.headers, "X-User-Id")
    attr = {"tenant": first(req.headers, "X-Tenant")}
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
        allow_response = struct(status = 200, headers = JSON, body = '{"allowed": true}'),
        deny_response = struct(status = 403, headers = JSON, body = '{"allowed": false}'),
    ))
