package schema

// Go port of App/app/db.py postgres_schema_status. Go has no SQLite, so the
// expected schema is a snapshot that App/scripts/pg_schema_golden.py writes
// from Python's own functions; App/tests/test_go_schema_golden.py fails when
// it is stale.

import (
	"context"
	_ "embed"
	"encoding/json"
	"fmt"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
)

//go:embed expected_schema.json
var expectedSchemaJSON []byte

// Column is one expected or actual column: its PostgreSQL data_type and
// whether it is NOT NULL.
type Column struct {
	Name    string `json:"name"`
	Type    string `json:"type"`
	NotNull bool   `json:"not_null"`
}

// Expected is the schema the current Python code expects.
type Expected struct {
	ExpectedVersion int                 `json:"expected_version"`
	Tables          map[string][]Column `json:"tables"`
	Indexes         []string            `json:"indexes"`
	Triggers        []string            `json:"triggers"`
}

// Actual is what a database has.
type Actual struct {
	Version  int
	Tables   map[string][]Column
	Indexes  map[string]bool
	Triggers map[string]bool
}

// Status mirrors the dict postgres_schema_status returns (goose pending apart).
type Status struct {
	ExpectedVersion  int
	ActualVersion    int
	ExpectedTables   int
	ActualTables     int
	MissingTables    int
	ExtraTables      int
	ColumnMismatches int
	MissingIndexes   int
	MissingTriggers  int
	ExtraTriggers    int
	Current          bool
}

// LoadExpected decodes the embedded snapshot.
func LoadExpected() (Expected, error) {
	var e Expected
	if err := json.Unmarshal(expectedSchemaJSON, &e); err != nil {
		return e, fmt.Errorf("expected_schema.json: %w", err)
	}
	if len(e.Tables) == 0 || e.ExpectedVersion <= 0 {
		return e, fmt.Errorf("expected_schema.json is empty")
	}
	return e, nil
}

// Compare is the "current" rule of postgres_schema_status.
func Compare(e Expected, a Actual) Status {
	s := Status{
		ExpectedVersion: e.ExpectedVersion,
		ActualVersion:   a.Version,
		ExpectedTables:  len(e.Tables),
		ActualTables:    len(a.Tables),
	}
	for table, cols := range e.Tables {
		got, ok := a.Tables[table]
		if !ok {
			s.MissingTables++
		}
		if len(cols) != len(got) {
			diff := len(cols) - len(got)
			if diff < 0 {
				diff = -diff
			}
			s.ColumnMismatches += diff
			continue
		}
		for i, want := range cols {
			// want.Type is "" for a SQLite type Python cannot map: never a match.
			if want.Name != got[i].Name || want.Type == "" || want.Type != got[i].Type || want.NotNull != got[i].NotNull {
				s.ColumnMismatches++
			}
		}
	}
	for table := range a.Tables {
		if _, ok := e.Tables[table]; !ok {
			s.ExtraTables++
		}
	}
	for _, name := range e.Indexes {
		if !a.Indexes[name] {
			s.MissingIndexes++
		}
	}
	want := map[string]bool{}
	for _, name := range e.Triggers {
		want[name] = true
		if !a.Triggers[name] {
			s.MissingTriggers++
		}
	}
	for name := range a.Triggers {
		if !want[name] {
			s.ExtraTriggers++
		}
	}
	s.Current = s.ExpectedVersion == s.ActualVersion && s.MissingTables == 0 &&
		s.ColumnMismatches == 0 && s.MissingIndexes == 0 && s.MissingTriggers == 0 && s.ExtraTriggers == 0
	return s
}

// Querier is a *pgx.Conn or a pgx.Tx.
type Querier interface {
	Exec(ctx context.Context, sql string, args ...any) (pgconn.CommandTag, error)
	Query(ctx context.Context, sql string, args ...any) (pgx.Rows, error)
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
}

// ReadActual reads the same catalog views postgres_schema_status reads.
func ReadActual(ctx context.Context, q Querier) (Actual, error) {
	a := Actual{Tables: map[string][]Column{}, Indexes: map[string]bool{}, Triggers: map[string]bool{}}
	rows, err := q.Query(ctx,
		"SELECT table_name, column_name, data_type, is_nullable "+
			"FROM information_schema.columns WHERE table_schema = current_schema() "+
			"AND table_name <> 'goose_db_version' "+
			"ORDER BY table_name, ordinal_position")
	if err != nil {
		return a, err
	}
	for rows.Next() {
		var table, name, dataType, nullable string
		if err := rows.Scan(&table, &name, &dataType, &nullable); err != nil {
			rows.Close()
			return a, err
		}
		// Python: "NO" is NOT NULL; anything but "YES" fails a nullable column too.
		col := Column{Name: name, Type: toLowerASCII(dataType), NotNull: nullable == "NO"}
		if nullable != "NO" && nullable != "YES" {
			col.Type = "?" + col.Type
		}
		a.Tables[table] = append(a.Tables[table], col)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return a, err
	}
	names := func(sql string, into map[string]bool) error {
		rows, err := q.Query(ctx, sql)
		if err != nil {
			return err
		}
		defer rows.Close()
		for rows.Next() {
			var n string
			if err := rows.Scan(&n); err != nil {
				return err
			}
			into[n] = true
		}
		return rows.Err()
	}
	if err := names("SELECT indexname FROM pg_indexes WHERE schemaname = current_schema()", a.Indexes); err != nil {
		return a, err
	}
	if err := names("SELECT t.tgname FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "+
		"JOIN pg_namespace n ON n.oid = c.relnamespace "+
		"WHERE n.nspname = current_schema() AND NOT t.tgisinternal", a.Triggers); err != nil {
		return a, err
	}
	var exists bool
	if err := q.QueryRow(ctx, "SELECT EXISTS (SELECT 1 FROM information_schema.tables "+
		"WHERE table_schema = current_schema() AND table_name = 'schema_migrations')").Scan(&exists); err != nil {
		return a, err
	}
	if exists {
		var v *int64
		if err := q.QueryRow(ctx, "SELECT MAX(version) FROM schema_migrations").Scan(&v); err != nil {
			return a, err
		}
		if v != nil {
			a.Version = int(*v)
		}
	}
	return a, nil
}

func toLowerASCII(s string) string {
	b := []byte(s)
	for i, c := range b {
		if c >= 'A' && c <= 'Z' {
			b[i] = c + 'a' - 'A'
		}
	}
	return string(b)
}
