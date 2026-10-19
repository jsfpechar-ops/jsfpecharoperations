"""scripts/design_lint.py enforces docs/design/MASTER.md section 11.1."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "design_lint.py"

spec = importlib.util.spec_from_file_location("design_lint", SCRIPT)
design_lint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(design_lint)
CATALOG = json.loads((ROOT / "docs" / "design" / "catalog.json").read_text(encoding="utf-8"))


def test_the_repository_passes_the_design_lint():
    result = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stdout + result.stderr


def _t(text):
    return design_lint._findings_template(ROOT / "App/app/templates/x.html", text, CATALOG)


def test_template_rules_catch_each_kind_of_drift():
    assert any("T1" in f for f in _t('<div style="margin:0"></div>'))
    assert any("T1" in f for f in _t("<style>.a{}</style>"))
    assert any("T2" in f for f in _t('<p class="ui-sub">#fff</p>'))
    assert any("T3" in f for f in _t('<p class="panel"></p>'))
    assert any("T4" in f for f in _t('<a class="ui-btn ui-btn-primary"></a><a class="ui-btn ui-btn-primary"></a>'))
    assert any("T5" in f for f in _t('<svg><path d="M0 0"/></svg>'))
    assert _t('<a class="ui-btn ui-btn-primary">{{ t("x") }}</a><span class="sr-only"></span>') == []


def test_stylesheet_rules_catch_raw_values():
    s = design_lint._findings_stylesheet
    p = ROOT / "App/app/static/host2.css"
    assert any("S1" in f for f in s(p, ".a{color:#c85a52}"))
    assert any("S1" in f for f in s(p, ".a{font-family:Arial}"))
    assert any("S2" in f for f in s(p, ".a{padding:9px 14px;}"))
    assert s(p, ".a{padding:var(--space-2) var(--control-px);border:1px solid var(--line);margin:0;}") == []
