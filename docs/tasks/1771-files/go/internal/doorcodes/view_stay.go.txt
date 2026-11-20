package doorcodes

import "context"

// ViewForStay is door_codes.view(reservation, apartment) for the host stay
// page: it loads both rows by id and calls View. nil when either row is missing.
func (s *Service) ViewForStay(ctx context.Context, reservationID, apartmentID int64) (*Shown, error) {
	r, err := s.loadReservation(ctx, reservationID)
	if err != nil || r == nil {
		return nil, err
	}
	a, err := s.loadApartment(ctx, apartmentID)
	if err != nil || a == nil {
		return nil, err
	}
	return s.View(ctx, *r, *a)
}
