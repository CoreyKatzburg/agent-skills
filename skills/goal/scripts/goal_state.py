#!/usr/bin/env python3
"""Per-thread fallback goal state. No automatic dispatch or token metering."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from datetime import datetime, timezone
from uuid import uuid4

def stamp():
    return datetime.now(timezone.utc).isoformat()

def root():
    if os.getenv("AGENT_SKILLS_GOAL_STATE_DIR"):
        return Path(os.environ["AGENT_SKILLS_GOAL_STATE_DIR"]).expanduser()
    if os.getenv("XDG_STATE_HOME"):
        return Path(os.environ["XDG_STATE_HOME"]) / "agent-skills" / "goals"
    if os.name == "nt" and os.getenv("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "agent-skills" / "goals"
    return Path.home() / ".local" / "state" / "agent-skills" / "goals"

def identity(arg, creating):
    for value in (arg, os.getenv("AGENT_SKILLS_GOAL_THREAD_ID"),
                  os.getenv("CODEX_THREAD_ID"), os.getenv("CLAUDE_SESSION_ID")):
        if value:
            return value
    if creating:
        return "portable-" + str(uuid4())
    raise ValueError("No session ID; use --thread-id or AGENT_SKILLS_GOAL_THREAD_ID")

def read(path):
    if not path.is_file():
        raise ValueError("No goal for this thread")
    with path.open(encoding="utf-8") as f:
        s = json.load(f)
    if s.get("schema_version") != 1:
        raise ValueError("Unsupported state version")
    return s

def save(path, s):
    path.parent.mkdir(parents=True, exist_ok=True)
    s["updated_at"] = stamp()
    fd, tmp = tempfile.mkstemp(prefix=".goal-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(s, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def audit(path):
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    items = doc.get("requirements")
    if not isinstance(items, list) or not items:
        raise ValueError("Audit needs a nonempty requirements list")
    for i, item in enumerate(items):
        if not isinstance(item, dict) or item.get("status") != "proven":
            raise ValueError("Requirement %s not proven" % (i+1))
        if any(not isinstance(item.get(k), str) or not item[k].strip()
               for k in ("requirement", "source", "evidence")):
            raise ValueError("Requirement %s lacks proof fields" % (i+1))
    return doc

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--thread-id")
    subs = p.add_subparsers(dest="command", required=True)
    c = subs.add_parser("create")
    c.add_argument("--objective", required=True)
    subs.add_parser("show")
    cp = subs.add_parser("checkpoint")
    cp.add_argument("--turn-id", required=True)
    cp.add_argument("--kind", choices=["progress","verified-wait","no-progress"], required=True)
    cp.add_argument("--evidence", required=True)
    cp.add_argument("--blocker")
    cp.add_argument("--handle")
    st = subs.add_parser("status")
    st.add_argument("value", choices=["active","paused","blocked","complete"])
    st.add_argument("--user-requested", action="store_true")
    st.add_argument("--audit")
    cl = subs.add_parser("clear")
    cl.add_argument("--user-requested", action="store_true")
    a = p.parse_args()
    try:
        tid = identity(a.thread_id, a.command == "create")
        path = root() / (hashlib.sha256(tid.encode()).hexdigest() + ".json")
        if a.command == "create":
            if not a.objective.strip():
                raise ValueError("Empty objective")
            if path.exists() and read(path)["status"] != "complete":
                raise ValueError("An unfinished goal exists")
            s = dict(schema_version=1, thread_id=tid, objective=a.objective.strip(),
                     status="active", created_at=stamp(), last_turn_id=None,
                     last_kind=None, blocker=None, blocker_streak=0, last_evidence=None, audit=None)
            save(path,s)
        else:
            s = read(path)
            if a.command == "checkpoint":
                if s["status"] != "active" or s["last_turn_id"] == a.turn_id:
                    raise ValueError("Goal not active or turn already recorded")
                if not a.evidence.strip():
                    raise ValueError("Evidence required")
                if a.kind == "no-progress" and not (a.blocker and a.blocker.strip()):
                    raise ValueError("Stable blocker required")
                if a.kind == "verified-wait" and not (a.handle and a.handle.strip()):
                    raise ValueError("Live handle required")
                if a.kind == "no-progress":
                    s["blocker_streak"] = s["blocker_streak"]+1 if s["last_kind"] == "no-progress" and s["blocker"] == a.blocker else 1
                    s["blocker"] = a.blocker
                else:
                    s["blocker_streak"], s["blocker"] = 0, None
                s["last_turn_id"], s["last_kind"], s["last_evidence"] = a.turn_id, a.kind, a.evidence
                if a.kind == "verified-wait":
                    s["last_live_handle"] = a.handle
                else:
                    s.pop("last_live_handle", None)
                save(path,s)
            elif a.command == "status":
                if a.value in ("active","paused") and not a.user_requested:
                    raise ValueError("Explicit user request required")
                if a.value == "active":
                    if s["status"] not in ("paused","blocked"):
                        raise ValueError("Only paused or blocked goals resume")
                    s.update(blocker=None, blocker_streak=0, last_kind=None)
                elif a.value == "paused":
                    if s["status"] != "active":
                        raise ValueError("Only active goals pause")
                elif a.value == "blocked":
                    if s["status"] != "active" or s["last_kind"] != "no-progress" or s["blocker_streak"] < 3:
                        raise ValueError("Blocked requires three consecutive same-blocker turns")
                elif a.value == "complete":
                    if s["status"] != "active" or not a.audit:
                        raise ValueError("Active goal and --audit required")
                    s["audit"] = audit(a.audit)
                s["status"] = a.value
                save(path,s)
            elif a.command == "clear":
                if not a.user_requested:
                    raise ValueError("Explicit user request required")
                path.unlink()
                s = dict(cleared=True, thread_id=tid)
        print(json.dumps(s,indent=2,ensure_ascii=False))
        return 0
    except (ValueError,OSError,json.JSONDecodeError) as error:
        print("goal_state: %s" % error,file=sys.stderr)
        return 2

if __name__ == "__main__":
    sys.exit(main())
