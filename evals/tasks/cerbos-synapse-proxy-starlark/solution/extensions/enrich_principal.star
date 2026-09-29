# Principal directory: the authoritative source of each principal's department.
DEPARTMENTS = {
    "alice": "engineering",
    "bob": "sales",
}

def augment_check_request(req):
    department = DEPARTMENTS.get(req.principal.id)
    if department:
        # Per-key write keeps the attributes the caller sent, such as tenant.
        req.principal.attr["department"] = department
    elif "department" in req.principal.attr:
        # Proto maps have no pop(); rebuild without the unverified claim.
        req.principal.attr = {k: req.principal.attr[k] for k in req.principal.attr if k != "department"}
    return req
