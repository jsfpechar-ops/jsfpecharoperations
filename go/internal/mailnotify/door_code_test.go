package mailnotify

import (
	"encoding/json"
	"os"
	"strings"
	"testing"
)

// doorGolden is testdata/door_code_golden.json (App/scripts/go_mailnotify_doorcode_golden.py).
type doorGolden struct {
	PublicBaseURL string     `json:"public_base_url"`
	SupportEmail  string     `json:"support_email"`
	Cases         []doorCase `json:"cases"`
}

type doorCase struct {
	Name   string          `json:"name"`
	Kind   string          `json:"kind"`
	Input  json.RawMessage `json:"input"`
	Row    *doorRow        `json:"row"`
	Output json.RawMessage `json:"output"`
}

type doorRow struct {
	Apartment struct {
		ID            int64  `json:"id"`
		InternalName  string `json:"internal_name"`
		OwnerUserID   int64  `json:"owner_user_id"`
		LegalEntityID int64  `json:"legal_entity_id"`
		ContactEmail  string `json:"contact_email"`
	} `json:"apartment"`
	Reservation struct {
		ID          int64  `json:"id"`
		ApartmentID int64  `json:"apartment_id"`
		DateFrom    string `json:"date_from"`
	} `json:"reservation"`
}

type doorBuildInput struct {
	Lang         string       `json:"lang"`
	PropertyName string       `json:"property_name"`
	Checkin      string       `json:"checkin"`
	Checkout     string       `json:"checkout"`
	FirstUseBy   string       `json:"first_use_by"`
	Host         *Host        `json:"host"`
	Fee          *DoorCodeFee `json:"fee"`
}

type doorBuildOutput struct {
	Subject string `json:"subject"`
	Text    string `json:"text"`
	HTML    string `json:"html"`
	QRSpayd string `json:"qr_spayd"`
}

type doorNoticeInput struct {
	DoorCodeID int64   `json:"door_code_id"`
	Variant    string  `json:"variant"`
	KeySuffix  string  `json:"key_suffix"`
	LastError  string  `json:"last_error"`
	Pin        *string `json:"pin"`
}

type doorMailOutput struct {
	Kind           string  `json:"kind"`
	IdempotencyKey string  `json:"idempotency_key"`
	ToEmail        string  `json:"to_email"`
	Subject        string  `json:"subject"`
	CCEmail        *string `json:"cc_email"`
	Payload        struct {
		Text string `json:"text"`
		HTML string `json:"html"`
		Lang string `json:"lang"`
	} `json:"payload"`
}

type doorDelayedInput struct {
	ReservationID int64  `json:"reservation_id"`
	Reason        string `json:"reason"`
}

func loadDoorGolden(t *testing.T) doorGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/door_code_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var g doorGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	if len(g.Cases) == 0 {
		t.Fatal("door_code_golden.json has no cases")
	}
	return g
}

func TestDoorCodeGolden(t *testing.T) {
	g := loadDoorGolden(t)
	// The generator ran with UBYHOST_GUEST_LANGS=en,cs,de,es,fr,uk; restore the default after.
	SetGuestLanguages("en,cs,de,es,fr,uk")
	defer SetGuestLanguages(strings.Join(catalogue.GuestDefaultLanguages, ","))
	env := DoorCodeMailEnv{AppBaseURL: g.PublicBaseURL, PublicBaseURL: g.PublicBaseURL, SupportEmail: g.SupportEmail}
	for _, c := range g.Cases {
		t.Run(c.Name, func(t *testing.T) {
			switch c.Kind {
			case "build":
				replayDoorBuild(t, env, c)
			case "notice":
				replayDoorNotice(t, env, c)
			case "delayed":
				replayDoorDelayed(t, env, c)
			default:
				t.Fatalf("unknown kind %q", c.Kind)
			}
		})
	}
}

