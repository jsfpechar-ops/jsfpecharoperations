#!/usr/bin/env python3
"""Check that Go has a handler for every Python route Caddy would send to it.

  python3 scripts/go_parity_check.py --paths "/login /signup /account/*"
  python3 scripts/go_parity_check.py --paths-file paths.txt     # whitespace separated
  python3 scripts/go_parity_check.py --all --json out.json       # whole matrix, never fails

For each UBYHOST_GO_PATHS entry (Caddy `path` matcher, see caddy_match: exact,
trailing * = prefix, otherwise Go path.Match) it finds the Python routes (METHOD /path)
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


def _class_char(pattern, i):
    """One class character at i (Go path.Match getEsc) and the index after it."""
    if i >= len(pattern) or pattern[i] in "-]":
        return None, i
    if pattern[i] == "\\":
        i += 1
        if i >= len(pattern):
            return None, i
    return pattern[i], i + 1


def _glob_regex(pattern):
    """Go path.Match as a regular expression; None for a pattern Go rejects.

    `*` is any run of characters other than `/`, `?` one such character, `[...]`
    and `[^...]` a class of characters and ranges (a class can match `/`), and a
    backslash escapes the next character.
    """
    out, i, n = [], 0, len(pattern)
    while i < n:
        c = pattern[i]
        i += 1
        if c == "*":
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        elif c == "\\":
            if i == n:
                return None
            out.append(re.escape(pattern[i]))
            i += 1
        elif c == "[":
            cls, items = "[", 0
            if i < n and pattern[i] == "^":
                cls, i = "[^", i + 1
            while i == n or pattern[i] != "]" or not items:
                lo, i = _class_char(pattern, i)
                if lo is None:
                    return None
                hi = lo
                if i < n and pattern[i] == "-":
                    hi, i = _class_char(pattern, i + 1)
                    if hi is None or hi < lo:
                        return None
                cls += re.escape(lo) + ("-" + re.escape(hi) if hi != lo else "")
                items += 1
            out.append(cls + "]")
            i += 1
        else:
            out.append(re.escape(c))
    return "".join(out)


def caddy_match(entry, sample):
    """Caddy's `path` matcher for one entry (caddyhttp MatchPath; no `%` escapes).

    Case-insensitive. `*` alone matches everything; `*x*`, `*x` and `x*` are
    substring, suffix and prefix matches when those are the only stars; every
    other entry is Go path.Match, so `/reservations/*[0-9]` is one path segment
    ending in a digit. Caddy also cleans the request path (keeping a trailing
    slash); the samples here are already clean.
    """
    e, s = entry.lower(), sample.lower()
    if "%" in e:
        raise ValueError(f"{entry}: % escapes are not supported")
    if e == "*":
        return True
    stars = e.count("*")
    if stars == 2 and e.startswith("*") and e.endswith("*"):
        return e[1:-1] in s
    if stars == 1 and e.startswith("*"):
        return s.endswith(e[1:])
    if stars == 1 and e.endswith("*"):
        return s.startswith(e[:-1])
    pat = _glob_regex(e)
    return pat is not None and re.fullmatch(pat, s) is not None


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
