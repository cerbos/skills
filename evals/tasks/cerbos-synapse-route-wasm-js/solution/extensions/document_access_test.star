test_suite = struct(
    name = "Document access route",
    synapse_config = testing.load_synapse_config("/workspace/config.yaml"),
)

def view(context, user_id, document_id):
    return context.http_get(
        "/ext/documents",
        {"id": document_id},
        headers = {"X-User-Id": user_id, "X-Tenant": "acme"},
    )

def test_same_department_allowed(context):
    have = view(context, "alice", "eng-acme")
    return testing.assert(have.status_code == 200 and have.json()["allowed"] == True)

def test_other_department_denied(context):
    have = view(context, "bob", "eng-acme")
    return testing.assert(have.status_code == 403 and have.json()["allowed"] == False)

def test_unknown_document_not_found(context):
    return testing.assert(view(context, "alice", "missing").status_code == 404)
