package schema

// Go port of App/scripts/pg_schema.py plan, check and apply. Apply runs only
// goose files on a database whose legacy schema Python set up once; a fresh,
// empty database stays a Python-only job (pg_schema.py apply or pg-cutover.sh).

import (
	"context"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"

	"github.com/jackc/pgx/v5"
)

// Lock ids of App/app/db_postgres.py: STARTUP_LOCK_ID, then WRITER_LOCK_ID.
const (
	StartupLockID = 593217222
	WriterLockID  = 593217221
)

// Config is one migrate run.
type Config struct {
	Action         string // plan, check or apply
	ExpectDatabase string
	DatabaseURL    string
	DataDir        string
	MigrationsDir  string
}

// errLegacy is returned when goose has nothing to build on.
var errLegacy = errors.New("legacy schema not set up; run App/scripts/pg_schema.py apply once")

// errPythonDDL is returned when the functions or triggers Python's apply
// re-creates differ from the app's; Go applies goose files only.
var errPythonDDL = errors.New("PostgreSQL functions or triggers differ from the app's (Python-owned DDL); " +
	"run App/scripts/pg_schema.py apply once (deploy with UBYHOST_SCHEMA_APPLY=python), then switch back")

// Run executes one action and prints the same OK line as pg_schema.py.
func Run(ctx context.Context, cfg Config, stdout io.Writer) error {
	switch cfg.Action {
	case "plan", "check", "apply":
	default:
		return fmt.Errorf("unknown action %q; use plan, check or apply", cfg.Action)
	}
	if cfg.ExpectDatabase == "" {
		return errors.New("--expect-database is required")
	}
	if cfg.DatabaseURL == "" {
		return errors.New("Set UBYHOST_DATABASE_URL to select PostgreSQL.")
	}
	if cfg.DataDir == "" {
		return errors.New("UBYHOST_DATA_DIR is required (it holds the authority marker)")
	}
	if _, err := ParseTarget(cfg.DatabaseURL); err != nil {
		return err
	}
	expected, err := LoadExpected()
	if err != nil {
		return err
	}
	files, err := Files(filepath.Clean(cfg.MigrationsDir))
	if err != nil {
		return err
	}
	if len(files) == 0 {
		return fmt.Errorf("no goose files in %s", cfg.MigrationsDir)
	}
	conn, err := pgx.Connect(ctx, cfg.DatabaseURL)
	if err != nil {
		return err
	}
	defer conn.Close(context.Background())
	for _, set := range []string{
		"SET statement_timeout = 60000",
		"SET lock_timeout = '30s'",
		"SET TIME ZONE 'UTC'",
		"SET search_path TO public",
	} {
		if _, err := conn.Exec(ctx, set); err != nil {
			return err
		}
	}
	var actual string
	var current *string
	if err := conn.QueryRow(ctx, "SELECT current_database(), current_schema()").Scan(&actual, &current); err != nil {
		return err
	}
	if current == nil || *current != "public" {
		return errors.New("PostgreSQL runtime requires the public schema search path.")
	}
	if err := CheckAuthority(cfg.DataDir, cfg.DatabaseURL, actual); err != nil {
		return err
	}
	if actual != cfg.ExpectDatabase {
		return errors.New("Connected database does not match --expect-database.")
	}
	switch cfg.Action {
	case "plan":
		pending, err := Pending(ctx, conn, cfg.MigrationsDir)
		if err != nil {
			return err
		}
		fmt.Fprintf(stdout, "PostgreSQL %s: schema version %d is planned; goose pending=%s; no changes made.\n",
			actual, expected.ExpectedVersion, pyList(pending))
		return nil
	case "check":
		status, pending, err := statusOf(ctx, conn, expected, cfg.MigrationsDir)
		if err != nil {
			return err
		}
		if status.PythonDDLStale() {
			return errPythonDDL
		}
		if !status.Current || len(pending) > 0 {
			return errors.New("PostgreSQL schema is not current; run the explicit apply command.")
		}
		return printOK(stdout, "check", actual, status, files, pending)
	}
	status, err := apply(ctx, conn, expected, cfg.MigrationsDir)
	if err != nil {
		return err
	}
	return printOK(stdout, "apply", actual, status, files, nil)
}

func statusOf(ctx context.Context, q Querier, expected Expected, dir string) (Status, []int, error) {
	a, err := ReadActual(ctx, q)
	if err != nil {
		return Status{}, nil, err
	}
	pending, err := pendingIn(ctx, q, dir)
	if err != nil {
		return Status{}, nil, err
	}
	return Compare(expected, a), pending, nil
}

