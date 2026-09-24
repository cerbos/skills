"""Output coverage credits asserted outputs that demonstrate each requirement."""

import importlib.util
import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).parent / "tasks/cerbos-policy-outputs/tests"
sys.path.insert(0, str(TESTS))
# Each task has its own contract module; drop another task's cached copy.
sys.modules.pop("contract", None)
spec = importlib.util.spec_from_file_location("payout_outputs", TESTS / "check_outputs.py")
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)
contract_spec = importlib.util.spec_from_file_location("payout_contract", TESTS / "contract.py")
contract = importlib.util.module_from_spec(contract_spec)
contract_spec.loader.exec_module(contract)
sys.path.remove(str(TESTS))

SRC = verifier.SRC
MANAGER = {"id": "max", "roles": ["manager"], "attr": {"approval_limit": 1000}}
CLERK = {"id": "clara", "roles": ["clerk"], "attr": {}}


def payout(amount, **attr):
    return {"kind": "payout", "id": "po", "attr": {"amount": amount, "account": "a", **attr}}


class OutputLabelTests(unittest.TestCase):
    def test_limit_boundary_is_distinct(self):
        approved = {"event": "payout_approved", "payout": "po", "approver": "max"}
        self.assertEqual(
            verifier.labels(MANAGER, payout(1000), "approve", SRC + "approve-within-limit", approved),
            {"approved-at-limit"},
        )
        self.assertEqual(
            verifier.labels(MANAGER, payout(999), "approve", SRC + "approve-within-limit", approved),
            {"approved-below-limit"},
        )

    def test_frozen_needs_an_otherwise_approvable_request(self):
        frozen = {"reason": "account_frozen", "account": "a"}
        src = SRC + "block-frozen-accounts"
        self.assertEqual(
            verifier.labels(MANAGER, payout(500, frozen=True), "approve", src, frozen),
            {"frozen-otherwise-approvable"},
        )
        self.assertEqual(verifier.labels(MANAGER, payout(5000, frozen=True), "approve", src, frozen), set())

    def test_flag_priority_labels_are_role_specific(self):
        normal = {"event": "payout_flagged", "by": "clara", "priority": "normal"}
        self.assertEqual(
            verifier.labels(CLERK, payout(10000), "flag", SRC + "flag-payouts", normal),
            {"flag-normal-at-10000-clerk"},
        )
        self.assertEqual(verifier.labels(CLERK, payout(9000), "flag", SRC + "flag-payouts", normal), set())

    def test_frozen_allow_outputs_are_order_dependent(self):
        frozen = payout(500, frozen=True)
        _, outputs = verifier.decide(MANAGER, frozen, "approve")
        required, optional = contract.split(frozen, outputs)
        self.assertEqual([src for src, _ in required], [SRC + "block-frozen-accounts"])
        self.assertEqual([src for src, _ in optional], [SRC + "approve-within-limit"])
        _, outputs = verifier.decide(MANAGER, payout(500), "approve")
        self.assertEqual(contract.split(payout(500), outputs), (outputs, []))


if __name__ == "__main__":
    unittest.main()
