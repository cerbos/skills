"""Feature flags, evaluated per tenant.

CSV export entitlement moved to the Cerbos `invoice` policy (rule
`export-on-paid-plans`); only rollout flags remain here.
"""

FLAGS = {
    # Rollout flag: the redesigned PDF layout is on for everyone.
    "pdf_layout_v2": lambda tenant: True,
}


def is_enabled(flag, tenant):
    rule = FLAGS.get(flag)
    return bool(rule and rule(tenant))
