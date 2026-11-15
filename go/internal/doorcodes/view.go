package doorcodes

import (
	"context"
	"fmt"
)

// Reservation is the reservation row fields the door-code flow reads.
type Reservation struct {
	ID                      int64
	ApartmentID             int64
	Source                  string
	Status                  string
	DateFrom                string
	DateTo                  string
	RegistrationCompletedAt *string
	ArchivedAt              *string
}

// Apartment is the apartment row fields the door-code flow reads.
type Apartment struct {
	ID           int64
	OwnerUserID  int64 // 0 when the apartment has no owner
	LockProvider string
	LockID       *string
	CheckinHour  *int64
	CheckoutHour *int64
	InternalName string
}

// Shown is what the guest and host pages show (view). State is one of delayed, preparing,
// waiting, failed or issued. The other fields are set when State is issued.
type Shown struct {
	State      string
	PIN        string
	WorksFrom  string
	WorksUntil string
	Checkin    string
	Checkout   string
	FirstUseBy string
}

// doorCode is one door_code row.
type doorCode struct {
	ID             int64
	ReservationID  int64
	ApartmentID    int64
	LockID         string
	CodeKind       *string
	State          string
	PinEnc         *string
	ProviderCodeID *string
	ValidFrom      *string
	ValidTo        *string
	Attempts       int64
	NextAttemptAt  *string
	ClaimedAt      *string
	LastError      *string
	NotifiedAt     *string
	IssuedAt       *string
}

const doorCodeColumns = "id, reservation_id, apartment_id, lock_id, code_kind, state, pin_enc, " +
	"provider_code_id, valid_from, valid_to, attempts, next_attempt_at, claimed_at, last_error, notified_at, issued_at"

// loadDoorCode returns the door_code row that matches where (for example "id = $1"), or nil.
func (s *Service) loadDoorCode(ctx context.Context, where string, args ...any) (*doorCode, error) {
	var d doorCode
	err := s.Pool.QueryRow(ctx, "SELECT "+doorCodeColumns+" FROM door_code WHERE "+where, args...).Scan(
		&d.ID, &d.ReservationID, &d.ApartmentID, &d.LockID, &d.CodeKind, &d.State, &d.PinEnc,
		&d.ProviderCodeID, &d.ValidFrom, &d.ValidTo, &d.Attempts, &d.NextAttemptAt, &d.ClaimedAt,
		&d.LastError, &d.NotifiedAt, &d.IssuedAt)
	if isNoRows(err) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &d, nil
}

// loadReservation returns the reservation with this id, or nil.
func (s *Service) loadReservation(ctx context.Context, id int64) (*Reservation, error) {
	var r Reservation
	err := s.Pool.QueryRow(ctx,
		"SELECT id, apartment_id, source, status, date_from, date_to, registration_completed_at, archived_at "+
			"FROM reservation WHERE id = $1", id).Scan(
		&r.ID, &r.ApartmentID, &r.Source, &r.Status, &r.DateFrom, &r.DateTo, &r.RegistrationCompletedAt, &r.ArchivedAt)
	if isNoRows(err) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &r, nil
}

// loadApartment returns the apartment with this id, or nil.
func (s *Service) loadApartment(ctx context.Context, id int64) (*Apartment, error) {
	var a Apartment
	err := s.Pool.QueryRow(ctx,
		"SELECT id, COALESCE(owner_user_id, 0), COALESCE(lock_provider, ''), lock_id, checkin_hour, checkout_hour, internal_name "+
			"FROM apartment WHERE id = $1", id).Scan(
		&a.ID, &a.OwnerUserID, &a.LockProvider, &a.LockID, &a.CheckinHour, &a.CheckoutHour, &a.InternalName)
	if isNoRows(err) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &a, nil
}

// View is view(reservation, apartment). It returns nil when the property has no door codes.
func (s *Service) View(ctx context.Context, r Reservation, a Apartment) (*Shown, error) {
	if a.LockProvider != "ttlock" || r.Source == "demo" {
		return nil, nil
	}
	if !s.Settings.Live && r.Source != "manual" {
		return nil, nil
	}
	row, err := s.loadDoorCode(ctx, "reservation_id = $1", r.ID)
	if err != nil {
		return nil, err
	}
	if row == nil {
		if r.RegistrationCompletedAt != nil {
			return s.preparing(*r.RegistrationCompletedAt), nil
		}
		return &Shown{State: "waiting"}, nil
	}
	switch row.State {
	case StatePending, StateIssuing, StateRetrying:
		if r.RegistrationCompletedAt != nil {
			return s.preparing(*r.RegistrationCompletedAt), nil
		}
		return &Shown{State: "waiting"}, nil
	case StateFailed:
		return &Shown{State: "failed"}, nil
	case StateExpired:
		return nil, nil
	}
	if row.State != StateIssued {
		return nil, nil
	}
	pin, err := s.decryptField(row.PinEnc)
	if err != nil {
		return nil, err
	}
	if pin == "" {
		return &Shown{State: "preparing"}, nil
	}
	return s.issuedView(r, a, row, pin)
}

// preparing is the delayed/preparing split of view: a guest who finished registering
// waits at most DelayMinutes before the page says it is delayed.
func (s *Service) preparing(registeredAt string) *Shown {
	if s.waited(&registeredAt) > DelayMinutes {
		return &Shown{State: "delayed"}
	}
	return &Shown{State: "preparing"}
}

// issuedView builds the issued case of view.
func (s *Service) issuedView(r Reservation, a Apartment, row *doorCode, pin string) (*Shown, error) {
	validFrom := derefOr(row.ValidFrom, "")
	validTo := derefOr(row.ValidTo, "")
	custom := derefOr(row.CodeKind, "") == "custom"
	if a.CheckinHour == nil || a.CheckoutHour == nil {
		return nil, fmt.Errorf("doorcodes: apartment %d has no check-in or check-out hour", a.ID)
	}
	out := &Shown{State: "issued", PIN: guestPinDisplay(pin)}
	var err error
	if validFrom != "" {
		if out.WorksFrom, err = fmtLocal(validFrom); err != nil {
			return nil, err
		}
	}
	if validTo != "" {
		if out.WorksUntil, err = fmtLocal(validTo); err != nil {
			return nil, err
		}
	}
	if out.Checkin, err = stayCheckinLabel(r.DateFrom, *a.CheckinHour); err != nil {
		return nil, err
	}
	if out.Checkout, err = stayCheckinLabel(r.DateTo, *a.CheckoutHour); err != nil {
		return nil, err
	}
	if validFrom != "" && !custom {
		ms, err := isoToMS(validFrom)
		if err != nil {
			return nil, err
		}
		out.FirstUseBy, err = fmtLocal(msToISO(ms + 24*3_600_000))
		if err != nil {
			return nil, err
		}
	}
	return out, nil
}
