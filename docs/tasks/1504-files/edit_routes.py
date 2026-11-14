# Brief 1504 step 2 (run from the repo root; not copied into the repo).
# Appends the three admin account rows as the last rows of Routes in auth.go,
# after any rows sibling briefs added, and raises the TestRoutesBuildWithoutPool
# count in auth_test.go by three from whatever it is now.
import re
from pathlib import Path

p = Path("go/internal/web/auth/auth.go")
s = p.read_text(encoding="utf-8")
rows = (
    '\t\t{"POST /admin/users", "/admin/users", d.userCreate},\n'
    '\t\t{"POST /admin/users/{id}/invite", "/admin/users/{id}/invite", d.userInvite},\n'
    '\t\t{"POST /admin/users/{id}/email", "/admin/users/{id}/email", d.userEmailSet},\n'
)
assert "d.userCreate" not in s and "d.userInvite" not in s and "d.userEmailSet" not in s, "rows already there"
start = s.index("func Routes(")
end = s.index("\n\t}\n}\n", start)
p.write_text(s[:end + 1] + rows + s[end + 1:], encoding="utf-8")
print("added 3 rows")

t = Path("go/internal/web/auth/auth_test.go")
src = t.read_text(encoding="utf-8")
pat = re.compile(r'if len\(seen\) != (\d+) \{\n\t\tt\.Errorf\("%d routes, want (\d+)", len\(seen\)\)')
m = pat.search(src)
assert m and m.group(1) == m.group(2), "route count anchor not found"
n = int(m.group(1)) + 3
src = src[:m.start()] + f'if len(seen) != {n} {{\n\t\tt.Errorf("%d routes, want {n}", len(seen))' + src[m.end():]
t.write_text(src, encoding="utf-8")
print(f"route count {n - 3} -> {n}")
