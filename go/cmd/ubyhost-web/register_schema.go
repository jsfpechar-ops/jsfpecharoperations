package main

// Lane D (schema) owns this file: the startup schema check, and the
// `ubyhost-web migrate plan|check|apply --expect-database <db>` command
// (Go port of App/scripts/pg_schema.py; brief 1260).

import (
	"context"
	"flag"
	"fmt"
	"io"
	"log/slog"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"github.com/jackc/pgx/v5"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/schema"
)

// checkSchema refuses to start while goose files are pending. It logs the
// reason itself and returns a non-nil error, so run() returns 1.
func checkSchema(ctx context.Context, dbURL, migrations string, redact func(error) string) error {
	startCtx, cancelStart := context.WithTimeout(ctx, 10*time.Second)
	conn, err := pgx.Connect(startCtx, dbURL)
	if err != nil {
		cancelStart()
		slog.Error("database connect failed", "error", redact(err))
		return err
	}
	pending, err := schema.Pending(startCtx, conn, migrations)
	_ = conn.Close(startCtx)
	cancelStart()
	if err != nil {
		slog.Error("goose check failed", "error", redact(err))
		return err
	}
	if len(pending) > 0 {
		err := fmt.Errorf("goose files pending: %v", pending)
		slog.Error(err.Error())
		return err
	}
	return nil
}

// init runs the migrate command instead of the server when the first
// argument is "migrate". main.go stays untouched.
func init() {
	if args, ok := migrateArgs(os.Args); ok {
		os.Exit(runMigrate(args, os.Getenv, os.Stdout, os.Stderr))
	}
}

// migrateArgs returns the arguments after "migrate", and whether it is there.
func migrateArgs(argv []string) ([]string, bool) {
	if len(argv) > 1 && argv[1] == "migrate" {
		return argv[2:], true
	}
	return nil, false
}

// runMigrate parses `<action> --expect-database <db>` and runs it. It
// returns the exit code: 0 OK, 1 failure, 2 bad usage.
func runMigrate(args []string, getenv func(string) string, stdout, stderr io.Writer) int {
	usage := "usage: ubyhost-web migrate plan|check|apply --expect-database <db>"
	if len(args) == 0 {
		fmt.Fprintln(stderr, usage)
		return 2
	}
	action := args[0]
	if action != "plan" && action != "check" && action != "apply" {
		fmt.Fprintln(stderr, usage)
		return 2
	}
	fs := flag.NewFlagSet("migrate "+action, flag.ContinueOnError)
	fs.SetOutput(stderr)
	expect := fs.String("expect-database", "", "database name the URL must connect to")
	if err := fs.Parse(args[1:]); err != nil || fs.NArg() != 0 || *expect == "" {
		fmt.Fprintln(stderr, usage)
		return 2
	}
	dbURL := getenv("UBYHOST_DATABASE_URL")
	migrations := getenv("UBYHOST_MIGRATIONS_DIR")
	if migrations == "" {
		migrations = "App/migrations_pg"
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	err := schema.Run(ctx, schema.Config{
		Action:         action,
		ExpectDatabase: *expect,
		DatabaseURL:    dbURL,
		DataDir:        getenv("UBYHOST_DATA_DIR"),
		MigrationsDir:  migrations,
	}, stdout)
	if err != nil {
		msg := err.Error()
		if dbURL != "" {
			msg = strings.ReplaceAll(msg, dbURL, "<redacted>")
		}
		fmt.Fprintf(stderr, "PostgreSQL schema %s failed: %s\n", action, msg)
		return 1
	}
	return 0
}
