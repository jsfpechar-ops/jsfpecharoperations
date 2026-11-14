package billingweb

// The route table of the subscription billing area. Each brief of the thread
// 1555 to 1560 replaces this file with the table that holds its routes.

import (
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// deps are what every handler needs.
type deps struct {
	pool   *pgxpool.Pool
	getenv func(string) string
	now    func() time.Time
	ares   *AresClient
}

func newDeps(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) deps {
	return deps{pool: pool, getenv: getenv, now: now, ares: &AresClient{}}
}

// Routes lists the ported routes. It never touches the pool, so it can be
// called with a nil one.
func Routes(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) []Route {
	return newRoutes(newDeps(pool, getenv, now))
}

// newRoutes is Routes with its dependencies given, so a test can swap the ARES client.
func newRoutes(d deps) []Route {
	return []Route{
		{"GET /predplatne/faktury/{file}", d.hostInvoicePDF},
		{"POST /predplatne/zrusit", d.hostCancel},
		{"POST /predplatne/obnovit", d.hostResume},
		{"GET /admin/fakturace/{file}", d.adminInvoicePDF},
		{"GET /predplatne", d.hostPlanPage},
		{"POST /predplatne", d.hostPlanOrder},
		{"POST /predplatne/zmena", d.hostPlanChange},
		{"POST /admin/fakturace/vypis", d.adminStatement},
		{"POST /admin/fakturace/{invoice_id}/zaplaceno", d.adminMarkPaid},
		{"POST /admin/fakturace/{invoice_id}/storno", d.adminStorno},
		{"GET /admin/fakturace/export-vse", d.adminExportAll},
		{"GET /admin/fakturace/export", d.adminExport},
	}
}
