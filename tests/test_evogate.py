import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import evogate

ROOT = os.path.join(os.path.dirname(__file__), "..")


class ScoreTests(unittest.TestCase):
    def test_contains_all(self):
        passed, total, fails = evogate.score_answer(
            "The sky banner is teal.", {"contains_all": ["teal"]})
        self.assertEqual((passed, total), (1, 1))
        passed, total, fails = evogate.score_answer(
            "No idea.", {"contains_all": ["teal"]})
        self.assertEqual(passed, 0)
        self.assertTrue(fails)

    def test_contains_any_and_not_contains(self):
        passed, total, _ = evogate.score_answer(
            "Support opens at 09:00.", {"contains_any": [["08:00", "09:00"]]})
        self.assertEqual(passed, 1)
        passed, total, _ = evogate.score_answer(
            "maybe later", {"not_contains": ["maybe"]})
        self.assertEqual(passed, 0)

    def test_max_chars(self):
        passed, total, fails = evogate.score_answer("x" * 61, {"max_chars": 60})
        self.assertEqual(passed, 0)
        self.assertIn("too long", fails[0])


class GateTests(unittest.TestCase):
    def cand(self, score, crit=None):
        return {"score": score, "critical_failures": crit or []}

    def test_first_champion_promoted(self):
        ok, _ = evogate.gate(self.cand(0.5), None)
        self.assertTrue(ok)

    def test_higher_score_promoted(self):
        ok, _ = evogate.gate(self.cand(0.9), {"variant": "a", "score": 0.5})
        self.assertTrue(ok)

    def test_tie_rejected(self):
        ok, reason = evogate.gate(self.cand(0.5), {"variant": "a", "score": 0.5})
        self.assertFalse(ok)
        self.assertIn("tie", reason)

    def test_lower_rejected(self):
        ok, _ = evogate.gate(self.cand(0.4), {"variant": "a", "score": 0.5})
        self.assertFalse(ok)

    def test_critical_failure_rejected_even_when_higher(self):
        ok, reason = evogate.gate(self.cand(1.0, ["short-answer"]),
                                  {"variant": "a", "score": 0.5})
        self.assertFalse(ok)
        self.assertIn("critical", reason)

    def test_critical_failure_rejected_for_first_champion(self):
        ok, _ = evogate.gate(self.cand(0.2, ["short-answer"]), None)
        self.assertFalse(ok)


class RunnerTests(unittest.TestCase):
    SUITE = {"tasks": [{"id": "t1", "input": "q",
                        "checks": {"contains_all": ["teal"]}}]}

    def test_runner_output_scored(self):
        res = evogate.run_variant("echo teal", "v.md", self.SUITE)
        self.assertEqual(res["score"], 1.0)

    def test_runner_failure_scores_zero(self):
        res = evogate.run_variant("false", "v.md", self.SUITE)
        self.assertEqual(res["score"], 0.0)
        self.assertEqual(res["critical_failures"], [])


class DemoTournamentTests(unittest.TestCase):
    def test_demo_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            res = subprocess.run(
                [sys.executable, os.path.join(ROOT, "evogate.py"), "demo", "--workdir", d],
                capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertIn("champion: v2-grounded.md (score 1.0)", res.stdout)
            entries = evogate.read_ledger(d)
            self.assertEqual(len(entries), 3)
            verdicts = [e["verdict"] for e in entries]
            self.assertEqual(verdicts, ["rejected", "promoted", "rejected"])
            self.assertIn("critical", entries[0]["reason"])
            self.assertIn("critical", entries[2]["reason"])
            state = evogate.load_state(d)
            self.assertEqual(state["champion"]["variant"], "v2-grounded.md")


if __name__ == "__main__":
    unittest.main()
