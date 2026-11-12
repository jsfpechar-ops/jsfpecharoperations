package calendar

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// watchAlert is one alert row as App/scripts/check_deadlines_golden.py records it.
type watchAlert struct {
	Seed          *int64  `json:"seed"`
	Level         string  `json:"level"`
	Kind          string  `json:"kind"`
	ApartmentID   *int64  `json:"apartment_id"`
	ReservationID *int64  `json:"reservation_id"`
	OwnerUserID   *int64  `json:"owner_user_id"`
	DedupeKey     *string `json:"dedupe_key"`
	Message       string  `json:"message"`
	Detail        *string `json:"detail"`
	Params        *string `json:"params"`
	Created       string  `json:"created"`
	Resolved      string  `json:"resolved"`
	UserDismissed int64   `json:"user_dismissed"`
}

type watchSeedTable struct {
	Table   string   `json:"table"`
	Columns []string `json:"columns"`
	Rows    [][]any  `json:"rows"`
}

type watchRun struct {
	At          string       `json:"at"`
	OwnerUserID *int64       `json:"owner_user_id"`
	Raised      int          `json:"raised"`
	Alerts      []watchAlert `json:"alerts"`
}

type watchGolden struct {
	SeedCreated  string           `json:"seed_created"`
	SeedResolved string           `json:"seed_resolved"`
	Seed         []watchSeedTable `json:"seed"`
	Runs         []watchRun       `json:"runs"`
}

func loadWatchGolden(t *testing.T) watchGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/check_deadlines_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	var g watchGolden
	if err := dec.Decode(&g); err != nil {
		t.Fatal(err)
	}
	if len(g.Runs) == 0 || len(g.Seed) == 0 {
		t.Fatal("golden file has no runs or no seed")
	}
	return g
}

// watchValue turns a decoded seed value into what pgx writes: json numbers are ids and counts.
func watchValue(t *testing.T, v any) any {
	t.Helper()
	if n, ok := v.(json.Number); ok {
		i, err := n.Int64()
		if err != nil {
			t.Fatalf("seed number %q is not an integer", n)
		}
		return i
	}
	return v
}

// watchSeed inserts the golden seed rows and returns the seeded alert ids.
func watchSeed(t *testing.T, pool *pgxpool.Pool, g watchGolden) map[int64]bool {
	t.Helper()
	ids := map[int64]bool{}
	for _, table := range g.Seed {
		marks := make([]string, len(table.Columns))
		for i := range marks {
			marks[i] = fmt.Sprintf("$%d", i+1)
		}
		sql := "INSERT INTO " + table.Table + " (" + strings.Join(table.Columns, ", ") +
			") VALUES (" + strings.Join(marks, ", ") + ")"
		for _, row := range table.Rows {
			args := make([]any, len(row))
			for i, v := range row {
				args[i] = watchValue(t, v)
			}
			if _, err := pool.Exec(context.Background(), sql, args...); err != nil {
				t.Fatalf("seed %s: %v", table.Table, err)
			}
			if table.Table == "alert" {
				ids[args[0].(int64)] = true
			}
		}
	}
	return ids
}

// watchSnapshot reads every alert row the way the golden script records it.
func watchSnapshot(t *testing.T, pool *pgxpool.Pool, g watchGolden, seeded map[int64]bool) []watchAlert {
	t.Helper()
	rows, err := pool.Query(context.Background(),
		`SELECT id, level, kind, apartment_id, reservation_id, owner_user_id, dedupe_key,
		message, detail, params, created_at, resolved_at, user_dismissed FROM alert`)
	if err != nil {
		t.Fatal(err)
	}
	defer rows.Close()
	var out []watchAlert
	for rows.Next() {
		var a watchAlert
		var id int64
		var created string
		var resolved *string
		if err := rows.Scan(&id, &a.Level, &a.Kind, &a.ApartmentID, &a.ReservationID, &a.OwnerUserID,
			&a.DedupeKey, &a.Message, &a.Detail, &a.Params, &created, &resolved, &a.UserDismissed); err != nil {
			t.Fatal(err)
		}
		if seeded[id] {
			seed := id
			a.Seed = &seed
		}
		a.Created = "run"
		if created == g.SeedCreated {
			a.Created = "seed"
		}
		switch {
		case resolved == nil:
			a.Resolved = "open"
		case *resolved == g.SeedResolved:
			a.Resolved = "seed"
		default:
			a.Resolved = "run"
		}
		out = append(out, a)
	}
	if err := rows.Err(); err != nil {
		t.Fatal(err)
	}
	return out
}

// watchLines is each alert as one JSON line, sorted, so order does not matter.
func watchLines(t *testing.T, alerts []watchAlert) []string {
	t.Helper()
	out := make([]string, 0, len(alerts))
	for _, a := range alerts {
		b, err := json.Marshal(a)
		if err != nil {
			t.Fatal(err)
		}
		out = append(out, string(b))
	}
	sort.Strings(out)
	return out
}

// TestCheckDeadlinesMatchesPython seeds the golden stays, runs CheckDeadlines
// for every golden run and compares the return value and every alert row with
// what reporting.check_deadlines did on the same rows.
func TestCheckDeadlinesMatchesPython(t *testing.T) {
	g := loadWatchGolden(t)
	pool := dbPool(t)
	seeded := watchSeed(t, pool, g)
	for i, run := range g.Runs {
		at, err := time.Parse(time.RFC3339, run.At)
		if err != nil {
			t.Fatal(err)
		}
		raised, err := CheckDeadlines(context.Background(), pool, dbGetenv, at, run.OwnerUserID)
		if err != nil {
			t.Fatalf("run %d: %v", i+1, err)
		}
		if raised != run.Raised {
			t.Errorf("run %d: raised %d, Python raised %d", i+1, raised, run.Raised)
		}
		got := watchLines(t, watchSnapshot(t, pool, g, seeded))
		want := watchLines(t, run.Alerts)
		if strings.Join(got, "\n") != strings.Join(want, "\n") {
			t.Errorf("run %d alerts differ from Python\n got:\n%s\nwant:\n%s", i+1,
				strings.Join(got, "\n"), strings.Join(want, "\n"))
		}
	}
}

func TestWatchTitle(t *testing.T) {
	for _, c := range []struct{ from, to, want string }{
		{"2026-09-10", "2026-09-14", "Byt · 10.09.2026 – 14.09.2026"},
		{"bad", "2026-09-20", "Byt ·  – 20.09.2026"},
		{"2026-09-10", "", "Byt · 10.09.2026"},
		{"", "", "Byt · "},
	} {
		got := watchTitle(stayRow{property: "Byt", dateFrom: c.from, dateTo: c.to})
		if got != c.want {
			t.Errorf("watchTitle(%q, %q) = %q, want %q", c.from, c.to, got, c.want)
		}
	}
}
