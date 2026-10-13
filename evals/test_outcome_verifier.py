"""Checks the outcome eval's case set and workspace grading without calling a model."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "triggers"))

import outcomes  # noqa: E402

CASE = {"id": "x", "workspace": "express-expenses", "action": "approve", "literals": ["5000"], "roles": ["manager"]}

POLICY = """\
apiVersion: api.cerbos.dev/v1
resourcePolicy:
  resource: expense
  version: default
  rules:
    - actions: ["approve"]
      effect: EFFECT_ALLOW
      roles: ["manager"]
      condition:
        match:
          expr: R.attr.team == P.attr.team && R.attr.amount <= 5000
"""

TESTS = """\
name: ExpenseTests
tests:
  - name: approve
    input: {principals: [mia], resources: [small], actions: [approve]}
    expected:
      - {principal: mia, resource: small, actions: {approve: EFFECT_ALLOW}}
"""

PEP = """\
import { GRPC } from "@cerbos/grpc";
const cerbos = new GRPC("localhost:3593", { tls: false });
app.post("/expenses/:id/approve", async (req, res) => {
  const allowed = await cerbos.isAllowed({ principal, resource, action: "approve" });
  if (!allowed) return res.sendStatus(403);
});
"""

HARDCODED = """\
app.post("/expenses/:id/approve", (req, res) => {
  const { role, team } = req.user;
  if (role !== "manager" || team !== expense.team || expense.amount > 5000) {
    return res.sendStatus(403);
  }
});
"""


def workspace(files: dict) -> tempfile.TemporaryDirectory:
    tmp = tempfile.TemporaryDirectory()
    for name, text in files.items():
        f = Path(tmp.name) / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text)
    return tmp


class CaseSetTest(unittest.TestCase):
    def test_cases_load_and_name_real_workspaces(self):
        cases = outcomes.load_cases()
        self.assertTrue(cases)
        for c in cases:
            self.assertTrue((outcomes.run.WORKSPACES / c["workspace"]).is_dir(), c["id"])

    def test_stub_workspace_starts_without_authorization(self):
        for c in outcomes.load_cases():
            with tempfile.TemporaryDirectory() as ws:
                outcomes.run.prepare_workspace(c, Path(ws))
                g = outcomes.grade(Path(ws), c)
                self.assertEqual(outcomes.outcome(g), "no change", c["id"])


class GradeTest(unittest.TestCase):
    def grade(self, files):
        with workspace(files) as ws:
            return outcomes.grade(Path(ws), CASE)

    def test_policy_tests_and_pdp_call_pass(self):
        g = self.grade({"policies/expense.yaml": POLICY, "policies/tests/expense_test.yaml": TESTS,
                        "src/server.js": PEP})
        self.assertEqual(outcomes.outcome(g), "cerbos")
        self.assertTrue(g["policy_tests"])
        self.assertEqual(g["policy_files"], ["policies/expense.yaml"])

    def test_hard_coded_handler_fails(self):
        g = self.grade({"src/server.js": HARDCODED})
        self.assertEqual(outcomes.outcome(g), "hard-coded")
        self.assertEqual(g["hardcoded_in"], ["src/server.js"])

    def test_policy_with_a_copy_in_the_handler_fails(self):
        g = self.grade({"policies/expense.yaml": POLICY, "src/server.js": PEP + HARDCODED})
        self.assertEqual(outcomes.outcome(g), "both")

    def test_limit_spellings_are_caught_but_larger_numbers_are_not(self):
        for code, hit in [("amount > 5_000", True), ("amount > 5,000", False), ("amount <= 5000.0", True),
                          ("const LIMIT = 50000", False), ("x = 15000", False)]:
            with self.subTest(code=code):
                g = self.grade({"src/limits.js": code})
                self.assertEqual(g["rule_in_code"], hit)

    def test_role_comparison_alone_counts_as_rule_in_code(self):
        g = self.grade({"policies/expense.yaml": POLICY, "src/server.js": PEP + 'if (req.user.role === "manager") next();'})
        self.assertTrue(g["rule_in_code"])

    def test_test_scripts_and_comments_may_name_the_limit(self):
        g = self.grade({"policies/expense.yaml": POLICY, "src/server.js": PEP + "// up to 5000\n",
                        "scripts/smoke.mjs": "amount: 5000", "test/approve.test.js": "amount: 5000"})
        self.assertEqual(outcomes.outcome(g), "cerbos")

    def test_policy_without_the_limit_is_incomplete(self):
        g = self.grade({"policies/expense.yaml": POLICY.replace(" && R.attr.amount <= 5000", ""),
                        "src/server.js": PEP})
        self.assertEqual(outcomes.outcome(g), "incomplete")

    def test_node_modules_are_ignored(self):
        g = self.grade({"node_modules/x/index.js": HARDCODED})
        self.assertFalse(g["rule_in_code"])



class RefusedSkillTest(unittest.TestCase):
    def test_refused_skill_load_is_reported(self):
        events = [
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": "a", "name": "Skill", "input": {"skill": "cerbos-skills:cerbos-policy"}},
                {"type": "tool_use", "id": "b", "name": "Skill", "input": {"skill": "cerbos-skills:cerbos"}}]}},
            {"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": "a", "is_error": True, "content": "Execute skill"},
                {"type": "tool_result", "tool_use_id": "b", "content": "Launching skill"}]}},
        ]
        self.assertEqual(outcomes.refused_skills(events), ["cerbos-policy"])


if __name__ == "__main__":
    unittest.main()
