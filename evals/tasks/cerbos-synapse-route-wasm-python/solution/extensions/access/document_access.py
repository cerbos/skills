# Route extension: answers whether a user may view a document, using the PDP.
import base64
import json

import extism

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


def first(values, key):
    return ((values or {}).get(key) or {}).get("values", [""])[0]


def json_response(status, body):
    # Synapse expects base64 response bodies.
    return {
        "status": status,
        "headers": {"content-type": {"values": ["application/json"]}},
        "body": base64.b64encode(body.encode()).decode(),
    }


@extism.plugin_fn
def handleHTTPRoute():
    req = json.loads(extism.input_str())
    document_id = first(req.get("queryParams"), "id")
    document = DOCUMENTS.get(document_id)
    if document is None:
        extism.output_str(json.dumps({"httpResponse": json_response(404, '{"error": "unknown document"}')}))
        return

    user_id = first(req.get("headers"), "X-User-Id")
    attr = {"tenant": first(req.get("headers"), "X-Tenant")}
    if user_id in DEPARTMENTS:
        attr["department"] = DEPARTMENTS[user_id]

    extism.output_str(json.dumps({
        "cerbosMapping": {
            "checkRequest": {
                "principal": {"id": user_id, "roles": ["employee"], "attr": attr},
                "resources": [{"resource": {"id": document_id, "kind": "document", "attr": document}, "actions": ["view"]}],
            },
            "allowResponse": json_response(200, '{"allowed": true}'),
            "denyResponse": json_response(403, '{"allowed": false}'),
        }
    }))
