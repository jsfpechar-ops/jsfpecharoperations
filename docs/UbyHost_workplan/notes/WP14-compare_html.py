import re, sys
from pathlib import Path
a, b = Path(sys.argv[1]), Path(sys.argv[2])
def norm(t):
    t = re.sub(r'(name="csrf-token" content=")[^"]*', r'\1X', t)
    t = re.sub(r'(name="_csrf" value=")[^"]*', r'\1X', t)
    t = re.sub(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\+00:00)?', 'TS', t)
    return t
bad = 0
for f in sorted(a.glob("*.html")):
    x, y = norm(f.read_text()), norm((b / f.name).read_text())
    if x != y:
        bad += 1
        import difflib
        print("DIFF", f.name); print("".join(list(difflib.unified_diff(x.splitlines(1), y.splitlines(1), n=0))[:20]))
print("files", len(list(a.glob("*.html"))), "differing", bad)
