package onboarding

// Unit tests of the police and property page data the golden cannot reach
// (brief 1600): hours that are not 0 to 23 and the operator choice.

import "testing"

func TestWizardDoorWindow(t *testing.T) {
	for _, c := range []struct {
		in, out, start, end, startKey, endKey string
		complete                              bool
	}{
		{"15", "10", "14:00", "11:00", "door_code.window.arrival", "door_code.window.departure", true},
		{"0", "23", "23:00", "00:00", "door_code.window.previous", "door_code.window.next", true},
		{"", "10", "", "", "", "", false},
		{"24", "10", "", "", "", "", false},
		{"07", "10", "", "", "", "", false},
		{"x", "-1", "", "", "", "", false},
	} {
		v := &wizardView{DoorBuffer: 1, Values: wizardValues{CheckinHour: c.in, CheckoutHour: c.out}}
		w := v.DoorWindow()
		if w.Complete != c.complete || w.Start != c.start || w.End != c.end || w.StartKey != c.startKey || w.EndKey != c.endKey {
			t.Errorf("%q %q: %+v", c.in, c.out, w)
		}
	}
	v := &wizardView{Values: wizardValues{CheckinHour: "", CheckoutHour: "x"}}
	if s := v.HourSelects(); s[0].Selected != 15 || s[1].Selected != -1 {
		t.Errorf("hour selects %+v", s)
	}
}

func TestWizardOperatorSelected(t *testing.T) {
	id := func(n int64) *int64 { return &n }
	two := []wizardEntity{{ID: 31}, {ID: 32}}
	for _, c := range []struct {
		stored   *int64
		entities []wizardEntity
		want     int64
	}{
		{id(32), two, 32}, {id(33), two, 0}, {nil, two, 0}, {nil, two[:1], 31}, {id(99), two[:1], 31}, {nil, nil, 0},
	} {
		v := &wizardView{Apt: &wizardApt{LegalEntityID: c.stored}, Entities: c.entities}
		if got := v.OperatorSelected(); got != c.want {
			t.Errorf("stored %v entities %v: %d, want %d", c.stored, c.entities, got, c.want)
		}
	}
	for mode, want := range map[string]string{"manual": "manual", "scheduled": "scheduled", "immediate": "immediate", "": "manual", "off": "manual"} {
		if got := (&wizardView{Values: wizardValues{AutomationMode: mode}}).AutoMode(); got != want {
			t.Errorf("auto mode %q: %q", mode, got)
		}
	}
}
