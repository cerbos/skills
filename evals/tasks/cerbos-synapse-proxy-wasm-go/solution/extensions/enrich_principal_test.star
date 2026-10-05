test_suite = struct(
    name = "Principal enrichment",
    synapse_config = testing.load_synapse_config("/workspace/config.yaml"),
)

def view(context, principal_id, attr = {"tenant": "acme"}):
    have = context.check_resources(struct(
        requestId = "test-" + principal_id,
        principal = struct(id = principal_id, roles = ["employee"], attr = attr),
        resources = [struct(
            actions = ["view"],
            resource = struct(kind = "document", id = "eng-doc",
                              attr = {"department": "engineering", "tenant": "acme"}),
        )],
    ))
    return have.results[0].actions["view"]

def test_enriched_principal_allowed(context):
    return testing.assert(view(context, "alice") == "EFFECT_ALLOW")

def test_other_department_denied(context):
    return testing.assert(view(context, "bob") == "EFFECT_DENY")

def test_unknown_principal_denied(context):
    return testing.assert(view(context, "carol") == "EFFECT_DENY")

def test_unknown_principal_claim_removed(context):
    claim = {"tenant": "acme", "department": "engineering"}
    return testing.assert(view(context, "carol", claim) == "EFFECT_DENY")
