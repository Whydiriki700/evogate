#!/usr/bin/env python3
"""evogate: agent evolution with a fail closed quality gate.

Prompt variants compete on a fixed task suite. A variant is promoted to
champion only when it beats the current champion's score AND passes every
critical task in full. Ties, lower scores, and critical failures are
rejected. Every tournament is appended to a public ledger, kept or
rejected, with the reason.

Zero dependencies. Python 3.9+.
"""

import argparse
import json
import os
import subprocess
import sys
import time

STATE_FILE = "evogate-state.json"
LEDGER_FILE = "evogate-ledger.jsonl"


# ---------- scoring ----------

def score_answer(answer, checks):
    """Return (passed, total, failures) for one answer against its checks."""
    failures = []
    total = 0
    passed = 0
    low = answer.lower()
    for needle in checks.get("contains_all", []):
        total += 1
        if needle.lower() in low:
            passed += 1
        else:
            failures.append("missing: " + needle)
    for group in checks.get("contains_any", []):
        total += 1
        if any(n.lower() in low for n in group):
            passed += 1
        else:
            failures.append("missing any of: " + ", ".join(group))
    for needle in checks.get("not_contains", []):
        total += 1
        if needle.lower() not in low:
            passed += 1
        else:
            failures.append("forbidden present: " + needle)
    if "max_chars" in checks:
        total += 1
        if len(answer) <= int(checks["max_chars"]):
            passed += 1
        else:
            failures.append("too long: {0} > {1} chars".format(len(answer), checks["max_chars"]))
    return passed, total, failures


def run_variant(runner_cmd, variant_path, suite):
    """Run one variant over the whole suite. Runner errors score zero: fail closed."""
    per_task = []
    total_passed = 0
    total_checks = 0
    critical_failures = []
    for task in suite["tasks"]:
        cmd = runner_cmd.replace("{variant}", variant_path).replace("{input}", task["input"])
        try:
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
            answer = proc.stdout.strip() if proc.returncode == 0 else ""
        except (OSError, subprocess.SubprocessError):
            answer = ""
        passed, total, failures = score_answer(answer, task.get("checks", {}))
        total_passed += passed
        total_checks += total
        ok = total > 0 and passed == total
        if task.get("critical") and not ok:
            critical_failures.append(task["id"])
        per_task.append({"task": task["id"], "passed": passed, "total": total,
                         "failures": failures})
    score = (total_passed / total_checks) if total_checks else 0.0
    return {"score": round(score, 4), "per_task": per_task,
            "critical_failures": critical_failures}


# ---------- gate ----------

def gate(candidate, champion):
    """Fail closed promotion rule. Returns (promoted, reason)."""
    if candidate["critical_failures"]:
        return False, "critical task(s) failed: " + ", ".join(candidate["critical_failures"])
    if champion is None:
        return True, "first champion (no incumbent)"
    if candidate["score"] > champion["score"]:
        return True, "score {0} beats champion {1}".format(candidate["score"], champion["score"])
    if candidate["score"] == champion["score"]:
        return False, "tie with champion ({0}); ties do not promote".format(champion["score"])
    return False, "score {0} below champion {1}".format(candidate["score"], champion["score"])


# ---------- state and ledger ----------

def load_state(workdir):
    path = os.path.join(workdir, STATE_FILE)
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return {"champion": None, "generation": 0}


def save_state(workdir, state):
    with open(os.path.join(workdir, STATE_FILE), "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2)


def append_ledger(workdir, entry):
    with open(os.path.join(workdir, LEDGER_FILE), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def read_ledger(workdir):
    path = os.path.join(workdir, LEDGER_FILE)
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


# ---------- tournament ----------

def tournament(workdir, suite, variant_paths, runner_cmd):
    state = load_state(workdir)
    champion = state["champion"]
    results = []
    for variant_path in variant_paths:
        state["generation"] += 1
        result = run_variant(runner_cmd, variant_path, suite)
        candidate = {"variant": os.path.basename(variant_path), "score": result["score"]}
        promoted, reason = gate(
            {"score": result["score"], "critical_failures": result["critical_failures"]},
            champion)
        entry = {
            "generation": state["generation"],
            "time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "variant": candidate["variant"],
            "score": result["score"],
            "champion_before": champion["variant"] if champion else None,
            "champion_score_before": champion["score"] if champion else None,
            "verdict": "promoted" if promoted else "rejected",
            "reason": reason,
            "critical_failures": result["critical_failures"],
            "per_task": result["per_task"],
        }
        append_ledger(workdir, entry)
        if promoted:
            champion = candidate
            state["champion"] = champion
        results.append(entry)
    save_state(workdir, state)
    return results


# ---------- CLI ----------

def cmd_run(args):
    with open(args.suite, encoding="utf-8") as fh:
        suite = json.load(fh)
    variants = []
    if os.path.isdir(args.variants):
        variants = [os.path.join(args.variants, f)
                    for f in sorted(os.listdir(args.variants)) if f.endswith(".md")]
    elif os.path.isfile(args.variants):
        variants = [args.variants]
    if not variants:
        print("evogate: no variant files found", file=sys.stderr)
        return 2
    results = tournament(args.workdir, suite, variants, args.runner)
    for e in results:
        print("gen {generation}: {variant} score {score} -> {verdict} ({reason})".format(**e))
    state = load_state(args.workdir)
    champ = state["champion"]
    print("champion: {0} (score {1})".format(champ["variant"], champ["score"]) if champ
          else "champion: none")
    return 0


def cmd_ledger(args):
    for e in read_ledger(args.workdir):
        print("gen {generation}: {variant} score {score} -> {verdict} ({reason})".format(**e))
    return 0


def cmd_demo(args):
    here = os.path.dirname(os.path.abspath(__file__))
    demo_dir = os.path.join(here, "demo")
    workdir = args.workdir
    for name in (STATE_FILE, LEDGER_FILE):
        path = os.path.join(workdir, name)
        if os.path.exists(path):
            os.remove(path)
    runner = '"{0}" "{1}" "{{variant}}" "{{input}}"'.format(
        sys.executable, os.path.join(demo_dir, "agent.py"))
    ns = argparse.Namespace(
        suite=os.path.join(demo_dir, "tasks.json"),
        variants=os.path.join(demo_dir, "variants"),
        runner=runner, workdir=workdir)
    return cmd_run(ns)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="evogate",
                                     description="Agent evolution with a fail closed quality gate.")
    sub = parser.add_subparsers(dest="command", required=True)
    run_p = sub.add_parser("run", help="Run a tournament over a variants directory.")
    run_p.add_argument("--suite", required=True, help="Task suite JSON file.")
    run_p.add_argument("--variants", required=True, help="Variant file or directory of .md files.")
    run_p.add_argument("--runner", required=True,
                       help="Command template with {variant} and {input} placeholders.")
    run_p.add_argument("--workdir", default=".", help="Where state and ledger live.")
    run_p.set_defaults(func=cmd_run)
    led_p = sub.add_parser("ledger", help="Print the ledger.")
    led_p.add_argument("--workdir", default=".")
    led_p.set_defaults(func=cmd_ledger)
    demo_p = sub.add_parser("demo", help="Run the built in offline demo tournament.")
    demo_p.add_argument("--workdir", default=".")
    demo_p.set_defaults(func=cmd_demo)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