func replayDoorBuild(t *testing.T, env DoorCodeMailEnv, c doorCase) {
	var in doorBuildInput
	var want doorBuildOutput
	if err := json.Unmarshal(c.Input, &in); err != nil {
		t.Fatal(err)
	}
	if err := json.Unmarshal(c.Output, &want); err != nil {
		t.Fatal(err)
	}
	got := BuildDoorCode(env.PublicBaseURL, DoorCodeInput{
		Lang: in.Lang, PropertyName: in.PropertyName, Checkin: in.Checkin, Checkout: in.Checkout,
		FirstUseBy: in.FirstUseBy, Host: in.Host, Fee: in.Fee,
	})
	sameBytes(t, c.Name, "subject", got.Subject, want.Subject)
	sameBytes(t, c.Name, "text", got.Text, want.Text)
	sameBytes(t, c.Name, "html", got.HTML, want.HTML)
	sameBytes(t, c.Name, "qr_spayd", got.QRSpayd, want.QRSpayd)
}

func replayDoorNotice(t *testing.T, env DoorCodeMailEnv, c doorCase) {
	var in doorNoticeInput
	var want *doorMailOutput
	if err := json.Unmarshal(c.Input, &in); err != nil {
		t.Fatal(err)
	}
	if err := json.Unmarshal(c.Output, &want); err != nil {
		t.Fatal(err)
	}
	if want == nil {
		// Python returned None before enqueueing: the entity has no contact address.
		if c.Row.Apartment.ContactEmail != "" {
			t.Fatalf("golden says no enqueue, but the entity has a contact address")
		}
		return
	}
	in2 := DoorCodeNoticeIn{
		DoorCodeID:    in.DoorCodeID,
		ReservationID: c.Row.Reservation.ID,
		Variant:       in.Variant,
		KeySuffix:     in.KeySuffix,
		PropertyName:  c.Row.Apartment.InternalName,
		DateFrom:      c.Row.Reservation.DateFrom,
		LastError:     in.LastError,
		HasPin:        in.Pin != nil && *in.Pin != "",
	}
	if in.Pin != nil {
		in2.Pin = *in.Pin
	}
	got := BuildDoorCodeNotice(env, in2)
	doorCompareMail(t, c.Name, got, want)
}

func replayDoorDelayed(t *testing.T, env DoorCodeMailEnv, c doorCase) {
	var in doorDelayedInput
	var want *doorMailOutput
	if err := json.Unmarshal(c.Input, &in); err != nil {
		t.Fatal(err)
	}
	if err := json.Unmarshal(c.Output, &want); err != nil {
		t.Fatal(err)
	}
	if want == nil {
		t.Fatalf("delayed golden %s has no enqueue", c.Name)
	}
	got := BuildDoorCodeDelayedNotice(env, DoorCodeDelayedIn{
		ReservationID: in.ReservationID,
		PropertyName:  c.Row.Apartment.InternalName,
		DateFrom:      c.Row.Reservation.DateFrom,
		Reason:        in.Reason,
	})
	doorCompareMail(t, c.Name, got, want)
}

func doorCompareMail(t *testing.T, name string, got DoorCodeNoticeOut, want *doorMailOutput) {
	t.Helper()
	if got.Kind != want.Kind {
		t.Errorf("%s: kind %q want %q", name, got.Kind, want.Kind)
	}
	if got.IdempotencyKey != want.IdempotencyKey {
		t.Errorf("%s: idempotency key %q want %q", name, got.IdempotencyKey, want.IdempotencyKey)
	}
	sameBytes(t, name, "subject", got.Subject, want.Subject)
	sameBytes(t, name, "payload.text", got.Text, want.Payload.Text)
	sameBytes(t, name, "payload.html", got.HTML, want.Payload.HTML)
	if got.Lang != want.Payload.Lang {
		t.Errorf("%s: lang %q want %q", name, got.Lang, want.Payload.Lang)
	}
	wantCC := ""
	if want.CCEmail != nil {
		wantCC = *want.CCEmail
	}
	if got.CC != wantCC {
		t.Errorf("%s: cc %q want %q", name, got.CC, wantCC)
	}
}
