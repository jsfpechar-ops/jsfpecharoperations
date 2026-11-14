package invoices

// Database reads and writes of the invoice pages: the owner-scoped lookups of
// routes/invoices.py and access.py, number allocation and the issue and
// cancel transactions of invoices.py. SQL is plain PostgreSQL; the owner test
// is `IS NOT DISTINCT FROM` as db.null_safe_eq writes it.

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/countries"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/pdf"
)

// ownerArg is access.owner_id as a query argument: nil when there is none.
func ownerArg(owner int64) any {
	if owner == 0 {
		return nil
	}
	return owner
}

const entityColumns = `id, name, COALESCE(seat,''), COALESCE(ico,''), COALESCE(dic,''),
	COALESCE(contact_email,''), COALESCE(contact_phone,''), COALESCE(bank_account,''),
	COALESCE(iban,''), COALESCE(bic,''), COALESCE(NULLIF(vat_status,''),'non_payer'),
	COALESCE(registry_entry,''), COALESCE(invoice_prefix,''), invoice_next_number,
	invoice_next_number_year, invoice_due_days`

func scanEntity(row pgx.Row) (entity, error) {
	var e entity
	err := row.Scan(&e.ID, &e.Name, &e.Seat, &e.ICO, &e.DIC, &e.ContactEmail, &e.ContactPhone,
		&e.BankAccount, &e.IBAN, &e.BIC, &e.VATStatus, &e.RegistryEntry, &e.InvoicePrefix,
		&e.NextNumber, &e.NextNumberYear, &e.DueDays)
	return e, err
}

// entities is _entities: the host's active operators, by name.
func entities(ctx context.Context, pool *pgxpool.Pool, owner int64) ([]entity, error) {
	rows, err := pool.Query(ctx,
		`SELECT `+entityColumns+` FROM legal_entity
		WHERE archived_at IS NULL AND owner_user_id IS NOT DISTINCT FROM $1::bigint ORDER BY name`,
		ownerArg(owner))
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []entity
	for rows.Next() {
		e, err := scanEntity(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, e)
	}
	return out, rows.Err()
}

// chosenEntity is _chosen_entity: the posted legal_entity_id, else ?entity=,
// when it is one of the host's; else the first.
func chosenEntity(list []entity, formValue, query string) *entity {
	wanted := formValue
	if wanted == "" {
		wanted = strings.TrimSpace(query)
	}
	if isDigits(wanted) {
		for i := range list {
			if itoa(list[i].ID) == wanted {
				return &list[i]
			}
		}
	}
	if len(list) > 0 {
		return &list[0]
	}
	return nil
}

func isDigits(s string) bool {
	if s == "" {
		return false
	}
	for _, c := range s {
		if c < '0' || c > '9' {
			return false
		}
	}
	return true
}

// entityForStay is _entity_for_stay: the property's operator when it has one
// (and the host still has it), otherwise the host's pick.
func entityForStay(list []entity, st *stay, formValue, query string) *entity {
	if st != nil && st.EntityID != nil {
		for i := range list {
			if list[i].ID == *st.EntityID {
				return &list[i]
			}
		}
	}
	return chosenEntity(list, formValue, query)
}

// stayFor is _stay_for: the host's own stay, or nil.
func stayFor(ctx context.Context, pool *pgxpool.Pool, owner int64, raw string) (*stay, error) {
	raw = strings.TrimSpace(raw)
	if !isDigits(raw) {
		return nil, nil
	}
	id, perr := strconv.ParseInt(raw, 10, 64)
	if perr != nil {
		return nil, nil // too big for bigint: no such stay
	}
	var s stay
	var internal, uby string
	err := pool.QueryRow(ctx,
		`SELECT r.id, r.apartment_id, r.date_from, r.date_to, COALESCE(r.status,''), COALESCE(r.source,''),
		        COALESCE(r.guest_email,''), a.legal_entity_id, COALESCE(a.internal_name,''), COALESCE(a.uby_name,'')
		 FROM reservation r JOIN apartment a ON a.id = r.apartment_id
		 WHERE r.id = $1 AND a.owner_user_id IS NOT DISTINCT FROM $2::bigint`,
		id, ownerArg(owner)).Scan(&s.ReservationID, &s.ApartmentID, &s.DateFrom, &s.DateTo, &s.Status,
		&s.Source, &s.GuestEmail, &s.EntityID, &internal, &uby)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	s.PropertyName = strings.TrimSpace(internal)
	if s.PropertyName == "" {
		s.PropertyName = strings.TrimSpace(uby)
	}
	return &s, nil
}

