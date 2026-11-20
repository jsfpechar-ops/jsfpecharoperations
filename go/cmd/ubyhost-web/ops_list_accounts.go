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
	if len(os.Args) > 1 && os.Args[1] == "list-accounts-without-email" {
		os.Exit(runListAccounts(os.Getenv, os.Stdout, os.Stderr))
	}
}

func runListAccounts(getenv func(string) string, stdout, stderr io.Writer) int {
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	pool, err := ops.Pool(ctx, getenv)
	if err != nil {
		fmt.Fprintln(stderr, err)
		return 1
	}
	defer pool.Close()
	code, err := ops.RunListAccountsWithoutEmail(ctx, pool, stdout)
	if err != nil {
		fmt.Fprintln(stderr, err)
		return 1
	}
	return code
}
