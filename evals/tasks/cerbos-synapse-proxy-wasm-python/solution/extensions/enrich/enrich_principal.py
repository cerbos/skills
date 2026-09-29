# Proxy extension: sets the principal's department from an authoritative directory.
import json

import extism

# Principal directory: the authoritative source of each principal's department.
DEPARTMENTS = {
    "alice": "engineering",
    "bob": "sales",
}


@extism.plugin_fn
def augmentCheckRequest():
    req = json.loads(extism.input_str())
    principal = req.get("principal")
    if isinstance(principal, dict):
        attr = principal.get("attr") or {}
        department = DEPARTMENTS.get(principal.get("id", ""))
        if department:
            attr["department"] = department
        else:
            attr.pop("department", None)  # unverified claim
        principal["attr"] = attr
    extism.output_str(json.dumps(req))