type stayOption struct {
	ID       int64
	Label    string
	DateFrom string
}

// stayOptions is _stay_options: stays the host can invoice, newest check-in
// first.
func stayOptions(ctx context.Context, pool *pgxpool.Pool, owner int64, today time.Time) ([]stayOption, error) {
	rows, err := pool.Query(ctx,
		`SELECT r.id, r.date_from, r.date_to, COALESCE(a.internal_name,''), COALESCE(a.uby_name,'')
		 FROM reservation r JOIN apartment a ON a.id = r.apartment_id
		 WHERE a.owner_user_id IS NOT DISTINCT FROM $1::bigint AND r.status != 'cancelled'
		 AND COALESCE(r.source, '') != 'demo'
		 AND r.date_to > r.date_from AND r.date_to >= $2 AND r.date_from <= $3
		 ORDER BY r.date_from DESC, r.id DESC LIMIT 200`,
		ownerArg(owner), today.AddDate(0, 0, -staleDays).Format("2006-01-02"),
		today.AddDate(0, 0, futureDays).Format("2006-01-02"))
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []stayOption
	for rows.Next() {
		var id int64
		var from, to, internal, uby string
		if err := rows.Scan(&id, &from, &to, &internal, &uby); err != nil {
			return nil, err
		}
		name := strings.TrimSpace(internal)
		if name == "" {
			name = strings.TrimSpace(uby)
		}
		out = append(out, stayOption{ID: id, Label: name + ", " + fmtDateRange(from, to), DateFrom: isoDate(from)})
	}
	return out, rows.Err()
}

type activeInvoice struct {
	ID     int64
	Number string
}

const activeForStaySQL = `SELECT i.id, i.number FROM invoice i WHERE i.reservation_id = $1 AND i.kind = 'invoice'
	AND NOT EXISTS (SELECT 1 FROM invoice c WHERE c.corrects_invoice_id = i.id)
	ORDER BY i.id DESC LIMIT 1`

// activeInvoiceForStay is active_invoice_for_stay: the stay's invoice that has
// no storno/ODD yet, or nil.
func activeInvoiceForStay(ctx context.Context, q interface {
	QueryRow(context.Context, string, ...any) pgx.Row
}, reservationID int64) (*activeInvoice, error) {
	var a activeInvoice
	err := q.QueryRow(ctx, activeForStaySQL, reservationID).Scan(&a.ID, &a.Number)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &a, nil
}

// quickStays is _quick_stays: started stays without a live invoice, newest
// first, six at most.
func quickStays(ctx context.Context, pool *pgxpool.Pool, options []stayOption, today time.Time) ([]stayOption, error) {
	const quick = 6
	day := today.Format("2006-01-02")
	var out []stayOption
	for i, o := range options {
		if i >= 40 {
			break
		}
		if o.DateFrom > day {
			continue
		}
		active, err := activeInvoiceForStay(ctx, pool, o.ID)
		if err != nil {
			return nil, err
		}
		if active != nil {
			continue
		}
		out = append(out, o)
		if len(out) == quick {
			break
		}
	}
	return out, nil
}

// lastStayPriceHint is _last_stay_price_hint: the last issued accommodation
// unit price on this property, for a placeholder.
func lastStayPriceHint(ctx context.Context, pool *pgxpool.Pool, owner, apartmentID int64) (string, error) {
	var gross, qty int64
	err := pool.QueryRow(ctx,
		`SELECT ii.gross_haler, ii.quantity FROM invoice i JOIN invoice_item ii ON ii.invoice_id = i.id
		 WHERE i.apartment_id = $1 AND i.owner_user_id IS NOT DISTINCT FROM $2::bigint
		 AND i.kind = 'invoice' AND ii.kind = 'accommodation'
		 ORDER BY i.issue_date DESC, i.id DESC LIMIT 1`, apartmentID, ownerArg(owner)).Scan(&gross, &qty)
	if errors.Is(err, pgx.ErrNoRows) || (err == nil && gross == 0) {
		return "", nil
	}
	if err != nil {
		return "", err
	}
	if qty == 0 {
		qty = 1
	}
	return hintAmount(gross, qty), nil
}

