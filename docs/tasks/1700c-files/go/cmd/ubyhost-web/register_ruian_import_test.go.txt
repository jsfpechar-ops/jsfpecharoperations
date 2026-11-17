package main

import "testing"

func TestRuianImportSwitches(t *testing.T) {
	env := func(m map[string]string) func(string) string { return func(k string) string { return m[k] } }
	for name, c := range map[string]struct {
		env  map[string]string
		want bool
	}{
		"unset is dormant":      {map[string]string{}, false},
		"opt in":                {map[string]string{"UBYHOST_RUIAN_IMPORT": "1"}, true},
		"opt in, feature off":   {map[string]string{"UBYHOST_RUIAN_IMPORT": "1", "UBYHOST_RUIAN_ENABLED": "0"}, false},
		"opt in, scheduler off": {map[string]string{"UBYHOST_RUIAN_IMPORT": "1", "UBYHOST_ENABLE_SCHEDULER": "0"}, false},
		"other value":           {map[string]string{"UBYHOST_RUIAN_IMPORT": "yes"}, false},
	} {
		if got := ruianImportEnabled(env(c.env)); got != c.want {
			t.Errorf("%s: got %v, want %v", name, got, c.want)
		}
	}
}

func TestRuianImportTaskRegisteredOnce(t *testing.T) {
	n := 0
	for _, task := range backgroundTasks {
		if task.name == "ruian_import" {
			n++
		}
	}
	if n != 1 {
		t.Fatalf("ruian_import registered %d times", n)
	}
	t.Setenv("UBYHOST_RUIAN_IMPORT", "")
	if run, err := ruianImportTask(nil); run != nil || err != nil {
		t.Fatal("dormant task must return nothing")
	}
}
