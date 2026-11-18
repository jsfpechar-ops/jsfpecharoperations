package ruian

import (
	"archive/zip"
	"context"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// DefaultBaseURL is the only host the import talks to (named in the PR text).
const DefaultBaseURL = "https://vdp.cuzk.gov.cz/vymenny_format/csv"

// ProductionMinRows is the sanity floor: the real file has about 3.03 million rows.
const ProductionMinRows = 2_500_000

const (
	maxZipBytes = 300 << 20
	lockKey     = 1700001 // pg advisory lock: one import at a time
	downloadFor = 25 * time.Minute
)

// Options configure one Run. Zero values are not valid except Client and Now.
type Options struct {
	BaseURL string           // no trailing slash
	Dir     string           // writable folder for the .zip.part file
	MinRows int64            // fewer loaded rows than this keeps the old table
	Now     func() time.Time // default time.Now
	Client  *http.Client     // default: same-host redirects only
}

func (o *Options) client() *http.Client {
	if o.Client != nil {
		return o.Client
	}
	return &http.Client{CheckRedirect: func(req *http.Request, via []*http.Request) error {
		if req.URL.Host != via[0].URL.Host || len(via) > 3 {
			return errors.New("redirect to another host refused")
		}
		return nil
	}}
}

// candidates are the last day of the previous month and of the month before.
func candidates(now time.Time) []time.Time {
	first := time.Date(now.UTC().Year(), now.UTC().Month(), 1, 0, 0, 0, 0, time.UTC)
	return []time.Time{first.AddDate(0, 0, -1), first.AddDate(0, -1, -1)}
}

// newest returns the first candidate month whose zip answers HEAD 200; ok is false
// when every candidate answers 404.
func newest(ctx context.Context, o *Options) (date time.Time, ok bool, err error) {
	now := time.Now
	if o.Now != nil {
		now = o.Now
	}
	for _, d := range candidates(now()) {
		req, err := http.NewRequestWithContext(ctx, http.MethodHead, zipURL(o, d), nil)
		if err != nil {
			return d, false, err
		}
		req.Header.Set("User-Agent", "UbyHost")
		resp, err := o.client().Do(req)
		if err != nil {
			return d, false, err
		}
		resp.Body.Close()
		switch resp.StatusCode {
		case http.StatusOK:
			return d, true, nil
		case http.StatusNotFound:
		default:
			return d, false, fmt.Errorf("HEAD %s: status %d", d.Format("20060102"), resp.StatusCode)
		}
	}
	return time.Time{}, false, nil
}

func zipURL(o *Options, d time.Time) string {
	return o.BaseURL + "/" + d.Format("20060102") + "_OB_ADR_csv.zip"
}

func download(ctx context.Context, o *Options, d time.Time, dst string) error {
	ctx, cancel := context.WithTimeout(ctx, downloadFor)
	defer cancel()
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, zipURL(o, d), nil)
	if err != nil {
		return err
	}
	req.Header.Set("User-Agent", "UbyHost")
	resp, err := o.client().Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("GET %s: status %d", d.Format("20060102"), resp.StatusCode)
	}
	f, err := os.Create(dst)
	if err != nil {
		return err
	}
	n, err := io.Copy(f, io.LimitReader(resp.Body, maxZipBytes+1))
	if cerr := f.Close(); err == nil {
		err = cerr
	}
	if err == nil && n > maxZipBytes {
		err = errors.New("download larger than 300 MB")
	}
	return err
}