// hintAmount is `str(int(amount))` for a whole amount, else f"{amount:.2f}"
// without trailing zeros, for amount = gross / (100 * qty).
func hintAmount(gross, qty int64) string {
	r := ratOf(gross, 100*qty)
	if r.IsInt() {
		return r.Num().String()
	}
	// f"{float:.2f}": round half even on the binary float; the quotient of
	// two integers is close enough that ties are not a concern at 2 places.
	f, _ := r.Float64()
	s := fmt.Sprintf("%.2f", f)
	s = strings.TrimRight(s, "0")
	return strings.TrimRight(s, ".")
}

// rememberedPaidVia is _remember_paid_via: the payment method of this
// operator's last paid invoice, as the values it fills.
func rememberedPaidVia(ctx context.Context, pool *pgxpool.Pool, owner, entityID int64) (map[string]string, error) {
	var via string
	err := pool.QueryRow(ctx,
		`SELECT paid_via FROM invoice WHERE legal_entity_id = $1 AND owner_user_id IS NOT DISTINCT FROM $2::bigint
		 AND kind = 'invoice' AND paid_via IS NOT NULL AND paid_via != ''
		 ORDER BY issue_date DESC, id DESC LIMIT 1`, entityID, ownerArg(owner)).Scan(&via)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	switch via {
	case "direct_transfer", "cash", "airbnb", "booking":
		return map[string]string{"paid_via": via}, nil
	}
	return map[string]string{"paid_via_custom": cut(via, 60)}, nil
}

// previewNumber is preview_number: the next number as a hint for the form.
func previewNumber(ctx context.Context, pool *pgxpool.Pool, e entity, year int) (string, error) {
	var last int64
	err := pool.QueryRow(ctx, `SELECT last_no FROM invoice_sequence WHERE legal_entity_id = $1 AND year = $2`,
		e.ID, year).Scan(&last)
	if err != nil && !errors.Is(err, pgx.ErrNoRows) {
		return "", err
	}
	return formatNumber(e.InvoicePrefix, year, last+1), nil
}

func formatNumber(prefix string, year int, seq int64) string {
	return fmt.Sprintf("%s%d-%0*d", prefix, year, max(4, len(itoa(seq))), seq)
}

// invoiceRow is a stored invoice with the columns the pages read (not the PDF).
type invoiceRow struct {
	ID, LegalEntityID                     int64
	ApartmentID, ReservationID            *int64
	Kind, Number, VS, Lang, VATStatus     string
	IssueDate                             string
	PaidOn, MarkedPaidAt, PDFSHA256, Note string
	PaidVia, BuyerName, BuyerEmail        string
	BuyerStreet, BuyerCity, BuyerZip      string
	BuyerCountry, BuyerICO, BuyerDIC      string
	SellerName, SellerSeat, SellerICO     string
	SellerDIC, SellerRegistry, SellerBank string
	SellerIBAN, SellerBIC, SellerEmail    string
	SellerPhone, StayLabel                string
	DUZP, DueDate, CorrectionReason       string
	CorrectionDate                        string
	CorrectsInvoiceID                     *int64
	TotalHaler                            int64
	OwnerUserID                           *int64
}

