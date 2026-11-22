package apartmententrycode

import (
	"reflect"
	"testing"
)

func slotKinds(slots []Slot) []string {
	out := make([]string, len(slots))
	for i, s := range slots {
		if s.Door {
			out[i] = "DOOR"
			continue
		}
		out[i] = s.Row.CodeType
	}
	return out
}

func TestEntryCodeGuestOrder(t *testing.T) {
	rows := []Row{{3, "other"}, {2, "garage"}, {1, "gate"}, {1, "bike_room"}, {2, "gate"}, {1, "building_entrance"}}
	want := []string{"gate", "gate", "building_entrance", "DOOR", "garage", "bike_room", "other"}
	if got := slotKinds(EntryCodeGuestOrder(rows, true)); !reflect.DeepEqual(got, want) {
		t.Fatalf("with lock %v want %v", got, want)
	}
	wantNL := []string{"gate", "gate", "building_entrance", "garage", "bike_room", "other"}
	if got := slotKinds(EntryCodeGuestOrder(rows, false)); !reflect.DeepEqual(got, wantNL) {
		t.Fatalf("no lock %v want %v", got, wantNL)
	}
}
