#!/usr/bin/env python3
"""Check that Go has a handler for every Python route Caddy would send to it.

  python3 scripts/go_parity_check.py --paths "/login /signup /account/*"
  python3 scripts/go_parity_check.py --paths-file paths.txt     # whitespace separated
  python3 scripts/go_parity_check.py --all --json out.json       # whole matrix, never fails

For each UBYHOST_GO_PATHS entry (Caddy `path` matcher: exact, trailing * = prefix,
other * = glob inside one segment) it finds the Python routes (METHOD /path)
that the entry catches, then asks the real Go mux (newMux, nil pool) whether it
serves each METHOD. A POST that Go lacks is a failure even when GET exists:
Caddy sends POST to Go too, and Go then answers 404 where Python would save.
Exit 1 on any missing handler or any entry that matches no Python route and no Go route.
Env-dependent Go registration is seen with the environment of this process.
"""
import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import py_routes  # noqa: E402

GO_DIR = os.path.join(HERE, "..", "go")
PARAM = re.compile(r"\{[^/}]*\}")


def caddy_match(entry, sample):
    e, s = entry.lower(), sample.lower()
    if "*" not in e:
        return e == s
    if e.endswith("*") and "*" not in e[:-1]:
        return s.startswith(e[:-1])
    pat = re.escape(e).replace(r"\*", "[^/]*")
    return re.fullmatch(pat, s) is not None


def probe(items):
    with tempfile.TemporaryDirectory() as d:
        i, o = os.path.join(d, "in.json"), os.path.join(d, "out.json")
        json.dump(items, open(i, "w"))
        env = dict(os.environ, GO_PROBE_IN=i, GO_PROBE_OUT=o)
        r = subprocess.run(["go", "test", "./cmd/ubyhost-web", "-run", "TestRouteProbe", "-count=1"],
                           cwd=GO_DIR, env=env, capture_output=True, text=True)
        if r.returncode != 0 or not os.path.exists(o):
            sys.exit("go probe failed:\n" + (r.stdout + r.stderr)[-2000:])
        out = json.load(open(o))
    allp = [[("{}" if "{" in x else x) for x in p.split("/")] for _, p in py_routes.routes()]
    for it, r in zip(items, out):
        r["shadow"] = False
        if r["handled"]:
            gp = r["pattern"].split(" ", 1)[-1].split("/")
            pp = [("{}" if "{" in x else x) for x in it["path"].split("/")]
            # Go {param} where Python has a literal segment, and Python has a
            # sibling route with a param there: Go's wildcard would catch a
            # different route (Go /apartments/{id}/guide/{item} catches Python
            # .../guide/questions, which is its own Python route).
            if len(gp) == len(pp):
                for i, (g, p) in enumerate(zip(gp, pp)):
                    if "{" in g and p != "{}" and any(len(q) > i and q[:i] == pp[:i] and q[i] == "{}" for q in allp):
                        r["handled"], r["shadow"] = False, True
                        break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--paths")
    ap.add_argument("--paths-file")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args()
    py = [{"method": m, "path": p} for m, p in py_routes.routes()]
    res = probe(py)
    handled = {(r["method"], r["path"]): r for r in res}
    if a.all:
        rows = [dict(r) for r in res]
        if a.json:
            json.dump(rows, open(a.json, "w"), indent=1)
        n = sum(1 for r in rows if r["handled"])
        print(f"{n}/{len(rows)} Python routes have a Go handler")
        return 0
    val = a.paths if a.paths is not None else (open(a.paths_file).read() if a.paths_file else None)
    if not val or not val.split():
        sys.exit("give --paths, --paths-file or --all")
    entries = val.replace('"', "").split()
    bad, rows = 0, []
    for e in entries:
        if e == "/__go_off__":
            continue
        caught = [r for r in py if caddy_match(e, PARAM.sub("1", r["path"]))]
        if not caught:
            extra = probe([{"method": "GET", "path": e.replace("*", "x")}])[0]
            if not extra["handled"]:
                print(f"FAIL {e}: matches no Python route and Go has no handler")
                bad += 1
            else:
                print(f"note {e}: no Python route; Go-only ({extra['pattern']})")
            continue
        for r in caught:
            h = handled[(r["method"], r["path"])]
            rows.append({"entry": e, **h})
            if not h["handled"]:
                why = "only a Go wildcard (%s) would catch it" % h["pattern"] if h.get("shadow") else "Go has no handler"
                print(f"FAIL {e}: {why} for {r['method']} {r['path']}")
                bad += 1
    if a.json:
        json.dump(rows, open(a.json, "w"), indent=1)
    print(f"{len(entries)} entries, {len(rows)} method/route pairs checked, {bad} missing")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
