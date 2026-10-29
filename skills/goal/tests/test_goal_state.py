"""Portable goal lifecycle smoke tests. Run: python -m unittest discover -s skills/goal/tests"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "goal_state.py"

class GoalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = dict(os.environ, AGENT_SKILLS_GOAL_STATE_DIR=self.tmp.name)
        for k in ("CODEX_THREAD_ID","CLAUDE_SESSION_ID","AGENT_SKILLS_GOAL_THREAD_ID"):
            self.env.pop(k, None)

    def run_goal(self, *args, tid="alpha", success=True):
        proc = subprocess.run([sys.executable,str(SCRIPT),"--thread-id",tid,*args],
                              env=self.env,capture_output=True,text=True)
        if success:
            self.assertEqual(proc.returncode,0,proc.stderr)
            return json.loads(proc.stdout)
        self.assertNotEqual(proc.returncode,0,proc.stdout)
        return proc.stderr

    def test_isolation(self):
        self.run_goal("create","--objective","first")
        self.run_goal("create","--objective","second",tid="beta")
        self.assertEqual(self.run_goal("show")["objective"],"first")
        self.assertEqual(self.run_goal("show",tid="beta")["objective"],"second")
        self.assertIn("unfinished",self.run_goal("create","--objective","wrong",success=False))
        self.assertIn("Explicit",self.run_goal("clear",success=False))
        self.run_goal("clear","--user-requested")

    def test_blocker_and_resume(self):
        self.run_goal("create","--objective","verify")
        for turn in ("1","2"):
            self.run_goal("checkpoint","--turn-id",turn,"--kind","no-progress","--blocker","missing","--evidence","rechecked")
        self.assertIn("three",self.run_goal("status","blocked",success=False))
        self.run_goal("checkpoint","--turn-id","3","--kind","no-progress","--blocker","missing","--evidence","rechecked")
        self.assertEqual(self.run_goal("status","blocked")["status"],"blocked")
        self.assertIn("Explicit",self.run_goal("status","active",success=False))
        self.assertEqual(self.run_goal("status","active","--user-requested")["blocker_streak"],0)

    def test_wait_pause_and_audit(self):
        self.run_goal("create","--objective","verify")
        self.assertIn("handle",self.run_goal("checkpoint","--turn-id","1","--kind","verified-wait","--evidence","check",success=False))
        self.run_goal("checkpoint","--turn-id","1","--kind","verified-wait","--handle","job1","--evidence","live")
        self.assertIn("already recorded",self.run_goal("checkpoint","--turn-id","1","--kind","progress","--evidence","x",success=False))
        self.run_goal("status","paused","--user-requested")
        self.run_goal("status","active","--user-requested")
        audit = Path(self.tmp.name)/"audit.json"
        audit.write_text(json.dumps({"requirements":[{"requirement":"verify","status":"missing","source":"test","evidence":"no"}]}))
        self.assertIn("not proven",self.run_goal("status","complete","--audit",str(audit),success=False))
        audit.write_text(json.dumps({"requirements":[{"requirement":"verify","status":"proven","source":"test","evidence":"yes"}]}))
        self.assertEqual(self.run_goal("status","complete","--audit",str(audit))["status"],"complete")

if __name__ == "__main__":
    unittest.main()