const invoiceColumns = `id, legal_entity_id, apartment_id, reservation_id, kind, number, vs, lang, vat_status,
	issue_date, COALESCE(paid_on,''), COALESCE(marked_paid_at,''), COALESCE(pdf_sha256,''), COALESCE(note,''),
	COALESCE(paid_via,''), buyer_name, COALESCE(buyer_email,''), COALESCE(buyer_street,''), COALESCE(buyer_city,''),
	COALESCE(buyer_zip,''), COALESCE(buyer_country,''), COALESCE(buyer_ico,''), COALESCE(buyer_dic,''),
	seller_name, seller_seat, COALESCE(seller_ico,''), COALESCE(seller_dic,''), COALESCE(seller_registry,''),
	COALESCE(seller_bank_account,''), COALESCE(seller_iban,''), COALESCE(seller_bic,''), COALESCE(seller_email,''),
	COALESCE(seller_phone,''), COALESCE(stay_label,''), COALESCE(duzp,''), COALESCE(due_date,''),
	COALESCE(correction_reason,''), COALESCE(correction_date,''), corrects_invoice_id, total_haler, owner_user_id`

func scanInvoice(row pgx.Row) (invoiceRow, error) {
	var v invoiceRow
	err := row.Scan(&v.ID, &v.LegalEntityID, &v.ApartmentID, &v.ReservationID, &v.Kind, &v.Number, &v.VS, &v.Lang,
		&v.VATStatus, &v.IssueDate, &v.PaidOn, &v.MarkedPaidAt, &v.PDFSHA256, &v.Note, &v.PaidVia, &v.BuyerName,
		&v.BuyerEmail, &v.BuyerStreet, &v.BuyerCity, &v.BuyerZip, &v.BuyerCountry, &v.BuyerICO, &v.BuyerDIC,
		&v.SellerName, &v.SellerSeat, &v.SellerICO, &v.SellerDIC, &v.SellerRegistry, &v.SellerBank, &v.SellerIBAN,
		&v.SellerBIC, &v.SellerEmail, &v.SellerPhone, &v.StayLabel, &v.DUZP, &v.DueDate, &v.CorrectionReason,
		&v.CorrectionDate, &v.CorrectsInvoiceID, &v.TotalHaler, &v.OwnerUserID)
	return v, err
}

type invoiceItemRow struct {
	Kind, Description, Unit string
	Quantity                int64
	VATRate, Base, VAT      *int64
	Gross                   int64
}

func (r invoiceRow) paid() bool { return r.PaidOn != "" || r.MarkedPaidAt != "" }

// loadInvoice is _load_invoice: the host's own invoice, or nil.
func loadInvoice(ctx context.Context, pool *pgxpool.Pool, owner, id int64) (*invoiceRow, error) {
	v, err := scanInvoice(pool.QueryRow(ctx,
		`SELECT `+invoiceColumns+` FROM invoice WHERE id = $1 AND owner_user_id IS NOT DISTINCT FROM $2::bigint`,
		id, ownerArg(owner)))
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &v, nil
}

type queryer interface {
	Query(context.Context, string, ...any) (pgx.Rows, error)
	QueryRow(context.Context, string, ...any) pgx.Row
}

