"""Feature flags, evaluated per tenant."""

FLAGS = {
    # Rollout flag: the redesigned PDF layout is on for everyone.
    "pdf_layout_v2": lambda tenant: True,
    # CSV export ships with the paid plans only.
    "csv_export": lambda tenant: tenant["plan"] in ("pro", "enterprise"),
}


def is_enabled(flag, tenant):
    rule = FLAGS.get(flag)
    return bool(rule and rule(tenant))
