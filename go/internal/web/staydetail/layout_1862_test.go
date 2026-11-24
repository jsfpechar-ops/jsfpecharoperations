package staydetail

import (
	"strings"
	"testing"
)

func view1862(archived bool) View {
	v := fixedView()
	v.SendControls.SendEnabled = true
	if archived {
		v.Reservation.ArchivedAt = "2026-11-18T10:00:00"
	}
	return v
}

func TestLayout1862Both(t *testing.T) {
	for _, archived := range []bool{false, true} {
		out := renderStay(t, view1862(archived))
		for _, want := range []string{
			`host-stay-detail stay-layout`,
			`<span class="ph-only">`,
			`<span class="ph-hide">`,
			`<a class="row-menu-item ph-hide" href="/guide#guests"`,
			`class="card stay-rows"`,
			`action="/reservations/7/submit"`,
			`<a class="btn ghost ph-hide" href="/invoices/new?reservation_id=7">`,
			`<a class="row-menu-item ph-only" href="/invoices/new?reservation_id=7"`,
		} {
			if !strings.Contains(out, want) {
				t.Errorf("archived=%v: missing %s", archived, want)
			}
		}
		if strings.Contains(out, `class="list ph-hide"`) {
			t.Errorf("archived=%v: class=\"list ph-hide\" left", archived)
		}
		// The group follows #reports in the DOM; CSS order (step 10) shows it first.
		g, r, q := strings.Index(out, `id="guests"`), strings.Index(out, `id="reports"`), strings.Index(out, `id="stay-quick-edit"`)
		if g < 0 || r < 0 || q < 0 || g >= r || r >= q {
			t.Errorf("archived=%v: DOM order guests=%d reports=%d stay-quick-edit=%d", archived, g, r, q)
		}
		// An inactive (archived) stay hides Request payment, so only Stay settings has an icon.
		minIcons := 2
		if archived {
			minIcons = 1
		}
		if n := strings.Count(out, "stay-row-ic"); n < minIcons {
			t.Errorf("archived=%v: stay-row-ic %d times, want at least %d", archived, n, minIcons)
		}
	}
}

func TestLayout1862HandFilingInPoliceCard(t *testing.T) {
	v := view1862(false)
	v.HandFiling.Candidates = 2
	out := renderStay(t, v)
	police := strings.Index(out, `id="police-card"`)
	hand := strings.Index(out, `id="file-by-hand"`)
	reports := strings.Index(out, `class="stay-reports"`)
	if police < 0 || hand < 0 || reports < 0 {
		t.Fatalf("police-card=%d file-by-hand=%d stay-reports=%d", police, hand, reports)
	}
	end := strings.Index(out[reports:], "</section>")
	if end < 0 || hand <= police || hand >= reports+end {
		t.Errorf("file-by-hand at %d, want after police-card %d and before </section> %d", hand, police, reports+end)
	}
	if n := strings.Count(out, "stay-row-ic"); n < 3 {
		t.Errorf("stay-row-ic %d times, want 3", n)
	}
}

func TestLayout1862DisplayName(t *testing.T) {
	v := view1862(false)
	v.GuestRows[0].Guest.Row.FirstName = "TOMAS"
	v.GuestRows[0].Guest.Row.Surname = "NOVAK"
	out := renderStay(t, v)
	if !strings.Contains(out, `<span class="ph-only">TOMAS NOVAK</span><span class="ph-hide">Tomas Novak</span>`) {
		t.Error("H1: want TOMAS NOVAK in ph-only and Tomas Novak in ph-hide")
	}
	i := strings.Index(out, `<div class="crumb">`)
	if i < 0 {
		t.Fatal("no crumb")
	}
	crumb := out[i : i+strings.Index(out[i:], "</div>")]
	if !strings.Contains(crumb, "Tomas Novak") || strings.Contains(crumb, "TOMAS NOVAK") {
		t.Errorf("crumb: want Tomas Novak, got %q", crumb)
	}
}

func TestLayout1862Archived(t *testing.T) {
	markers := []string{` stay-archived`, `class="inline ph-hide stay-restore"`, `action="/reservations/7/unarchive"`, `stay-archived-banner`}
	archived := renderStay(t, view1862(true))
	normal := renderStay(t, view1862(false))
	for _, m := range markers {
		if !strings.Contains(archived, m) {
			t.Errorf("archived: missing %s", m)
		}
		if strings.Contains(normal, m) {
			t.Errorf("normal: unexpected %s", m)
		}
	}
}
