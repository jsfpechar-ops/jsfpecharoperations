package booking

// The static guest pages of property_page.py: GET /terms/booking
// (booking_terms_page, lines 31-35) and GET /p/{slug}/thanks
// (property_page_thanks, lines 570-577). Neither reads the database.

import "net/http"

// TermsHandler serves GET /terms/booking.
func TermsHandler() http.HandlerFunc {
	set := newSet("terms.tmpl")
	return func(w http.ResponseWriter, r *http.Request) {
		lang := pageLang(r)
		title := "Podmínky rezervace · UbyHost"
		if lang == "en" {
			title = "Booking terms · UbyHost"
		}
		writeGuest(w, r, set, http.StatusOK, Guest{Lang: lang, Title: title}, nil)
	}
}

// ThanksHandler serves GET /p/{slug}/thanks, Stripe's success_url. It shows
// no booking data.
func ThanksHandler() http.HandlerFunc {
	set := newSet("thanks.tmpl")
	return func(w http.ResponseWriter, r *http.Request) {
		g := Guest{Lang: pageLang(r), Data: struct{ Slug string }{r.PathValue("slug")}}
		g.Title = g.T("pp.book.done")
		writeGuest(w, r, set, http.StatusOK, g, map[string]string{"X-Robots-Tag": "noindex"})
	}
}
