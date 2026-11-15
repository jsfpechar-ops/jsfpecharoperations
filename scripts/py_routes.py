#!/usr/bin/env python3
"""List every Python (FastAPI) route as 'METHOD /path', read from source with ast.

Used by scripts/go_parity_check.py. No imports of the app, so it needs no venv.
Resolves module-level string constants and simple f-strings; the 6
/settings/<group> loop routes are added by hand (admin.py adds them in a loop).
"""
import ast
import glob
import json
import os
import sys

HTTP = {"get", "post", "put", "delete", "patch", "head"}
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "App", "app")


def consts(tree):
    out = {}
    for n in tree.body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            v = text(n.value, out)
            if v is not None:
                out[n.targets[0].id] = v
    return out


def text(node, env):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return env.get(node.id)
    if isinstance(node, ast.JoinedStr):
        parts = []
        for p in node.values:
            if isinstance(p, ast.Constant):
                parts.append(str(p.value))
            elif isinstance(p, ast.FormattedValue):
                v = text(p.value, env)
                if v is None:
                    return None
                parts.append(v)
        return "".join(parts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        a, b = text(node.left, env), text(node.right, env)
        return a + b if a is not None and b is not None else None
    return None


def routes():
    found = set()
    files = sorted(glob.glob(os.path.join(ROOT, "routes", "*.py"))) + [os.path.join(ROOT, "main.py")]
    for f in files:
        tree = ast.parse(open(f, encoding="utf-8").read())
        env = consts(tree)
        for n in ast.walk(tree):
            if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for d in n.decorator_list:
                if not (isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)):
                    continue
                if not d.args:
                    continue
                p = text(d.args[0], env)
                if p is None or not p.startswith("/"):
                    continue
                m = d.func.attr
                if m in HTTP:
                    found.add((m.upper(), p))
                elif m == "api_route":
                    for kw in d.keywords:
                        if kw.arg == "methods" and isinstance(kw.value, (ast.List, ast.Tuple)):
                            for e in kw.value.elts:
                                if isinstance(e, ast.Constant):
                                    found.add((str(e.value).upper(), p))
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "add_api_route" and n.args:
                p = text(n.args[0], env)
                if p and p.startswith("/"):
                    methods = ["GET"]
                    for kw in n.keywords:
                        if kw.arg == "methods" and isinstance(kw.value, (ast.List, ast.Tuple)):
                            methods = [str(e.value).upper() for e in kw.value.elts if isinstance(e, ast.Constant)]
                    for m in methods:
                        found.add((m, p))
    for g in ("account", "security", "phone", "data", "technical", "help"):
        found.add(("GET", "/settings/" + g))
    return sorted(found, key=lambda x: (x[1], x[0]))


if __name__ == "__main__":
    r = routes()
    if "--json" in sys.argv:
        json.dump([{"method": m, "path": p} for m, p in r], sys.stdout)
    else:
        for m, p in r:
            print(m, p)
        print(len(r), "routes", file=sys.stderr)
