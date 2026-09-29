"""Principal-exception coverage credits pinned-clock and JWT evidence only."""

import importlib.util
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

TESTS = Path(__file__).parent / "tasks/cerbos-policy-principal-exceptions/tests"
sys.path.insert(0, str(TESTS))
# Each task has its own contract module; drop another task's cached copy.
sys.modules.pop("contract", None)
spec = importlib.util.spec_from_file_location("principal_exceptions", TESTS / "check_outputs.py")
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)
sys.path.remove(str(TESTS))

ENDS = "2026-06-30T00:00:00Z"
BEFORE = datetime(2026, 6, 29, 23, 59, 59, tzinfo=timezone.utc)
AT = datetime(2026, 6, 30, tzinfo=timezone.utc)
TICKET = {"kind": "ticket", "id": "t", "attr": {"team": "billing"}}
MFA = {"amr": ["pwd", "mfa"]}


def auditor(*roles, **attr):
    return {"id": "ext-auditor-7", "roles": list(roles or ["reporter"]), "attr": {"engagement_ends": ENDS, **attr}}


def manager(team="billing"):
    return {"id": "mo", "roles": ["manager"], "attr": {"team": team}}


class PrincipalExceptionLabelTests(unittest.TestCase):
    def test_view_labels_need_a_pinned_clock(self):
        self.assertEqual(verifier.labels(auditor(), TICKET, "view", BEFORE, None), {"auditor-view-active"})
        self.assertEqual(verifier.labels(auditor(), TICKET, "view", AT, None), {"auditor-view-expired"})
        self.assertEqual(verifier.labels(auditor(), TICKET, "view", None, None), set())

    def test_view_granted_by_a_team_role_is_not_credited(self):
        team_agent = auditor("reporter", "agent", team="billing")
        self.assertEqual(verifier.labels(team_agent, TICKET, "view", BEFORE, None), set())

    def test_export_denial_must_override_a_reporter_grant(self):
        self.assertEqual(verifier.labels(auditor(), TICKET, "export", AT, None), {"auditor-export-denied"})
        self.assertEqual(verifier.labels(auditor("customer"), TICKET, "export", AT, None), set())
        self.assertFalse(verifier.decide(auditor(), TICKET, "export", BEFORE, None))
        other = {"id": "rhea", "roles": ["reporter"], "attr": {}}
        self.assertEqual(verifier.labels(other, TICKET, "export", None, None), {"reporter-export-allowed"})

    def test_close_labels_need_the_managers_own_team(self):
        self.assertEqual(verifier.labels(manager(), TICKET, "close", None, MFA), {"close-mfa-allowed"})
        self.assertEqual(
            verifier.labels(manager(), TICKET, "close", None, {"amr": ["pwd"]}), {"close-without-mfa-denied"}
        )
        self.assertEqual(verifier.labels(manager(), TICKET, "close", None, {}), {"close-without-mfa-denied"})
        self.assertEqual(verifier.labels(manager(), TICKET, "close", None, None), {"close-no-token-denied"})
        self.assertEqual(verifier.labels(manager("shipping"), TICKET, "close", None, MFA), set())

    def test_yaml_timestamps_are_accepted(self):
        parsed = datetime(2026, 6, 30)  # PyYAML parses unquoted timestamps
        self.assertEqual(verifier.to_time(parsed), AT)
        self.assertEqual(verifier.normalise(auditor(engagement_ends=parsed))["attr"]["engagement_ends"], AT.isoformat())


if __name__ == "__main__":
    unittest.main()
