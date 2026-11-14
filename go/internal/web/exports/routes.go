package exports

import (
	"net/http"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// Route is one pattern for http.ServeMux with its metrics label.
type Route struct {
	Pattern string
	Label   string
	Handler http.HandlerFunc
}

// Routes lists the export routes. It does not use the pool: the handlers
// read it only when a request comes in.
//
// "/submissions/{id}/{which}.xml" is not a valid ServeMux pattern, so
// {file} takes the last segment; receipt.pdf and errors.pdf are more
// specific and win over it.
func Routes(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) []Route {
	return []Route{
		{"GET /reservations.csv", "/reservations.csv", ReservationsCSVHandler(pool, getenv, now)},
		{"GET /submissions/receipts.zip", "/submissions/receipts.zip", ReceiptsZipHandler(pool, getenv, now)},
		{"GET /submissions/{id}/receipt.pdf", "/submissions/{id}/receipt.pdf", SubmissionPDFHandler(pool, getenv, now, "receipt")},
		{"GET /submissions/{id}/errors.pdf", "/submissions/{id}/errors.pdf", SubmissionPDFHandler(pool, getenv, now, "errors")},
		{"GET /submissions/{id}/{file}", "/submissions/{id}/{file}", SubmissionFileHandler(pool, getenv, now)},
		{"GET /reservations/{id}/dorucenka.zip", "/reservations/{id}/dorucenka.zip", StayReceiptsHandler(pool, getenv, now)},
		{"GET /housebook.csv", "/housebook.csv", HousebookCSVHandler(pool, getenv, now)},
		{"GET /guests/{id}/export.json", "/guests/{id}/export.json", GuestExportHandler(pool, getenv, now)},
		// Brief 1605.
		{"GET /guests/{id}/form.pdf", "/guests/{id}/form.pdf", GuestFormPDFHandler(pool, getenv, now)},
		// Brief 1606.
		{"GET /housebook/pdfs.zip", "/housebook/pdfs.zip", HousebookPDFsHandler(pool, getenv, now)},
		// Brief 1607.
		{"POST /settings/workspace-export", "/settings/workspace-export", WorkspaceExportHandler(pool, getenv, now)},
		// Brief 1608.
		{"GET /settings/archived", "/settings/archived", ArchivedHandler(pool, getenv, now)},
	}
}
