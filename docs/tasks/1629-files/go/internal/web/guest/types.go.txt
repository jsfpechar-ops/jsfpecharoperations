package guest

// GuideApartment is the slice of apartment row the guide view needs.
type GuideApartment struct {
	ID          int64
	OwnerUserID int64
	Name        string
}

// GuideReservation is the reservation row for booked_level.
type GuideReservation struct {
	ID       int64
	DateFrom string
	DateTo   string
}
