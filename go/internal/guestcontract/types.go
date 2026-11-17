package guestcontract

// FormConfig is guest_form_snapshot.form_config (JSONB): everything the guest
// program needs to draw and check the form for one link key without the app.
type FormConfig struct {
	ApartmentID         int64             `json:"apartment_id"`
	ApartmentName       string            `json:"apartment_name"`
	Languages           []string          `json:"languages"`
	DefaultPurpose      string            `json:"default_purpose"`
	PassportPhotoPolicy string            `json:"passport_photo_policy"`
	LegalVersions       map[string]string `json:"legal_versions"`
	Stays               []Stay            `json:"stays"`
}

// Stay is one stay the link may register guests for.
type Stay struct {
	ReservationID int64  `json:"reservation_id"`
	DateFrom      string `json:"date_from"` // ISO date, the booking's date_from
	DateTo        string `json:"date_to"`   // ISO date, the booking's date_to
	// ExpectedGuests is nil when the stay has no expected count yet; the form
	// then asks for party_size.
	ExpectedGuests   *int `json:"expected_guests"`
	RegisteredGuests int  `json:"registered_guests"`
}

// Submission is the plaintext of guest_inbox.payload_enc. received_at and
// token_hash are columns, not payload fields.
type Submission struct {
	ContractVersion int       `json:"contract_version"`
	IdempotencyKey  string    `json:"idempotency_key"`
	ReservationID   int64     `json:"reservation_id"`
	Lang            string    `json:"lang"`
	Guest           GuestForm `json:"guest"`
}

// GuestForm holds one guest as posted, by the form field names of the guest
// page, before any normalisation. The app normalises on processing exactly as
// today, so what is filed with UbyPort does not depend on this package.
type GuestForm struct {
	Surname         string `json:"surname"`
	FirstName       string `json:"first_name"`
	BirthDate       string `json:"birth_date"`
	Nationality     string `json:"nationality"`
	DocNumber       string `json:"doc_number"`
	VisaNumber      string `json:"visa_number"`
	ResStreet       string `json:"res_street"`
	ResCity         string `json:"res_city"`
	ResCountry      string `json:"res_country"`
	Purpose         string `json:"purpose"`
	Note            string `json:"note"`
	ParentDocNumber string `json:"parent_doc_number"`
	Signature       string `json:"signature"`
	PartySize       string `json:"party_size"`
	LegalAck        bool   `json:"legal_ack"`
	ChildSignRole   string `json:"child_sign_role"`
	SignedBy        string `json:"signed_by"`
}

// Fields returns the posted text fields by form name, as the guest route reads
// them from the request (missing means empty).
func (g GuestForm) Fields() map[string]string {
	return map[string]string{
		"surname":           g.Surname,
		"first_name":        g.FirstName,
		"birth_date":        g.BirthDate,
		"nationality":       g.Nationality,
		"doc_number":        g.DocNumber,
		"visa_number":       g.VisaNumber,
		"res_street":        g.ResStreet,
		"res_city":          g.ResCity,
		"res_country":       g.ResCountry,
		"purpose":           g.Purpose,
		"note":              g.Note,
		"parent_doc_number": g.ParentDocNumber,
	}
}
