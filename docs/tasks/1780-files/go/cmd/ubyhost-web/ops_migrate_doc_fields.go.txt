package main

import (
	"context"
	"fmt"
	"io"
	"os"
	"os/signal"
	"syscall"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ops"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

func init() {
	if len(os.Args) > 1 && os.Args[1] == "migrate-encrypt-doc-fields" {
		os.Exit(runMigrateDocFields(os.Args[2:], os.Getenv, os.Stdout, os.Stderr))
	}
}

func runMigrateDocFields(args []string, getenv func(string) string, stdout, stderr io.Writer) int {
	cfg := ops.DocFieldsConfig{}
	for _, a := range args {
		switch a {
		case "--dry-run":
			cfg.DryRun = true
		case "--check":
			cfg.Check = true
		case "--rollback":
			cfg.Rollback = true
		default:
			fmt.Fprintln(stderr, "usage: ubyhost-web migrate-encrypt-doc-fields [--dry-run|--check|--rollback]")
			return 2
		}
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	pool, err := ops.Pool(ctx, getenv)
	if err != nil {
		fmt.Fprintln(stderr, err)
		return 1
	}
	defer pool.Close()
	var mf *secure.MultiFernet
	if !cfg.Check {
		mf, err = ops.Keys(getenv)
		if err != nil {
			fmt.Fprintln(stderr, err)
			return 1
		}
	}
	code, runErr := ops.RunDocFields(ctx, pool, mf, cfg, getenv, stdout)
	if runErr != nil {
		fmt.Fprintln(stderr, runErr)
		return 1
	}
	return code
}
