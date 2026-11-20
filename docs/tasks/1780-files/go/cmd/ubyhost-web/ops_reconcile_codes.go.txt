package main

import (
	"context"
	"fmt"
	"io"
	"os"
	"os/signal"
	"syscall"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ops"
)

func init() {
	if len(os.Args) > 1 && os.Args[1] == "reconcile-accepted-codes" {
		os.Exit(runReconcileCodes(os.Args[2:], os.Getenv, os.Stdout, os.Stderr))
	}
}

func runReconcileCodes(args []string, getenv func(string) string, stdout, stderr io.Writer) int {
	apply := false
	for _, a := range args {
		if a == "--apply" {
			apply = true
		} else {
			fmt.Fprintln(stderr, "usage: ubyhost-web reconcile-accepted-codes [--apply]")
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
	code, err := ops.RunReconcileAcceptedCodes(ctx, pool, apply, stdout)
	if err != nil {
		fmt.Fprintln(stderr, err)
		return 1
	}
	return code
}
