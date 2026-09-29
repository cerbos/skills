test_suite = struct(
    name = "Document gate",
    synapse_config = testing.load_synapse_config("/workspace/config.yaml"),
)

def check(context, user_id, path):
    return context.envoy_check(struct(attributes = struct(request = struct(http = struct(
        id = "test",
        method = "GET",
        path = path,
        headers = {"x-user-id": user_id, "x-tenant": "acme"},
    )))))

def test_same_department_allowed(context):
    return testing.assert(check(context, "alice", "/documents/eng-acme").status.code == 0)

def test_other_department_denied(context):
    return testing.assert(check(context, "bob", "/documents/eng-acme").status.code == 7)

def test_unknown_document_denied(context):
    return testing.assert(check(context, "alice", "/documents/missing").status.code == 7)
