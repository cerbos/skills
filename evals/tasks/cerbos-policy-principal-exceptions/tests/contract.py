"""Expected ticket decisions; run as a script to regenerate cases.json."""

import json
from datetime import datetime, timezone
from pathlib import Path

AUDITOR = "ext-auditor-7"
ACTIONS = ["view", "update", "close", "export", "delete"]
# JWT claims the PDP check sends; None means the request carries no token.
TOKENS = {
    "no_token": None,
    "mfa": {"iss": "https://idp.example.com", "amr": ["pwd", "mfa"]},
    "password_only": {"iss": "https://idp.example.com", "amr": ["pwd"]},
    "no_amr_claim": {"iss": "https://idp.example.com"},
}


def parse_time(value):
    """RFC 3339 timestamp as an aware datetime."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def has_mfa(jwt):
    amr = (jwt or {}).get("amr")
    return isinstance(amr, list) and "mfa" in amr


def resource_policy_allows(principal, resource, action, jwt):
    """The seeded ticket rules, with MFA required to close."""
    roles = set(principal["roles"])
    same_team = (
        "team" in principal.get("attr", {})
        and resource.get("attr", {}).get("team") == principal["attr"]["team"]
    )
    if action in {"view", "update"}:
        return bool(roles & {"agent", "manager"}) and same_team
    if action == "close":
        return "manager" in roles and same_team and has_mfa(jwt)
    if action == "export":
        return "reporter" in roles
    return False


def decide(principal, resource, action, now, jwt):
    """The auditor's principal policy is evaluated first.

    Its export DENY is final. Its view grant applies only before
    `engagement_ends`; otherwise the request falls through to the resource policy.
    """
    if principal["id"] == AUDITOR:
        if action == "export":
            return False
        ends = principal.get("attr", {}).get("engagement_ends")
        if action == "view" and ends is not None and now < parse_time(ends):
            return True
    return resource_policy_allows(principal, resource, action, jwt)


def build_cases():
    # now() is the PDP's wall clock, so engagement ends are far from today.
    principals = {
        "auditor_active": {
            "id": AUDITOR,
            "roles": ["reporter"],
            "attr": {"engagement_ends": "2099-12-31T00:00:00Z"},
        },
        "auditor_expired": {
            "id": AUDITOR,
            "roles": ["reporter"],
            "attr": {"engagement_ends": "2001-01-01T00:00:00Z"},
        },
        "lookalike_auditor": {
            "id": "ext-auditor-8",
            "roles": ["reporter"],
            "attr": {"engagement_ends": "2099-12-31T00:00:00Z"},
        },
        "reporter": {"id": "hidden-reporter", "roles": ["reporter"], "attr": {}},
        "agent_billing": {"id": "hidden-agent", "roles": ["agent"], "attr": {"team": "billing"}},
        "manager_billing": {"id": "hidden-mgr", "roles": ["manager"], "attr": {"team": "billing"}},
        "manager_shipping": {"id": "hidden-mgr2", "roles": ["manager"], "attr": {"team": "shipping"}},
        "customer": {"id": "hidden-customer", "roles": ["customer"], "attr": {}},
    }
    resources = {
        f"ticket_{team}": {"kind": "ticket", "id": f"hidden-{team}", "attr": {"team": team}}
        for team in ("billing", "shipping")
    }
    now = datetime.now(timezone.utc)
    cases = []
    for p_name, principal in principals.items():
        for r_name, resource in resources.items():
            for t_name, jwt in TOKENS.items():
                expected = {
                    action: "EFFECT_ALLOW" if decide(principal, resource, action, now, jwt) else "EFFECT_DENY"
                    for action in ACTIONS
                }
                cases.append(
                    {
                        "name": f"{p_name} {r_name} {t_name}",
                        "principal": p_name,
                        "resource": r_name,
                        "token": t_name,
                        "expected": expected,
                    }
                )
    return {"principals": principals, "resources": resources, "tokens": TOKENS, "cases": cases}


if __name__ == "__main__":
    target = Path(__file__).with_name("cases.json")
    target.write_text(json.dumps(build_cases(), indent=2) + "\n")
    print(f"Wrote {target}")
