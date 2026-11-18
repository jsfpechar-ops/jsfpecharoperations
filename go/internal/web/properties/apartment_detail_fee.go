package properties

// Brief 1701b: the Stay fee section of GET /apartments/{id} (sec-fee). The data
// the Jinja context of _render_apartment_detail adds for it: rate_from_default,
// fee_template_peers, fee_signature (_fee_signature_context) and
// guest_pay_operator (stay_fee_routes.guest_pay_operator_context), plus what
// _stay_fee_fields.html computes with {% set %}. The fee amounts, the account
// and the sample QR come from the stayfees package; nothing is calculated
// here. Every read is scoped to the workspace (owner_user_id IS NOT DISTINCT
// FROM $owner), starting from the property already loaded by detailLoad.

import (
	"context"
	"errors"
	"html/template"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/stayfees"
)

// detailFeePeer is one fee_template_peers row: another property of the
// workspace that has a stay fee, as the copy dropdown reads it.
type detailFeePeer struct {
	ID                                  int64
	Name                                string
	Rate                                int64
	Cadence, VS, Account, AuthorityName string
	AuthorityAddress, AuthorityContact  string
	Payee, Instruction                  string
}

// detailFeeSignature is fee_signature: the operator's report signature.
// Preview is the stored image as a data: URL (or ""), kept only when it is a
// PNG or JPEG data URL, as the entity form wrote it.
type detailFeeSignature struct {
	Name    string
	Preview template.URL
}

// detailFeeRail is one guest payment method of the guest-pay block.
type detailFeeRail struct {
	Code          string
	On, IsDefault bool
}

// detailFee is the template context of the section.
type detailFee struct {
	RateFromDefault string
	AccountValue    string
	Needed          bool // fee_needed: a rate above 0 stars the three required boxes
	MoreOpen        bool // the folded office details hold a value
	MissingWarn     bool
	Peers           []detailFeePeer
	Signature       *detailFeeSignature
	GuestPay        bool
	Rails           []detailFeeRail
	OperatorValue   string
	HasPreview      bool
	PreviewQR       template.URL // a data: image drawn by stayfees from the operator account
	AccountDisplay  string
}

const (
	detailFeePeersSQL = `SELECT id, COALESCE(internal_name, ''), COALESCE(stay_fee_rate_czk, 0), COALESCE(NULLIF(stay_fee_cadence, ''), 'monthly'),
  COALESCE(stay_fee_vs, ''), COALESCE(stay_fee_council_account, ''), COALESCE(stay_fee_authority_name, ''),
  COALESCE(stay_fee_authority_address, ''), COALESCE(stay_fee_authority_contact, ''), COALESCE(stay_fee_payee, ''),
  COALESCE(stay_fee_instruction, '')
FROM apartment WHERE owner_user_id IS NOT DISTINCT FROM $1 AND archived_at IS NULL AND id <> $2 AND COALESCE(stay_fee_rate_czk, 0) > 0
ORDER BY internal_name, id`
	detailFeeOperatorSQL = `SELECT COALESCE(bank_account, ''), COALESCE(iban, ''), COALESCE(signature_name, ''),
  COALESCE(signature_png_enc, ''), archived_at IS NOT NULL
FROM legal_entity WHERE id = $1 AND owner_user_id IS NOT DISTINCT FROM $2`
)

// detailFeeBuild fills the section's context for the loaded property.
func (s *Pages) detailFeeBuild(ctx context.Context, owner int64, a *detailApt, now time.Time) (detailFee, error) {
	f := detailFee{RateFromDefault: stayfees.PragueToday(now), Needed: a.StayFeeRateCZK > 0}
	f.AccountValue = a.StayFeeCouncilAccount
	if f.AccountValue == "" {
		f.AccountValue = a.StayFeeCouncilIBAN
	}
	f.MoreOpen = a.StayFeeAuthorityAddress != "" || a.StayFeeAuthorityContact != "" || a.StayFeeAuthorityDatabox != ""
	f.MissingWarn = a.StayFeeRateCZK > 0 && (pyStrip(a.StayFeeVS) == "" || pyStrip(a.StayFeeCouncilAccount) == "" || pyStrip(a.StayFeeAuthorityName) == "")

	rows, err := s.pool.Query(ctx, detailFeePeersSQL, owner, a.ID)
	if err != nil {
		return f, err
	}
	if f.Peers, err = pgx.CollectRows(rows, func(row pgx.CollectableRow) (detailFeePeer, error) {
		var p detailFeePeer
		err := row.Scan(&p.ID, &p.Name, &p.Rate, &p.Cadence, &p.VS, &p.Account, &p.AuthorityName, &p.AuthorityAddress,
			&p.AuthorityContact, &p.Payee, &p.Instruction)
		return p, err
	}); err != nil {
		return f, err
	}

	var bank, iban, sigName, sigEnc string
	var archived, haveOperator bool
	if a.LegalEntityID != 0 {
		err := s.pool.QueryRow(ctx, detailFeeOperatorSQL, a.LegalEntityID, owner).Scan(&bank, &iban, &sigName, &sigEnc, &archived)
		if err != nil && !errors.Is(err, pgx.ErrNoRows) {
			return f, err
		}
		haveOperator = err == nil
	}
	if haveOperator {
		preview, err := s.detailSecret(sigEnc, now)
		if err != nil {
			return f, err
		}
		if !strings.HasPrefix(preview, "data:image/png;base64,") && !strings.HasPrefix(preview, "data:image/jpeg;base64,") {
			preview = ""
		}
		f.Signature = &detailFeeSignature{Name: sigName, Preview: template.URL(preview)} // a data: image the host stored through the entity form
	}
	// The guest-pay operator is one of the workspace's not archived businesses (access.entities).
	if haveOperator && archived {
		bank, iban = "", ""
	}
	op, err := stayfees.GuestPayOperatorFor(s.getenv, bank, iban, a.StayFeeRateCZK)
	if err != nil {
		return f, err
	}
	f.GuestPay = op.On
	f.OperatorValue, f.AccountDisplay = op.FieldValue, op.AccountDisplay
	f.HasPreview = op.HasAccount && op.PreviewQR != ""
	f.PreviewQR = template.URL(op.PreviewQR) // a data: image drawn from the operator account
	f.Rails = detailFeeRails(a.StayFeeGuestRails, a.StayFeeGuestDefaultRail)
	return f, nil
}

// detailFeeRails is the {% set %} block of _stay_fee_fields.html: the stored
// rails ("qr" is the old name of "iban"), in the fixed order, and which one the
// default select shows (the stored default when it is still on, else the first).
func detailFeeRails(stored, storedDefault string) []detailFeeRail {
	have := map[string]bool{}
	for _, r := range strings.Split(strings.ReplaceAll(stored, "qr", "iban"), ",") {
		have[r] = true
	}
	def := strings.ReplaceAll(storedDefault, "qr", "iban")
	out := make([]detailFeeRail, 0, 3)
	first := ""
	for _, code := range []string{"iban", "revolut", "cash"} {
		out = append(out, detailFeeRail{Code: code, On: have[code]})
		if have[code] && first == "" {
			first = code
		}
	}
	on := false
	for _, r := range out {
		on = on || (r.On && r.Code == def)
	}
	if !on {
		def = first
	}
	for i := range out {
		out[i].IsDefault = out[i].Code == def
	}
	return out
}
