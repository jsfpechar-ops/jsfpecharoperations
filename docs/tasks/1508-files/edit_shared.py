"""Brief 1508: the three edits of shared files, written to apply whatever
sibling briefs (1502-1510) already changed. Run from the repo root:

    python3 docs/tasks/1508-files/edit_shared.py

1. go/internal/web/auth/auth.go: append the GET /admin/operations row at the
   end of the Routes slice, after any rows other briefs added.
2. go/internal/web/auth/auth_test.go TestRoutesBuildWithoutPool: one route
   more than it counts now.
3. deploy/lightsail/docker-compose.yml, service ubyhost-go: the bare keys the
   page reads, each in alphabetical place among the bare UBYHOST_* keys.
Each edit refuses to run twice.
"""
import re
from pathlib import Path

# 1. Routes row.
p = Path("go/internal/web/auth/auth.go")
s = p.read_text(encoding="utf-8")
row = '\t\t{"GET /admin/operations", "/admin/operations", d.operationsAdmin},\n'
assert row not in s, "route row already there"
start = s.index("func Routes(")
end = s.index("\n\t}\n}\n", start)
p.write_text(s[:end + 1] + row + s[end + 1:], encoding="utf-8")
print("auth.go: route added")

# 2. Route count.
t = Path("go/internal/web/auth/auth_test.go")
src = t.read_text(encoding="utf-8")
pat = re.compile(r'if len\(seen\) != (\d+) \{\n\t\tt\.Errorf\("%d routes, want (\d+)", len\(seen\)\)')
m = pat.search(src)
assert m and m.group(1) == m.group(2), "route count anchor not found"
n = int(m.group(1)) + 1
src = src[:m.start()] + f'if len(seen) != {n} {{\n\t\tt.Errorf("%d routes, want {n}", len(seen))' + src[m.end():]
t.write_text(src, encoding="utf-8")
print(f"auth_test.go: route count {n - 1} -> {n}")

# 3. Compose keys (ubyhost-go only; a bare key passes the value through from .env when set).
NEW = ["UBYHOST_AI_MONTHLY_USD_HAVEL", "UBYHOST_AI_PRICE_CACHE_READ", "UBYHOST_AI_PRICE_CACHE_WRITE",
       "UBYHOST_AI_PRICE_INPUT", "UBYHOST_AI_PRICE_OUTPUT", "UBYHOST_DOOR_CODES_LIVE", "UBYHOST_TTLOCK_MONTHLY_CALLS"]
c = Path("deploy/lightsail/docker-compose.yml")
lines = c.read_text(encoding="utf-8").split("\n")
svc = lines.index("  ubyhost-go:")
env = next(i for i in range(svc + 1, len(lines)) if lines[i] == "    environment:")
stop = next(i for i in range(env + 1, len(lines)) if not lines[i].startswith("      "))
for key in NEW:
    bare = [i for i in range(env + 1, stop) if re.fullmatch(r"      UBYHOST_[A-Z0-9_]+:", lines[i])]
    names = {lines[i].strip()[:-1]: i for i in bare}
    assert key not in names and not any(lines[i].strip().startswith(key + ":") for i in range(env + 1, stop)), key + " already there"
    after = [i for i in bare if lines[i].strip()[:-1] < key]
    at = (after[-1] + 1) if after else bare[0]
    lines.insert(at, "      " + key + ":")
    stop += 1
c.write_text("\n".join(lines), encoding="utf-8")
print("docker-compose.yml: " + str(len(NEW)) + " keys added to ubyhost-go")
