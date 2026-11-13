package main

// Lane D (schema) owns this file: the startup schema check.

import (
	"context"
	"fmt"
	"log/slog"
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
