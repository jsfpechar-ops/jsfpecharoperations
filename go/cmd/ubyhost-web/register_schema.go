package main

// Lane D (schema) owns this file: the startup schema check, and the
// `ubyhost-web migrate plan|check|apply --expect-database <db>` command
// (Go port of App/scripts/pg_schema.py; brief 1260).

import (
	"context"
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

// runMigrate parses the action and --expect-database in any order, like
// pg_schema.py's argparse, and runs it. It returns the exit code: 0 OK,
// 1 failure, 2 bad usage.
func runMigrate(args []string, getenv func(string) string, stdout, stderr io.Writer) int {
	action, expect, ok := parseMigrateArgs(args)
	if !ok {
		fmt.Fprintln(stderr, "usage: ubyhost-web migrate plan|check|apply --expect-database <db>")
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
		ExpectDatabase: expect,
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

// parseMigrateArgs accepts one action (plan, check or apply) and
// --expect-database <db> or --expect-database=<db>, in either order. Any
// other argument, a second action or an empty database name is refused.
func parseMigrateArgs(args []string) (action, expect string, ok bool) {
	seenExpect := false
	for i := 0; i < len(args); i++ {
		a := args[i]
		switch {
		case a == "--expect-database":
			if i+1 >= len(args) || strings.HasPrefix(args[i+1], "-") {
				return "", "", false
			}
			i++
			expect, seenExpect = args[i], true
		case strings.HasPrefix(a, "--expect-database="):
			expect, seenExpect = strings.TrimPrefix(a, "--expect-database="), true
		case strings.HasPrefix(a, "-"):
			return "", "", false
		case action != "":
			return "", "", false
		default:
			action = a
		}
	}
	if action != "plan" && action != "check" && action != "apply" {
		return "", "", false
	}
	if !seenExpect || expect == "" {
		return "", "", false
	}
	return action, expect, true
}