func loadItems(ctx context.Context, q queryer, invoiceID int64) ([]invoiceItemRow, error) {
	rows, err := q.Query(ctx,
		`SELECT kind, description, quantity, COALESCE(unit,''), vat_rate, base_haler, vat_haler, gross_haler
		 FROM invoice_item WHERE invoice_id = $1 ORDER BY position`, invoiceID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []invoiceItemRow
	for rows.Next() {
		var it invoiceItemRow
		if err := rows.Scan(&it.Kind, &it.Description, &it.Quantity, &it.Unit, &it.VATRate, &it.Base, &it.VAT, &it.Gross); err != nil {
			return nil, err
		}
		out = append(out, it)
	}
	return out, rows.Err()
}

// ---- issuing ----

// stayLimit is StayLimit: the stay already has its invoice, or its last
// allowed one.
type stayLimit struct {
	Key       string
	InvoiceID int64 // 0 when none
}

func (s *stayLimit) Error() string { return s.Key }

func checkStayLimit(ctx context.Context, tx pgx.Tx, reservationID int64) error {
	active, err := activeInvoiceForStay(ctx, tx, reservationID)
	if err != nil {
		return err
	}
	if active != nil {
		return &stayLimit{Key: "invoice.err.stay_has_invoice", InvoiceID: active.ID}
	}
	var total int64
	if err := tx.QueryRow(ctx, `SELECT COUNT(*) FROM invoice WHERE reservation_id = $1 AND kind = 'invoice'`,
		reservationID).Scan(&total); err != nil {
		return err
	}
	if total >= stayMaxInvoices {
		return &stayLimit{Key: "invoice.err.stay_limit"}
	}
	return nil
}

// nullStr is the `value or None` of the invoice columns.
func nullStr(s string) any {
	if s == "" {
		return nil
	}
	return s
}

// writeIssued is _write_issued: allocate the number, write the invoice, its
// items and its PDF in one transaction. The advisory lock is the one
// db.lock_key takes, so Python and Go writers of one operator queue up.
func writeIssued(ctx context.Context, pool *pgxpool.Pool, d draft, actor *int64, at time.Time) (int64, string, error) {
	year := 0
	if _, err := fmt.Sscanf(d.IssueDate[:4], "%d", &year); err != nil {
		return 0, "", err
	}
	tx, err := pool.Begin(ctx)
	if err != nil {
		return 0, "", err
	}
	defer func() { _ = tx.Rollback(ctx) }()
	if _, err := tx.Exec(ctx, `SELECT pg_advisory_xact_lock(hashtext($1), $2::int)`, "invoice_sequence", d.LegalEntityID); err != nil {
		return 0, "", err
	}
	e, err := scanEntity(tx.QueryRow(ctx, `SELECT `+entityColumns+` FROM legal_entity WHERE id = $1`, d.LegalEntityID))
	if err != nil {
		return 0, "", err
	}
	if d.Kind == "invoice" && d.ReservationID != nil {
		if err := checkStayLimit(ctx, tx, *d.ReservationID); err != nil {
			return 0, "", err
		}
	}
	seq, number, vs, err := allocateNumber(ctx, tx, e, year)
	if err != nil {
		return 0, "", err
	}
	var id int64
	err = tx.QueryRow(ctx,
		`INSERT INTO invoice (legal_entity_id, apartment_id, reservation_id, kind, corrects_invoice_id,
		   correction_reason, correction_date, seq_year, seq_no, number, vs, lang, currency, vat_status,
		   issue_date, duzp, due_date, paid_on, paid_via, note, seller_name, seller_seat, seller_ico, seller_dic,
		   seller_registry, seller_bank_account, seller_iban, seller_bic, seller_email, seller_phone, buyer_name,
		   buyer_street, buyer_city, buyer_zip, buyer_country, buyer_ico, buyer_dic, buyer_email, stay_from,
		   stay_to, stay_label, total_base_haler, total_vat_haler, total_haler, owner_user_id, created_at)
		 VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,'CZK',$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24,$25,
		   $26,$27,$28,$29,$30,$31,$32,$33,$34,$35,$36,$37,$38,$39,$40,$41,$42,$43,$44,$45)
		 RETURNING id`,
		d.LegalEntityID, d.ApartmentID, d.ReservationID, d.Kind, d.CorrectsInvoiceID,
		nullStr(d.CorrectionReason), nullStr(d.CorrectionDate), int64(year), seq, number, vs, d.Lang, d.VATStatus,
		d.IssueDate, nullStr(d.DUZP), nullStr(d.DueDate), nullStr(d.PaidOn), nullStr(d.PaidVia), nullStr(d.Note),
		d.Seller.Name, d.Seller.Seat, nullStr(d.Seller.ICO), nullStr(d.Seller.DIC), nullStr(d.Seller.Registry),
		nullStr(d.Seller.BankAccount), nullStr(d.Seller.IBAN), nullStr(d.Seller.BIC), nullStr(d.Seller.Email),
		nullStr(d.Seller.Phone), d.Buyer.Name, nullStr(d.Buyer.Street), nullStr(d.Buyer.City), nullStr(d.Buyer.Zip),
		nullStr(d.Buyer.Country), nullStr(d.Buyer.ICO), nullStr(d.Buyer.DIC), nullStr(d.Buyer.Email),
		nullStr(d.StayFrom), nullStr(d.StayTo), nullStr(d.StayLabel), d.TotalBase, d.TotalVAT, d.TotalHaler,
		d.OwnerUserID, stamp(at)).Scan(&id)
	if err != nil {
		return 0, "", err
	}
	for i, it := range d.Items {
		if _, err := tx.Exec(ctx,
			`INSERT INTO invoice_item (invoice_id, position, kind, description, quantity, unit, vat_rate, base_haler, vat_haler, gross_haler)
			 VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)`,
			id, int64(i+1), it.Kind, it.Description, it.Quantity, it.Unit, it.VATRate, it.Base, it.VAT, it.Gross); err != nil {
			return 0, "", err
		}
	}
	view, err := pdfView(ctx, tx, id)
	if err != nil {
		return 0, "", err
	}
	items, err := loadItems(ctx, tx, id)
	if err != nil {
		return 0, "", err
	}
	blob, err := pdf.Render(view, pdfItems(items), d.Lang, false, false)
	if err != nil {
		return 0, "", err
	}
	sum := sha256.Sum256(blob)
	if _, err := tx.Exec(ctx, `UPDATE invoice SET pdf_blob = $1, pdf_sha256 = $2, issued_at = $3, issued_by = $4 WHERE id = $5`,
		blob, hex.EncodeToString(sum[:]), stamp(at), actor, id); err != nil {
		return 0, "", err
	}
	if err := tx.Commit(ctx); err != nil {
		return 0, "", err
	}
	return id, number, nil
}

// allocateNumber is allocate_number: (seq, number, vs). The caller holds the
// advisory lock.
func allocateNumber(ctx context.Context, tx pgx.Tx, e entity, year int) (int64, string, string, error) {
	var last int64
	err := tx.QueryRow(ctx, `SELECT last_no FROM invoice_sequence WHERE legal_entity_id = $1 AND year = $2`,
		e.ID, int64(year)).Scan(&last)
	if err != nil && !errors.Is(err, pgx.ErrNoRows) {
		return 0, "", "", err
	}
	if e.NextNumber != nil && *e.NextNumber != 0 && e.NextNumberYear != nil && *e.NextNumberYear == int64(year) {
		last = max(last, *e.NextNumber-1)
		if _, err := tx.Exec(ctx,
			`UPDATE legal_entity SET invoice_next_number = NULL, invoice_next_number_year = NULL WHERE id = $1`, e.ID); err != nil {
			return 0, "", "", err
		}
	}
	seq := last + 1
	if _, err := tx.Exec(ctx,
		`INSERT INTO invoice_sequence (legal_entity_id, year, last_no) VALUES ($1, $2, $3)
		 ON CONFLICT(legal_entity_id, year) DO UPDATE SET last_no = excluded.last_no`,
		e.ID, int64(year), seq); err != nil {
		return 0, "", "", err
	}
	width := max(4, len(itoa(seq)))
	return seq, fmt.Sprintf("%s%d-%0*d", e.InvoicePrefix, year, width, seq), fmt.Sprintf("%d%0*d", year, width, seq), nil
}

// pdfView is pdf_view_row for pdf.Render: the stored row plus the view-only fields.
func pdfView(ctx context.Context, q queryer, id int64) (pdf.Invoice, error) {
	v, err := scanInvoice(q.QueryRow(ctx, `SELECT `+invoiceColumns+` FROM invoice WHERE id = $1`, id))
	if err != nil {
		return pdf.Invoice{}, err
	}
	in := pdf.Invoice{
		Number: v.Number, Kind: v.Kind, VATStatus: v.VATStatus,
		SellerName: v.SellerName, SellerSeat: v.SellerSeat, SellerICO: v.SellerICO, SellerDIC: v.SellerDIC,
		SellerRegistry: v.SellerRegistry, SellerEmail: v.SellerEmail, SellerPhone: v.SellerPhone,
		SellerIBAN: v.SellerIBAN, SellerBankAccount: v.SellerBank, SellerBIC: v.SellerBIC,
		BuyerName: v.BuyerName, BuyerStreet: v.BuyerStreet, BuyerZip: v.BuyerZip, BuyerCity: v.BuyerCity,
		BuyerICO: v.BuyerICO, BuyerDIC: v.BuyerDIC, IssueDate: v.IssueDate, DUZP: v.DUZP, DueDate: v.DueDate,
		PaidOn: v.PaidOn, VS: v.VS, PaidViaLabel: customPaidViaLabel(v.PaidVia), StayLabel: v.StayLabel,
		CorrectionReason: v.CorrectionReason, CorrectionDate: v.CorrectionDate, Note: v.Note, TotalHaler: v.TotalHaler,
	}
	if v.BuyerCountry != "" && v.BuyerCountry != "CZE" {
		in.BuyerCountryName = countries.Name(v.BuyerCountry, "cs")
	}
	if v.CorrectsInvoiceID != nil {
		var number string
		var total int64
		err := q.QueryRow(ctx, `SELECT number, total_haler FROM invoice WHERE id = $1`, *v.CorrectsInvoiceID).Scan(&number, &total)
		if err == nil {
			in.CorrectsNumber = number
			in.PartialCorrection = absInt(v.TotalHaler) < absInt(total)
		} else if !errors.Is(err, pgx.ErrNoRows) {
			return pdf.Invoice{}, err
		}
	}
	return in, nil
}

func absInt(n int64) int64 {
	if n < 0 {
		return -n
	}
	return n
}

func pdfItems(items []invoiceItemRow) []pdf.Item {
	out := make([]pdf.Item, len(items))
	for i, it := range items {
		p := pdf.Item{Description: it.Description, Quantity: int(it.Quantity), Unit: it.Unit, GrossHaler: it.Gross}
		if it.VATRate != nil {
			r := int(*it.VATRate)
			p.VATRate = &r
		}
		if it.Base != nil {
			p.BaseHaler = *it.Base
		}
		if it.VAT != nil {
			p.VATHaler = *it.VAT
		}
		out[i] = p
	}
	return out
}

// issueInvoice is invoices.issue: write the invoice, then the audit line.
func (c *call) issueInvoice(d draft) (int64, string, error) {
	d.OwnerUserID = ptrOwner(c.owner)
	// invoices.issue(draft, access.owner_id(request)): issued_by is the workspace owner.
	id, number, err := writeIssued(c.r.Context(), c.pool, d, ptrOwner(c.owner), c.at)
	if err != nil {
		return 0, "", err
	}
	if err := c.audit("invoice_issued",
		fmt.Sprintf("id=%d number=%s entity=%d total=%d", id, number, d.LegalEntityID, d.TotalHaler)); err != nil {
		return 0, "", err
	}
	return id, number, nil
}

func ptrOwner(owner int64) *int64 {
	if owner == 0 {
		return nil
	}
	return &owner
}

// errCancel is the ValueError keys of invoices.cancel.
type errCancel string

func (e errCancel) Error() string { return string(e) }

// cancelInvoice is invoices.cancel: a storno (non-payer) or ODD (payer)
// reversing an issued invoice. It returns the new invoice's id.
func (c *call) cancelInvoice(id int64, reason, correctionDate string) (int64, error) {
	ctx := c.r.Context()
	original, err := scanInvoice(c.pool.QueryRow(ctx, `SELECT `+invoiceColumns+` FROM invoice WHERE id = $1`, id))
	if errors.Is(err, pgx.ErrNoRows) || (err == nil && original.Kind != "invoice") {
		return 0, errCancel("not_cancellable")
	}
	if err != nil {
		return 0, err
	}
	if len([]rune(strings.TrimSpace(reason))) < 5 {
		return 0, errCancel("reason_required")
	}
	var other int64
	err = c.pool.QueryRow(ctx, `SELECT id FROM invoice WHERE corrects_invoice_id = $1 LIMIT 1`, id).Scan(&other)
	if err == nil {
		return 0, errCancel("already_corrected")
	}
	if !errors.Is(err, pgx.ErrNoRows) {
		return 0, err
	}
	items, err := loadItems(ctx, c.pool, id)
	if err != nil {
		return 0, err
	}
	kind := "storno"
	if original.VATStatus == "payer" {
		kind = "corrective"
	}
	today := pragueDay(c.at).Format("2006-01-02")
	dateText := correctionDate
	if dateText == "" {
		dateText = today
	}
	d, err := draftFromOriginal(ctx, c.pool, original, items, kind, strings.TrimSpace(reason), dateText, today)
	if err != nil {
		return 0, err
	}
	newID, _, err := writeIssued(ctx, c.pool, d, ptrOwner(c.owner), c.at)
	if err != nil {
		return 0, err
	}
	if err := c.audit("invoice_corrected",
		fmt.Sprintf("orig=%d new=%d kind=%s reason=%s", id, newID, kind, strings.TrimSpace(reason))); err != nil {
		return 0, err
	}
	return newID, nil
}

// draftFromOriginal is _draft_from_original: every amount negated.
func draftFromOriginal(ctx context.Context, pool *pgxpool.Pool, o invoiceRow, items []invoiceItemRow, kind, reason, correctionDate, today string) (draft, error) {
	neg := func(p *int64) *int64 {
		if p == nil {
			return nil
		}
		v := -*p
		return &v
	}
	d := draft{
		Kind: kind, Lang: o.Lang, VATStatus: o.VATStatus, IssueDate: today,
		PaidVia: o.PaidVia, LegalEntityID: o.LegalEntityID, ApartmentID: o.ApartmentID, ReservationID: o.ReservationID,
		CorrectsInvoiceID: ptr(o.ID), CorrectionReason: reason, OwnerUserID: o.OwnerUserID,
		Seller: sellerSnap{Name: o.SellerName, Seat: o.SellerSeat, ICO: o.SellerICO, DIC: o.SellerDIC,
			Registry: o.SellerRegistry, BankAccount: o.SellerBank, IBAN: o.SellerIBAN, BIC: o.SellerBIC,
			Email: o.SellerEmail, Phone: o.SellerPhone},
		Buyer: buyerSnap{Name: o.BuyerName, Street: o.BuyerStreet, City: o.BuyerCity, Zip: o.BuyerZip,
			Country: o.BuyerCountry, ICO: o.BuyerICO, DIC: o.BuyerDIC, Email: o.BuyerEmail},
		StayLabel:  o.StayLabel,
		TotalHaler: -o.TotalHaler,
	}
	if o.PaidOn != "" {
		d.PaidOn = today
	}
	if kind == "corrective" {
		d.CorrectionDate = correctionDate
	}
	if d.Buyer.Country == "" {
		d.Buyer.Country = "CZE"
	}
	// stay_from, stay_to, total_base_haler, total_vat_haler come from the
	// original row (they are not in invoiceColumns).
	var from, to *string
	var base, vat *int64
	if err := pool.QueryRow(ctx, `SELECT stay_from, stay_to, total_base_haler, total_vat_haler FROM invoice WHERE id = $1`,
		o.ID).Scan(&from, &to, &base, &vat); err != nil {
		return draft{}, err
	}
	if from != nil {
		d.StayFrom = *from
	}
	if to != nil {
		d.StayTo = *to
	}
	d.TotalBase, d.TotalVAT = neg(base), neg(vat)
	for _, it := range items {
		d.Items = append(d.Items, item{Kind: it.Kind, Description: it.Description, Quantity: it.Quantity,
			Unit: it.Unit, VATRate: it.VATRate, Base: neg(it.Base), VAT: neg(it.VAT), Gross: -it.Gross})
	}
	return d, nil
}

// downloadPDF is invoices.download_pdf: always the stored bytes, checked
// against their hash; an issued document is never re-rendered.
func downloadPDF(ctx context.Context, pool *pgxpool.Pool, id int64) ([]byte, error) {
	var blob []byte
	var sum *string
	err := pool.QueryRow(ctx, `SELECT pdf_blob, pdf_sha256 FROM invoice WHERE id = $1`, id).Scan(&blob, &sum)
	if err != nil {
		return nil, err
	}
	if len(blob) == 0 {
		return nil, errors.New("invoice_pdf_missing")
	}
	digest := sha256.Sum256(blob)
	if sum != nil && *sum != "" && hex.EncodeToString(digest[:]) != *sum {
		return nil, errors.New("invoice_pdf_mismatch")
	}
	return blob, nil
}