// apply runs the pending goose files in one transaction under the session
// advisory locks Python takes, and commits only when the result is current.
func apply(ctx context.Context, conn *pgx.Conn, expected Expected, dir string) (Status, error) {
	for _, id := range []int64{StartupLockID, WriterLockID} {
		if _, err := conn.Exec(ctx, "SELECT pg_advisory_lock($1)", id); err != nil {
			return Status{}, err
		}
		defer conn.Exec(context.Background(), "SELECT pg_advisory_unlock($1)", id) //nolint:errcheck
	}
	tx, err := conn.Begin(ctx)
	if err != nil {
		return Status{}, err
	}
	defer tx.Rollback(context.Background()) //nolint:errcheck
	var gooseTable, migrationsTable *string
	if err := tx.QueryRow(ctx,
		"SELECT to_regclass('public.goose_db_version')::text, to_regclass('public.schema_migrations')::text").
		Scan(&gooseTable, &migrationsTable); err != nil {
		return Status{}, err
	}
	if gooseTable == nil || migrationsTable == nil {
		return Status{}, errLegacy
	}
	pending, err := pendingIn(ctx, tx, dir)
	if err != nil {
		return Status{}, err
	}
	for _, v := range pending {
		if v == 1 {
			return Status{}, errLegacy
		}
	}
	for _, v := range pending {
		path, err := fileFor(dir, v)
		if err != nil {
			return Status{}, err
		}
		text, err := os.ReadFile(path)
		if err != nil {
			return Status{}, err
		}
		statements, err := UpStatements(string(text))
		if err != nil {
			return Status{}, fmt.Errorf("%s: %w", filepath.Base(path), err)
		}
		for _, s := range statements {
			if _, err := tx.Exec(ctx, s); err != nil {
				return Status{}, fmt.Errorf("goose %05d: %w", v, err)
			}
		}
		if _, err := tx.Exec(ctx, "INSERT INTO goose_db_version (version_id, is_applied) VALUES ($1, true)", int64(v)); err != nil {
			return Status{}, err
		}
	}
	status, left, err := statusOf(ctx, tx, expected, dir)
	if err != nil {
		return Status{}, err
	}
	if status.PythonDDLStale() {
		return Status{}, fmt.Errorf("%w; nothing was committed", errPythonDDL)
	}
	if !status.Current {
		return Status{}, errors.New("PostgreSQL schema is absent, outdated, or incompatible after apply; nothing was committed.")
	}
	if len(left) > 0 {
		return Status{}, fmt.Errorf("goose migrations %s are still pending; nothing was committed", pyList(left))
	}
	if err := tx.Commit(ctx); err != nil {
		return Status{}, err
	}
	return status, nil
}

// pendingIn is Pending for a Querier (a transaction sees its own changes).
func pendingIn(ctx context.Context, q Querier, dir string) ([]int, error) {
	files, err := Files(filepath.Clean(dir))
	if err != nil {
		return nil, err
	}
	applied, err := appliedVersions(ctx, q)
	if err != nil {
		return nil, err
	}
	var pending []int
	for _, v := range files {
		if !applied[v] {
			pending = append(pending, v)
		}
	}
	return pending, nil
}

func fileFor(dir string, version int) (string, error) {
	matches, err := filepath.Glob(filepath.Join(dir, fmt.Sprintf("%05d_*.sql", version)))
	if err != nil {
		return "", err
	}
	if len(matches) != 1 {
		return "", fmt.Errorf("goose version %d has %d files", version, len(matches))
	}
	return matches[0], nil
}

func printOK(w io.Writer, action, database string, s Status, files, pending []int) error {
	skip := map[int]bool{}
	for _, v := range pending {
		skip[v] = true
	}
	highest := 0
	for _, v := range files {
		if !skip[v] && v > highest {
			highest = v
		}
	}
	_, err := fmt.Fprintf(w, "PostgreSQL schema %s OK: database=%s, version=%d, tables=%d, goose=%d.\n",
		action, database, s.ActualVersion, s.ActualTables, highest)
	return err
}

// pyList prints a version list like Python: [15, 16], or none when empty.
func pyList(vs []int) string {
	if len(vs) == 0 {
		return "none"
	}
	parts := make([]string, len(vs))
	for i, v := range vs {
		parts[i] = fmt.Sprint(v)
	}
	return "[" + strings.Join(parts, ", ") + "]"
}
