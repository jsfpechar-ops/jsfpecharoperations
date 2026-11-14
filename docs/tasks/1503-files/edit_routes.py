# Brief 1503 step 2 (run from the repo root; not copied into the repo).
# Appends the POST /login/2fa row as the last row of Routes in auth.go, after
# any rows sibling briefs added, and raises the TestRoutesBuildWithoutPool
# count in auth_test.go by one from whatever it is now.
import re
from pathlib import Path

p = Path("go/internal/web/auth/auth.go")
s = p.read_text(encoding="utf-8")
row = '\t\t{"POST /login/2fa", "/login/2fa", d.twoFactorLogin},\n'
assert row not in s, "row already there"
start = s.index("func Routes(")
end = s.index("\n\t}\n}\n", start)
p.write_text(s[:end + 1] + row + s[end + 1:], encoding="utf-8")
print("added 1 row")

t = Path("go/internal/web/auth/auth_test.go")
src = t.read_text(encoding="utf-8")
pat = re.compile(r'if len\(seen\) != (\d+) \{\n\t\tt\.Errorf\("%d routes, want (\d+)", len\(seen\)\)')
m = pat.search(src)
assert m and m.group(1) == m.group(2), "route count anchor not found"
n = int(m.group(1)) + 1
src = src[:m.start()] + f'if len(seen) != {n} {{\n\t\tt.Errorf("%d routes, want {n}", len(seen))' + src[m.end():]
t.write_text(src, encoding="utf-8")
print(f"route count {n - 1} -> {n}")