// Run loads the newest published month into ruian_address when it is not loaded
// yet (or the table is empty after a crash) and returns the rows loaded; 0 and
// no error when there is nothing to do. The old rows stay on any error.
func Run(ctx context.Context, pool *pgxpool.Pool, o Options) (int, error) {
	lock, err := pool.Acquire(ctx)
	if err != nil {
		return 0, err
	}
	defer lock.Release()
	var got bool
	if err := lock.QueryRow(ctx, "SELECT pg_try_advisory_lock($1)", lockKey).Scan(&got); err != nil || !got {
		return 0, err
	}
	defer lock.Exec(context.Background(), "SELECT pg_advisory_unlock($1)", lockKey)

	date, found, err := newest(ctx, &o)
	if err != nil || !found {
		return 0, err
	}
	var loaded *time.Time
	var prevRows int64
	err = pool.QueryRow(ctx, "SELECT data_date, rows FROM ruian_import WHERE id = 1").Scan(&loaded, &prevRows)
	if err != nil && !errors.Is(err, pgx.ErrNoRows) {
		return 0, err
	}
	var hasRows bool
	if err := pool.QueryRow(ctx, "SELECT EXISTS (SELECT 1 FROM ruian_address)").Scan(&hasRows); err != nil {
		return 0, err
	}
	if !hasRows {
		prevRows = 0
	}
	if hasRows && loaded != nil && loaded.Format("20060102") == date.Format("20060102") {
		return 0, nil
	}

	if err := os.MkdirAll(o.Dir, 0o700); err != nil {
		return 0, err
	}
	part := filepath.Join(o.Dir, date.Format("20060102")+".zip.part")
	defer os.Remove(part)
	if err := download(ctx, &o, date, part); err != nil {
		return 0, err
	}
	zr, err := zip.OpenReader(part)
	if err != nil {
		return 0, err
	}
	defer zr.Close()

	if _, err := pool.Exec(ctx, "DROP TABLE IF EXISTS ruian_address_new"); err != nil {
		return 0, err
	}
	if _, err := pool.Exec(ctx, "CREATE UNLOGGED TABLE ruian_address_new (LIKE ruian_address INCLUDING DEFAULTS)"); err != nil {
		return 0, err
	}
	var open pgx.Tx // a transaction still holding the staging table: roll it back first
	fail := func(err error) (int, error) {
		if open != nil {
			open.Rollback(context.Background())
		}
		pool.Exec(context.Background(), "DROP TABLE IF EXISTS ruian_address_new")
		return 0, err
	}
	n, err := pool.CopyFrom(ctx, pgx.Identifier{"ruian_address_new"}, columns, newZipRows(ctx, &zr.Reader))
	if err != nil {
		return fail(err)
	}
	if n < o.MinRows || (prevRows > 0 && n*10 < prevRows*9) {
		return fail(fmt.Errorf("ruian import: %d rows loaded, minimum %d, previous %d: old table kept", n, o.MinRows, prevRows))
	}

	tx, err := pool.Begin(ctx)
	if err != nil {
		return fail(err)
	}
	open = tx
	for _, q := range []string{
		"SET LOCAL maintenance_work_mem = '256MB'",
		"ALTER TABLE ruian_address_new ADD PRIMARY KEY (code)",
		"CREATE INDEX ruian_address_new_search_trgm ON ruian_address_new USING gin (search gin_trgm_ops)",
	} {
		if _, err := tx.Exec(ctx, q); err != nil {
			return fail(err)
		}
	}
	if err := tx.Commit(ctx); err != nil {
		return fail(err)
	}
	open = nil
	if _, err := pool.Exec(ctx, "ANALYZE ruian_address_new"); err != nil {
		return fail(err)
	}

	swap, err := pool.Begin(ctx)
	if err != nil {
		return fail(err)
	}
	open = swap
	for _, q := range []string{
		"DROP TABLE ruian_address",
		"ALTER TABLE ruian_address_new RENAME TO ruian_address",
		"ALTER INDEX ruian_address_new_pkey RENAME TO ruian_address_pkey",
		"ALTER INDEX ruian_address_new_search_trgm RENAME TO ruian_address_search_trgm",
	} {
		if _, err := swap.Exec(ctx, q); err != nil {
			return fail(err)
		}
	}
	if _, err := swap.Exec(ctx, `INSERT INTO ruian_import (id, data_date, rows, imported_at) VALUES (1, $1, $2, now())
		ON CONFLICT (id) DO UPDATE SET data_date = EXCLUDED.data_date, rows = EXCLUDED.rows, imported_at = EXCLUDED.imported_at`,
		date.Format("2006-01-02"), n); err != nil {
		return fail(err)
	}
	if err := swap.Commit(ctx); err != nil {
		return fail(err)
	}
	open = nil
	return int(n), nil
}
