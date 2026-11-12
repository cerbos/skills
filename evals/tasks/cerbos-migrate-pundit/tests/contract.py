"""Python model of app/policies/*.rb.

The verifier builds its decision matrix from build_cases() at run time. Run as
a script for a summary; `--ruby-cases` writes the matrix as JSON lines so the
model can be checked against the real Ruby policies at build time (see README).
"""

import json
import sys

ACTIONS = ["show", "new", "create", "edit", "update", "publish", "destroy"]
GUEST_ID = "anonymous"


def pundit_user(principal):
    """Map a Cerbos principal back to Current.user; the guest principal is nil."""
    if principal["id"] == GUEST_ID:
        return None
    attr = principal.get("attr") or {}
    return {
        "id": principal["id"],
        "roles": list(principal.get("roles") or []),
        "team_ids": list(attr.get("team_ids") or []),
        "suspended": attr.get("suspended") is True,
    }


def pundit_record(resource):
    attr = resource.get("attr") or {}
    return {
        "id": resource["id"],
        "owner_id": attr.get("owner_id"),
        "team_id": attr.get("team_id"),
        "published": attr.get("published"),
        "confidential": attr.get("confidential"),
        "locked_by": attr.get("locked_by"),
    }


def decide(user, action, record):
    if user is not None and user["suspended"]:
        return False
    roles = user["roles"] if user else []
    admin = "admin" in roles
    owner = user is not None and record["owner_id"] == user["id"]
    member = user is not None and record["team_id"] in user["team_ids"]
    editor = "editor" in roles
    external = "external" in roles
    locked = bool(record["locked_by"]) and record["locked_by"] != (user["id"] if user else None)

    def update():
        if admin:
            return True
        if locked:
            return False
        return owner or (editor and member)

    if action == "show":
        if admin:
            return True
        if external and record["confidential"]:
            return False
        if record["published"]:
            return True
        if user is None:
            return False
        return owner or member
    if action in ("new", "create"):
        return user is not None and bool({"editor", "admin"} & set(roles))
    if action in ("edit", "update", "publish"):
        return update()
    if action == "destroy":
        return admin or (owner and not record["published"])
    raise ValueError(action)


def decide_cerbos(principal, resource, action):
    return decide(pundit_user(principal), action, pundit_record(resource))


PRINCIPALS = {
    "admin": ("u-admin", ["admin"], ["t1"], False),
    "admin_external": ("u-adm-ext", ["admin", "external"], ["t1"], False),
    "editor": ("u-editor", ["editor"], ["t1"], False),
    "editor_t2": ("u-editor2", ["editor"], ["t2"], False),
    "editor_external": ("u-ed-ext", ["editor", "external"], ["t1"], False),
    "member": ("u-member", ["member"], ["t1"], False),
    "external": ("u-ext", ["external"], ["t1"], False),
    "intern": ("u-intern", ["intern"], [], False),
    "suspended_admin": ("u-sus-adm", ["admin"], ["t1"], True),
    "suspended_editor": ("u-sus-ed", ["editor"], ["t1"], True),
}
OWNERS = ["u-editor", "u-member", "u-ed-ext", "u-intern", "u-sus-ed", "u-other"]
TEAMS = ["t1", "t2"]
LOCKS = [None, "u-editor", "u-member", "u-other"]


def build_principals():
    principals = {}
    for name, (pid, roles, teams, suspended) in PRINCIPALS.items():
        attr = {"team_ids": teams}
        if suspended:
            attr["suspended"] = True
        principals[name] = {"id": pid, "roles": roles, "attr": attr}
    principals["guest"] = {"id": GUEST_ID, "roles": ["anonymous"]}
    return principals


def build_resources():
    resources = {}
    for owner in OWNERS:
        for team in TEAMS:
            for published in (False, True):
                for confidential in (False, True):
                    for lock in LOCKS:
                        name = f"{owner}_{team}_{'pub' if published else 'draft'}_{'conf' if confidential else 'open'}_{lock or 'unlocked'}"
                        attr = {"owner_id": owner, "team_id": team, "published": published, "confidential": confidential}
                        if lock:
                            attr["locked_by"] = lock
                        resources[name] = {"kind": "document", "id": f"hidden-{name}", "attr": attr}
    return resources


def build_cases():
    principals, resources = build_principals(), build_resources()
    cases = []
    for p_name, principal in principals.items():
        for r_name, resource in resources.items():
            expected = {
                action: "EFFECT_ALLOW" if decide_cerbos(principal, resource, action) else "EFFECT_DENY"
                for action in ACTIONS
            }
            cases.append({"name": f"{p_name} {r_name}", "principal": p_name, "resource": r_name, "expected": expected})
    return {"principals": principals, "resources": resources, "cases": cases}


if __name__ == "__main__":
    suite = build_cases()
    if len(sys.argv) > 1 and sys.argv[1] == "--ruby-cases":
        for case in suite["cases"]:
            principal, resource = suite["principals"][case["principal"]], suite["resources"][case["resource"]]
            for action, effect in case["expected"].items():
                print(json.dumps({
                    "user": pundit_user(principal),
                    "record": pundit_record(resource),
                    "action": action,
                    "expected": effect == "EFFECT_ALLOW",
                }))
        raise SystemExit(0)
    allow = sum(v == "EFFECT_ALLOW" for c in suite["cases"] for v in c["expected"].values())
    total = sum(len(c["expected"]) for c in suite["cases"])
    print(f"{len(suite['cases'])} requests, {total} decisions, {allow} allow")
