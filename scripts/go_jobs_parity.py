#!/usr/bin/env python3
"""Fail unless Go registers every Python job kind with the same interval.

Python kinds: the keys of scheduler.job_intervals() plus 'billing' (scheduled
daily in scheduler.py but missing from that dict). Config-driven intervals
(ical, submit) are compared to their env defaults in App/app/config.py.
Run from the repo root: python3 scripts/go_jobs_parity.py [--allow-missing k1,k2]
"""
import ast
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def py_kinds():
    src = open(os.path.join(ROOT, "App/app/scheduler.py"), encoding="utf-8").read()
    cfg = open(os.path.join(ROOT, "App/app/config.py"), encoding="utf-8").read()
    default = lambda n: int(re.search(n + r'\s*=\s*int\(os\.environ\.get\("[A-Z_]+", "(\d+)"\)\)', cfg).group(1))
    tree = ast.parse(src)
    out = {}
    for f in ast.walk(tree):
        if isinstance(f, ast.FunctionDef) and f.name == "job_intervals":
            d = [n for n in ast.walk(f) if isinstance(n, ast.Dict)][0]
            for k, v in zip(d.keys, d.values):
                if isinstance(v, ast.Constant):
                    out[k.value] = v.value
                elif isinstance(v, ast.BinOp):
                    out[k.value] = eval(compile(ast.Expression(v), "x", "eval"))
                elif isinstance(v, ast.Attribute):
                    out[k.value] = default(v.attr)
    out.setdefault("billing", 24 * 60)
    return out


def go_kinds():
    with tempfile.TemporaryDirectory() as d:
        o = os.path.join(d, "jobs.json")
        env = dict(os.environ, GO_PROBE_JOBS_OUT=o)
        r = subprocess.run(["go", "test", "./cmd/ubyhost-web", "-run", "TestJobProbe", "-count=1"],
                           cwd=os.path.join(ROOT, "go"), env=env, capture_output=True, text=True)
        if r.returncode:
            sys.exit((r.stdout + r.stderr)[-2000:])
        return json.load(open(o))


def main():
    allow = set()
    if "--allow-missing" in sys.argv:
        allow = set(sys.argv[sys.argv.index("--allow-missing") + 1].split(","))
    py, go = py_kinds(), go_kinds()
    bad = 0
    for k in sorted(py):
        if k not in go:
            tag = "allowed" if k in allow else "FAIL"
            print(f"{tag} {k}: no Go job kind")
            bad += k not in allow
        elif go[k] != py[k]:
            print(f"FAIL {k}: interval Go {go[k]} min, Python {py[k]} min")
            bad += 1
        else:
            print(f"ok   {k} ({py[k]} min)")
    for k in sorted(set(go) - set(py)):
        print(f"note {k}: Go-only kind")
    print(f"{len(py)} Python kinds, {len(go)} Go kinds, {bad} failing")
    return 1 if bad else 0


sys.exit(main())
