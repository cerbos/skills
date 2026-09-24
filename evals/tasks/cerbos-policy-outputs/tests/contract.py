"""Expected effects and outputs for the payout policy."""

SRC = "resource.payout.vdefault#"
ACTIONS = ["view", "approve", "flag", "delete"]


def decide(principal, resource, action):
    """Return (allowed, outputs) where outputs is a list of (src, value).

    For frozen payouts the frozen-account output is required, and outputs from
    allow rules are optional (see split()): Cerbos emits them only for rules
    evaluated before the matching DENY rule, so presence depends on rule order.
    """
    roles = set(principal["roles"])
    p = principal.get("attr", {})
    r = resource.get("attr", {})
    staff = bool(roles & {"clerk", "manager"})
    allowed, outputs = False, []
    if action == "view" and staff:
        allowed = True
    if action == "approve" and "manager" in roles:
        if r["amount"] <= p["approval_limit"]:
            allowed = True
            outputs.append(
                (
                    SRC + "approve-within-limit",
                    {"event": "payout_approved", "payout": resource["id"], "approver": principal["id"]},
                )
            )
        else:
            outputs.append(
                (
                    SRC + "approve-within-limit",
                    {"reason": "over_limit", "amount": r["amount"], "limit": p["approval_limit"]},
                )
            )
    if action == "flag" and staff:
        allowed = True
        priority = "high" if r["amount"] > 10000 else "normal"
        outputs.append(
            (SRC + "flag-payouts", {"event": "payout_flagged", "by": principal["id"], "priority": priority})
        )
    if r.get("frozen", False) is True:
        allowed = False
        outputs.append((SRC + "block-frozen-accounts", {"reason": "account_frozen", "account": r["account"]}))
    return allowed, outputs


def split(resource, outputs):
    """Separate required outputs from rule-order-dependent ones."""
    if resource.get("attr", {}).get("frozen", False) is not True:
        return outputs, []
    frozen = SRC + "block-frozen-accounts"
    return [o for o in outputs if o[0] == frozen], [o for o in outputs if o[0] != frozen]
