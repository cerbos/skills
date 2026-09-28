"""Expected document decisions; run as a script to regenerate cases.json."""

import json
from pathlib import Path

ACTIONS = ["view", "edit", "download", "delete", "share"]
DOWNLOAD_LIMIT_MB = 25


def role_allows(role, principal, resource, action):
    attr = resource.get("attr", {})
    if role == "contractor" and attr.get("classification") != "public":
        # An absent classification is not public.
        return False
    if action == "view":
        return role in {"employee", "contractor", "manager"}
    if action == "edit":
        return role in {"employee", "contractor"} and attr.get("owner") == principal["id"]
    if action == "download":
        return role == "manager" or (role == "employee" and attr["size_mb"] <= DOWNLOAD_LIMIT_MB)
    if action == "delete":
        return role == "manager"
    return False


def decide(principal, resource, action):
    """Cerbos evaluates each role separately; any role's ALLOW grants access."""
    return any(role_allows(role, principal, resource, action) for role in principal["roles"])


def build_cases():
    principals = {
        "employee": {"id": "hidden-emp", "roles": ["employee"], "attr": {}},
        "contractor": {"id": "hidden-con", "roles": ["contractor"], "attr": {}},
        "manager": {"id": "hidden-mgr", "roles": ["manager"], "attr": {}},
        "guest": {"id": "hidden-guest", "roles": ["guest"], "attr": {}},
    }
    owners = {"emp": "hidden-emp", "con": "hidden-con", "other": "hidden-other"}
    classifications = {"absent": None, "public": "public", "internal": "internal"}
    resources = {}
    for size in (10, 25, 26):
        for c_name, classification in classifications.items():
            for o_name, owner in owners.items():
                name = f"doc_{size}_{c_name}_{o_name}"
                attr = {"owner": owner, "size_mb": size}
                if classification is not None:
                    attr["classification"] = classification
                resources[name] = {"kind": "document", "id": f"hidden-{name}", "attr": attr}
    cases = []
    for p_name, principal in principals.items():
        for r_name, resource in resources.items():
            expected = {
                action: "EFFECT_ALLOW" if decide(principal, resource, action) else "EFFECT_DENY"
                for action in ACTIONS
            }
            cases.append(
                {"name": f"{p_name} {r_name}", "principal": p_name, "resource": r_name, "expected": expected}
            )
    return {"principals": principals, "resources": resources, "cases": cases}


if __name__ == "__main__":
    target = Path(__file__).with_name("cases.json")
    target.write_text(json.dumps(build_cases(), indent=2) + "\n")
    print(f"Wrote {target}")
