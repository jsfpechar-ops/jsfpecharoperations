"""Build go/internal/web/guest/templates/form_content.tmpl from App guest form.html.

Mechanical Jinja→Go conversion for the check-in form body (brief 1723 step 3).
Run from repo root:

    python3 App/scripts/go_guest_form_template.py
    python3 App/scripts/go_guest_form_template.py --check
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FORM = REPO / "App/app/templates/guest/form.html"
PARTIALS = REPO / "App/app/templates/guest"
OUT = REPO / "go/internal/web/guest/templates/form_content.tmpl"

INCLUDE_RE = re.compile(r'\{%\s*include\s+[\'"]([^\'"]+)[\'"]\s*%\}')
SCRIPT_RE = re.compile(r"<script\b.*?</script>", re.S | re.I)


def expand_includes(text: str) -> str:
    for _ in range(12):
        m = INCLUDE_RE.search(text)
        if not m:
            break

        def repl(match: re.Match[str]) -> str:
            rel = match.group(1)
            path = PARTIALS / Path(rel).name
            if not path.exists():
                path = PARTIALS.parent / rel
            body = path.read_text(encoding="utf-8")
            body = expand_includes(body)
            return body

        text = INCLUDE_RE.sub(repl, text, count=1)
    return text


def strip_python_only(text: str) -> str:
    text = re.sub(r"\{%\s*extends\s+[^%]+%\}", "", text)
    text = re.sub(r"\{%\s*set\s+[^%]+%\}", "", text)
    text = re.sub(r"\{#.*?#\}", "", text, flags=re.S)
    text = SCRIPT_RE.sub("", text)
    text = re.sub(r"\{%\s*macro\s+.*?%\}.*?\{%\s*endmacro\s*%\}", "", text, flags=re.S)
    # content block only: from dup_warnings through end of checkin-main
    start = text.find("{% block content %}")
    if start >= 0:
        text = text[start + len("{% block content %}") :]
    end = text.rfind("{% endblock %}")
    if end >= 0:
        text = text[:end]
    return text


def jinja_to_go(text: str) -> str:
    reps = [
        (r"\{\{\s*t\('([^']+)'(?:,\s*[^)]+)?\)\s*\}\}", r'{{.T "\1"}}'),
        (r"\{\{\s*t\(\"([^\"]+)\"(?:,\s*[^)]+)?\)\s*\}\}", r'{{.T "\1"}}'),
        (r"\{\%\s*if\s+dup_warnings\s*\%\}", "{{if .DupWarnings}}"),
        (r"\{\%\s*for\s+item\s+in\s+dup_warnings\s*\%\}", "{{range .DupWarnings}}"),
        (r"\{\{\s*item\.name\s*\}\}", "{{.Name}}"),
        (r"\{\{\s*t\('dup_warning_body',\s*what=item\.what\)\s*\}\}", '{{$.T "dup_warning_body" "what" .What}}'),
        (r"\{\%\s*endif\s*\%\}", "{{end}}"),
        (r"\{\%\s*endfor\s*\%\}", "{{end}}"),
        (r"\{\%\s*if\s+back_url\s+and\s+not\s+\(can_pick_other\s+and\s+not\s+guest\)\s*\%\}", "{{if and .BackURL (not .HideBack)}}"),
        (r"\{\{\s*back_url\s*\}\}", "{{.BackURL}}"),
        (r"\{\%\s*if\s+issues\s*\|\s*selectattr\('is_error'\)\s*\|\s*list\s*\%\}", "{{if .HasErrors}}"),
        (r"\{\%\s*for\s+issue\s+in\s+issues\s+if\s+issue\.is_error\s*\%\}", "{{range .ErrorIssues}}"),
        (r"\{\{\s*issue\.message\s*\}\}", "{{.Message}}"),
        (r"\{\{\s*issue\.field\s*\}\}", "{{.Field}}"),
        (r"/l/\{\{\s*token\s*\}\}/\{\{\s*reservation\.id\s*\}\}/save\?lang=\{\{\s*lang\s*\}\}", '/l/{{.Token}}/{{.ReservationID}}/save?lang={{.Lang}}'),
        (r"\{\%\s*if\s+draft_url\s*\%\}", "{{if .DraftURL}}"),
        (r"\{\{\s*draft_url\s*\}\}", "{{.DraftURL}}"),
        (r"\{\{\s*draft_fields\s*\}\}", "{{.DraftFields}}"),
        (r"\{\{\s*draft_owned\s*\}\}", "{{.DraftOwned}}"),
        (r"\{\{\s*start_step\s*\|\s*default\(0\)\s*\}\}", "{{.StartStep}}"),
        (r"\{\%\s*if\s+guest\s*\%\}", "{{if .GuestID}}"),
        (r"\{\{\s*guest\.id\s*\}\}", "{{.GuestID}}"),
        (r"\{\{\s*values\.get\('stay_from'\)[^}]+\}\}", "{{.StayFromValue}}"),
        (r"\{\{\s*values\.get\('stay_to'\)[^}]+\}\}", "{{.StayToValue}}"),
        (r"\{\%\s*if\s+draft_restored\s*\%\}", "{{if .DraftRestored}}"),
        (r"\{\%\s*if\s+just_saved\s*\%\}", "{{if .JustSaved}}"),
        (r"\{\{\s*reservation\.date_from\s*\|\s*date_cz\s*\}\}", "{{.StayFromLabel}}"),
        (r"\{\{\s*reservation\.date_to\s*\|\s*date_cz\s*\}\}", "{{.StayToLabel}}"),
        (r"\{\{\s*nights_label\(reservation\.date_from,\s*reservation\.date_to\)\s*\}\}", "{{.NightsLabel}}"),
        (r"\{\%\s*if\s+person_number\s+and\s+expected_people\s*\%\}", "{{if and .PersonNumber .ExpectedPeople}}"),
        (r"\{\{\s*t\('person_progress',\s*current=person_number,\s*total=expected_people\)\s*\}\}", '{{.T "person_progress" "current" .PersonNumber "total" .ExpectedPeople}}'),
        (r"\{\%\s*if\s+dates_link\s*\%\}", "{{if .DatesLink}}"),
        (r"\{\{\s*dates_link\s*\}\}", "{{.DatesLink}}"),
        (r"\{\{\s*err_for\('([^']+)'\)\s*\}\}", r'{{$.ErrHTML "\1"}}'),
        (r"\{\{\s*bad\('([^']+)'\)\s*\}\}", r'{{$.FieldClass "\1"}}'),
        (r"\{\{\s*invalid\('([^']+)'\)\s*\}\}", r'{{$.FieldInvalid "\1"}}'),
        (r"\{\{\s*val\('([^']+)'\)(?:\s+if[^}]*)?\s*\}\}", r'{{$.Val "\1"}}'),
        (r"\{\{\s*display_birth_date\(val\('birth_date'\)\)\s*\}\}", '{{$.DisplayBirth ($.Val "birth_date")}}'),
        (r"\{\%\s*if\s+ask_party_size\s*\%\}", "{{if .AskPartySize}}"),
        (r"\{\{\s*values\.get\('party_size'\)\s+or\s+1\s*\}\}", '{{or (index $.Values "party_size") "1"}}'),
        (r"\{\%\s*for\s+group\s+in\s+country_groups\s*\%\}", "{{range .CountryGroups}}"),
        (r"\{\{\s*t\(group\.key\)\s*\}\}", '{{$.T .Key}}'),
        (r"\{\%\s*for\s+country\s+in\s+group\.options\s*\%\}", "{{range .Options}}"),
        (r"\{\{\s*country\.code\s*\}\}", "{{.Code}}"),
        (r"\{\{\s*country\.label\s*\}\}", "{{.Label}}"),
        (r"\{\%\s*if\s+val\('nationality'\)\s*==\s*country\.code\s*\%\}selected\{\%\s*endif\s*\%\}", '{{if eq ($.Val "nationality") .Code}}selected{{end}}'),
        (r"\{\%\s*for\s+purpose\s+in\s+purposes\s*\%\}", "{{range .Purposes}}"),
        (r"\{\{\s*purpose\.code\s*\}\}", "{{.Code}}"),
        (r"\{\{\s*purpose\.label\s*\}\}", "{{.Label}}"),
        (r"\{\%\s*if\s+\(val\('purpose'\)\s+or\s+default_purpose\)\s*==\s*purpose\.code\s*\%\}", '{{if eq ($.SelectedPurpose) .Code}}selected{{end}}'),
        (r"\{\{\s*val\('doc_number'\)\s+if\s+val\('doc_number'\)\s*!=\s*inpass\s+else\s*''\s*\}\}", '{{if ne ($.Val "doc_number") $.Inpass}}{{$.Val "doc_number"}}{{end}}'),
        (r"\{\%\s*if\s+residence_copied_from\s*\%\}", "{{if .ResidenceCopiedFrom}}"),
        (r"\{\{\s*residence_copied_from\s*\}\}", "{{.ResidenceCopiedFrom}}"),
        (r"\{\%\s*if\s+ruian_suggest_url\s*\%\}", "{{if .RuianSuggestURL}}"),
        (r"\{\%\s*if\s+require_passport\s*\%\}", "{{if .RequirePassport}}"),
        (r"\{\%\s*if\s+under15\s*\%\}", "{{if .Under15}}"),
        (r"\{\%\s*if\s+under15\s*==\s*false\s*\%\}", "{{if not .Under15}}"),
        (r"\{\{\s*values\.get\('signature'\)\s+or\s+stored_signature\s*\}\}", "{{.SignatureValue}}"),
        (r"\{\%\s*if\s+fee_estimate\s*\%\}", "{{if .FeeEstimate}}"),
        (r"\{\%\s*if\s+fee_panel\s*\%\}", "{{if .FeePanel}}"),
        (r"\{\{\s*t\(save_action_key\)\s*\}\}", "{{.SaveActionLabel}}"),
        (r"\{\{\s*csrf_token\s*\}\}", "{{.CSRFToken}}"),
        (r"\{\{\s*privacy_url\s*\}\}", "{{.PrivacyURL}}"),
        (r"\{\%\s*if\s+privacy_url\s*\%\}", "{{if .PrivacyURL}}"),
        (r"\{\%\s*if\s+ocr_available\s*\%\}", "{{if .OCRAvailable}}"),
        (r"\{\%\s*if\s+person_number\s+and\s+person_number\s*>\s*1\s*\%\}", "{{if gt .PersonNumber 1}}"),
        (r"\{\{\s*t\('person'\)\s*\}\}\s*\{\{\s*person_number\s*\}\}", '{{.T "person"}} {{.PersonNumber}}'),
        (r"\{\%\s*if\s+values\.get\('legal_ack'\)\s*\%\}checked\{\%\s*endif\s*\%\}", '{{if index .Values "legal_ack"}}checked{{end}}'),
        (r"\{\{\s*notice_version\s*\}\}", "{{.NoticeVersion}}"),
        (r"\{\%\s*if\s+apartment\.passport_photo_policy\s*==\s*'required_foreign'\s*\%\}", "{{if .RequirePassport}}"),
        (r"\{\%\s*if\s+fee_notice\s*\%\}", "{{if .FeeNotice}}"),
    ]
    for pat, repl in reps:
        text = re.sub(pat, repl, text)
    text = re.sub(r"\{\%\s*else\s*\%\}", "{{else}}", text)
    return text


def build() -> str:
    raw = FORM.read_text(encoding="utf-8")
    raw = expand_includes(raw)
    raw = strip_python_only(raw)
    body = jinja_to_go(raw)
    return '{{define "content"}}\n' + body.strip() + "\n{{end}}\n"


def main(argv: list[str]) -> int:
    check = "--check" in argv
    text = build()
    if check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != text:
            print(f"stale: {OUT}", file=sys.stderr)
            return 1
        return 0
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT} ({len(text.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))