"""Checks the trigger eval's prompt set, transcript parsing and scoring without calling a model."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "triggers"))

import run  # noqa: E402

SKILLS = ["cerbos", "cerbos-embedded-pdp", "cerbos-pep-integration", "cerbos-policy"]


def tool(name, **args):
    return {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": name, "input": args}]}}


def result(id, expect, loaded, also_ok=(), near=()):
    return {"id": id, "rep": 0, "expect": expect, "also_ok": list(also_ok), "near": list(near),
            "loaded": loaded, "error": None}


class PromptSetTest(unittest.TestCase):
    def test_prompt_set_is_valid_and_covers_every_skill(self):
        prompts = run.load_prompts()
        skills = run.skill_names()
        for skill in skills:
            positives = [p for p in prompts if p["expect"] == skill]
            self.assertGreaterEqual(len(positives), 6, skill)
        self.assertGreaterEqual(sum(p["expect"] is None for p in prompts), 10)

    def test_unknown_skill_is_rejected(self):
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl") as f:
            f.write(json.dumps({"id": "x", "expect": "cerbos-nope", "prompt": "hi"}) + "\n")
            f.flush()
            with self.assertRaisesRegex(ValueError, "unknown skill"):
                run.load_prompts(Path(f.name), SKILLS)


class ParseTest(unittest.TestCase):
    def test_claude_skill_tool_and_direct_reads_in_order(self):
        events = [
            {"type": "system", "subtype": "init"},
            tool("Glob", pattern="**/*"),
            tool("Skill", skill="cerbos-skills:cerbos"),
            tool("Read", file_path="/x/skills/cerbos-policy/SKILL.md"),
            tool("Read", file_path="/x/skills/cerbos-policy/references/tests.md"),
            tool("Skill", skill="cerbos-skills:cerbos"),
            tool("Skill", skill="deep-research"),
        ]
        self.assertEqual(run.claude_loaded(events, SKILLS), ["cerbos", "cerbos-policy"])

    def test_codex_reads_skill_files_from_shell_commands(self):
        events = [
            {"type": "item.started", "item": {"type": "command_execution",
                                              "command": "cat /h/skills/cerbos-policy/SKILL.md"}},
            {"type": "item.completed", "item": {"type": "agent_message", "text": "skills/cerbos/SKILL.md"}},
            {"type": "item.completed", "item": {"type": "command_execution",
                                                "command": "/bin/zsh -lc 'sed -n 1,200p /h/skills/cerbos-embedded-pdp/SKILL.md'"}},
            {"type": "item.completed", "item": {"type": "command_execution",
                                                "command": "cat /h/skills/cerbos-embedded-pdp/references/RULES.md"}},
        ]
        self.assertEqual(run.codex_loaded(events, SKILLS), ["cerbos-embedded-pdp"])


class ScoreTest(unittest.TestCase):
    def setUp(self):
        self.results = [
            result("a", "cerbos-policy", ["cerbos-policy"]),
            result("b", "cerbos-policy", ["cerbos", "cerbos-policy"], also_ok=["cerbos"]),
            result("c", "cerbos-policy", []),
            result("d", "cerbos-embedded-pdp", ["cerbos-pep-integration"], near=["cerbos-pep-integration"]),
            result("e", None, ["cerbos"], near=["cerbos"]),
            result("f", None, []),
            {**result("g", "cerbos-policy", []), "error": "timeout"},
        ]

    def test_recall_precision_and_near_misses(self):
        s = run.score(self.results, SKILLS)
        policy = s["per_skill"]["cerbos-policy"]
        self.assertEqual((policy["recall"]["n"], policy["recall"]["of"]), (2, 3))
        self.assertEqual(policy["first_pick"]["n"], 1)
        self.assertEqual(policy["precision"]["rate"], 1.0)
        router = s["per_skill"]["cerbos"]
        # Loaded on b (acceptable) and e (a negative): one of two correct.
        self.assertEqual(router["precision"]["rate"], 0.5)
        self.assertEqual(router["near_miss_fired"]["rate"], 1.0)
        self.assertEqual(s["per_skill"]["cerbos-pep-integration"]["precision"]["rate"], 0.0)
        self.assertEqual(s["overall"]["false_trigger_on_none"]["n"], 1)
        self.assertEqual(s["errors"], 1)

    def test_confusion_matrix_uses_first_skill_loaded(self):
        m = run.score(self.results, SKILLS)["confusion"]
        self.assertEqual(m["cerbos-policy"]["cerbos-policy"], 1)
        self.assertEqual(m["cerbos-policy"]["cerbos"], 1)
        self.assertEqual(m["cerbos-policy"]["none"], 1)
        self.assertEqual(m["cerbos-embedded-pdp"]["cerbos-pep-integration"], 1)
        self.assertEqual(m["none"]["cerbos"], 1)

    def test_relabel_applies_current_labels(self):
        prompts = [{"id": "e", "expect": "cerbos", "also_ok": [], "near": []}]
        relabelled = run.relabel(self.results, prompts)
        self.assertEqual(relabelled[4]["expect"], "cerbos")
        self.assertEqual(relabelled[0], self.results[0])

    def test_report_lists_misses(self):
        meta = {"agent": "claude", "model": "sonnet", "prompts": 7, "repeats": 1}
        text = run.render(meta, self.results, SKILLS)
        self.assertIn("| `c` | 0 | policy | none |", text)
        self.assertIn("| `e` | 0 | none | router |", text)
        self.assertNotIn("| `a` |", text)
        self.assertIn("`g` rep 0: timeout", text)


if __name__ == "__main__":
    unittest.main()
