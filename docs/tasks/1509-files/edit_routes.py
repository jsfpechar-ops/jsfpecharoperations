from pathlib import Path
p = Path("go/internal/web/auth/auth.go")
s = p.read_text(encoding="utf-8")
row = '\t\t{"POST /admin/users/{id}/schedule-deletion", "/admin/users/{id}/schedule-deletion", d.scheduleDeletion},\n'
assert row not in s, "row already there"
start = s.index("func Routes(")
end = s.index("\n\t}\n}\n", start)
p.write_text(s[:end + 1] + row + s[end + 1:], encoding="utf-8")
print("added")

# auth_test.go TestRoutesBuildWithoutPool: one route more than it counts now,
# whatever sibling briefs (1502-1508) already added.
import re

t = Path("go/internal/web/auth/auth_test.go")
src = t.read_text(encoding="utf-8")
pat = re.compile(r'if len\(seen\) != (\d+) \{\n\t\tt\.Errorf\("%d routes, want (\d+)", len\(seen\)\)')
m = pat.search(src)
assert m and m.group(1) == m.group(2), "route count anchor not found"
n = int(m.group(1)) + 1
src = src[:m.start()] + f'if len(seen) != {n} {{\n\t\tt.Errorf("%d routes, want {n}", len(seen))' + src[m.end():]
t.write_text(src, encoding="utf-8")
print(f"route count {n - 1} -> {n}")
