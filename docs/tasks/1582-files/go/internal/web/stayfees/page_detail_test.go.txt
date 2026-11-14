package stayfees

// Route tests of the stay fee detail page (brief 1582) on PostgreSQL. The
// environment and the made-up fixtures come from page_list_test.go.

import (
	"net/http"
	"strings"
	"testing"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

func TestPageDetailPage(t *testing.T) {
	e := newPageEnv(t)

	// Byt B in October: ready to save, guests with their facts and decisions, corrections.
	body := pgOk(t, "detail", e.get(1, "/stay-fees/12?month=2026-10&lang=en"))
	pgHas(t, "detail", body,
		"Byt B ("+pgText("month.10")+" 2026)",
		pgText("stay_fees.metric.liable"), pgText("stay_fees.metric.vs"), `class="metric-value small-value mono">12<`,
		// the save form with the collected amounts, no blockers
		`action="/stay-fees/12/finalize"`, `name="confirm_collected" value="1"`, `name="collected_1" value="200"`,
		pgText("stay_fees.save_period"),
		// guests: names, facts (born, age, country), the status badges, decisions
		`href="/reservations/1"`, "Jan Novak", `data-fee-guest-facts`, "01.01.1980", pgText("stay_fees.guest.age", "age", 46), "Germany",
		pgText("stay_fees.status.liable"), pgText("stay_fees.status.under_18"),
		pgText("stay_fees.hint.local_resident"), pgText("stay_fees.label.obec_resident"), `id="obec-1"`,
		`action="/stay-fees/guest-decision"`, `name="guest_id" value="3"`, `name="apartment_id" value="12"`, `name="month" value="2026-10"`,
		`name="decision" value="exempt"`, `name="decision" value="charge"`,
		// the charge decision of guest 3 can be cleared; the exempt categories are listed
		pgText("stay_fees.decision.auto"), pgText("stay_fees.exempt.disability"),
		// payment is not saved yet; the adjustment form, the open correction with its undo
		pgText("stay_fees.payment.incomplete"), `id="fee-adjust"`, `action="/stay-fees/12/adjustment"`,
		"3 "+pgText("stay_fees.adjust.bed_days")+" (sample reason)", "-1 "+pgText("stay_fees.adjust.bed_days")+" (sealed reason)", `action="/stay-fees/12/adjustment/1/undo"`,
		// the month filter of the toolbar and the way back
		`action="/stay-fees/12"`, `value="2026-10"`, `href="/stay-fees?month=2026-10"`, pgText("stay_fees.back"),
	)
	pgLacks(t, "detail", body, `id="fee-blockers"`, `id="fee-send"`, `id="fee-records"`, `id="fee-account"`,
		`action="/stay-fees/12/adjustment/2/undo"`, `name="correct"`, "Provozovatel")
	// An auto minor and a local resident need a reason before a decision is taken.
	if n := strings.Count(body, `aria-label="`+pgText("stay_fees.decision.reason_label")+`" required>`); n != 2 {
		t.Errorf("review guests with a required reason: %d, want 2 (the minor and the local resident)", n)
	}

	// Byt F: blockers with their fix links and the scope ruling form.
	body = pgOk(t, "blockers", e.get(1, "/stay-fees/18?month=2026-10&lang=en"))
	pgHas(t, "blockers", body, `id="fee-blockers"`, pgText("stay_fees.blockers.title"),
		pgText("stay_fees.issue.no_vs"), pgText("stay_fees.issue.no_authority"), pgText("stay_fees.issue.no_payer"), pgText("stay_fees.issue.unsigned"),
		pgText("stay_fees.issue.scope_ruling"),
		`href="/apartments/18?view=settings&amp;section=reporting&amp;return_to=%2Fstay-fees%2F18%3Fmonth%3D2026-10#stay-fee-settings"`,
		`href="/apartments/18?view=settings&amp;section=property&amp;return_to=%2Fstay-fees%2F18%3Fmonth%3D2026-10#settings-property"`,
		pgText("host.fix_details"),
		`action="/stay-fees/18/scope-ruling"`, `name="rule"`, `name="reference"`,
		`<button class="ui-btn ui-btn-secondary" type="button" disabled>`)
	pgLacks(t, "blockers", body, `action="/stay-fees/18/finalize"`)

	// Byt Q: only the running quarter blocks.
	body = pgOk(t, "running", e.get(1, "/stay-fees/17?month=2026-10&lang=en"))
	pgHas(t, "running", body, pgText("stay_fees.issue.period_running"), pgText("stay_fees.quarter", "n", 4, "year", 2026))
	pgLacks(t, "running", body, pgText("stay_fees.issue.no_payer"))

	// Byt E in September: the sealed filing. Download links, the send panel, the payment with its QR, the records.
	body = pgOk(t, "frozen", e.get(1, "/stay-fees/15?month=2026-09&lang=en"))
	pgHas(t, "frozen", body,
		pgText("stay_fees.saved_version", "version", 1),
		`href="/stay-fees/15/csv?month=2026-09"`, `href="/stay-fees/15/pdf?month=2026-09"`, `href="/stay-fees/15?month=2026-09&correct=1"`,
		`id="fee-send"`, `value="Authority 15 (box15)"`, `id="fee-send-databox"`,
		`value="Ohlášení poplatku z pobytu – Září 2026 – Byt E"`,
		"Provozovatel Test s.r.o., IČO 12345678", "Částka k úhradě: 500\u00a0Kč. Podrobnosti v příloze.",
		pgText("stay_fees.payment.ready"), `id="fee-account"`, `value="19-2000145399/0800"`, `value="CZ6508000000192000145399"`,
		`src="data:image/png;base64,`, "SPD*1.0*ACC:CZ6508000000192000145399*AM:500.00*CC:CZK",
		`id="fee-records"`, `action="/stay-fees/15/filings/1/sent"`, `action="/stay-fees/15/filings/1/paid"`,
		// the sealed line, with the guest's facts read from the guest row
		"Eva Frozen", "05.05.1975", pgText("stay_fees.guest.age", "age", 51), "Austria", `name="guest_id" value="9001"`,
	)
	pgLacks(t, "frozen", body, `id="fee-adjust"`, `action="/stay-fees/15/finalize"`)

	// Correcting a sealed period: the live period again, saved with correct=1.
	body = pgOk(t, "correcting", e.get(1, "/stay-fees/15?month=2026-09&correct=1&lang=en"))
	pgHas(t, "correcting", body, `action="/stay-fees/15/finalize"`, `name="correct" value="1"`, `id="fee-adjust"`)
	pgLacks(t, "correcting", body, `id="fee-send"`, `id="fee-records"`)
}

func TestPageDetailRefusals(t *testing.T) {
	e := newPageEnv(t)
	// Another host's property, a missing one, a text id.
	for _, target := range []string{"/stay-fees/20?month=2026-10", "/stay-fees/999", "/stay-fees/99999999999999999999"} {
		rec := e.get(1, target)
		if rec.Code != http.StatusNotFound || strings.TrimSpace(rec.Body.String()) != `{"detail":"Not Found"}` {
			t.Errorf("%s: %d %q", target, rec.Code, rec.Body.String())
		}
	}
	rec := e.get(1, "/stay-fees/abc")
	if rec.Code != http.StatusUnprocessableEntity {
		t.Errorf("text id: %d", rec.Code)
	}
	// FastAPI checks the path before the login guard.
	rec = e.get(0, "/stay-fees/abc")
	if rec.Code != http.StatusUnprocessableEntity {
		t.Errorf("text id signed out: %d", rec.Code)
	}
	rec = e.get(0, "/stay-fees/12")
	if rec.Code != http.StatusSeeOther || rec.Header().Get("Location") != "/login?next=/stay-fees/12" {
		t.Errorf("signed out: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	// A month after the current one goes to the default month.
	rec = e.get(1, "/stay-fees/12?month=2027-05")
	if rec.Code != http.StatusSeeOther || rec.Header().Get("Location") != "/stay-fees/12?month=2026-11" {
		t.Errorf("future month: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	// A bad month falls back to the default month.
	body := pgOk(t, "bad month", e.get(1, "/stay-fees/12?month=junk&lang=en"))
	pgHas(t, "bad month", body, "Byt B ("+pgText("month.11")+" 2026)")
	// A property with no fee and no sealed filing: back to the list with the error.
	rec = e.get(1, "/stay-fees/14?month=2026-10&lang=en")
	loc := rec.Header().Get("Location")
	if rec.Code != http.StatusSeeOther || !strings.HasPrefix(loc, "/stay-fees?err=") {
		t.Errorf("no fee: %d %q", rec.Code, loc)
	}
}

func TestPageGuestIdentityVisible(t *testing.T) {
	host := func(role string, imp bool, rv ...any) *call {
		return &call{h: &session.Host{Account: session.Account{Role: role}, Impersonating: imp, Payload: map[string]any{"rv": rv}}}
	}
	for _, c := range []struct {
		name string
		call *call
		want bool
	}{
		{"own workspace", host("host", false), true},
		{"admin impersonating", host("admin", true), true},
		{"revealed guest", host("host", true, float64(7)), true},
		{"other guest", host("host", true, float64(8)), false},
		{"nothing revealed", host("host", true), false},
	} {
		if got := pgGuestIdentityVisible(c.call, 7); got != c.want {
			t.Errorf("%s: %v, want %v", c.name, got, c.want)
		}
	}
}

func TestPageDetailHelpers(t *testing.T) {
	if d, ok := pgParseBirthDate("01011980"); !ok || d.Year() != 1980 {
		t.Error("pgParseBirthDate full date")
	}
	for _, bad := range []string{"", "0101198", "00011980", "31022000", "0101198x", "+1011980"} {
		if _, ok := pgParseBirthDate(bad); ok {
			t.Errorf("pgParseBirthDate(%q) accepted", bad)
		}
	}
	for in, want := range map[string]string{"01011980": "01.01.1980", "1.1.1980": "01.01.1980", " 0000 ": "0000"} {
		if got := pgDisplayBirthDate(in); got != want {
			t.Errorf("pgDisplayBirthDate(%q) = %q, want %q", in, got, want)
		}
	}
}
