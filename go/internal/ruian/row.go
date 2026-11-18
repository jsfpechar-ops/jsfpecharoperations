package ruian

import (
	"archive/zip"
	"bufio"
	"context"
	"fmt"
	"io"
	"path"
	"strconv"
	"strings"

	"golang.org/x/text/encoding/charmap"
)

// columns are the ruian_address columns in COPY order.
var columns = []string{"code", "street", "house_no", "orient_no", "is_evid", "zip",
	"obec", "obec_code", "part", "district", "okres", "search"}

// parseLine turns one data line of an OB_ADR csv (19 columns, ";" between,
// no quotes, already UTF-8) into a COPY row. ok is false for a header, a short
// line or a row without a numeric code, house number or obec code.
func parseLine(line string) (row []any, ok bool) {
	f := strings.Split(strings.TrimRight(line, "\r\n"), ";")
	if len(f) < 16 {
		return nil, false
	}
	code, err := strconv.ParseInt(f[0], 10, 64)
	if err != nil || code <= 0 {
		return nil, false
	}
	obecCode, err := strconv.Atoi(f[1])
	if err != nil || f[12] == "" {
		return nil, false
	}
	orient := f[13] + f[14]
	district := f[4]
	if district == "" {
		district = f[6]
	}
	zipCode := strings.ReplaceAll(f[15], " ", "")
	return []any{code, f[10], f[12], orient, f[11] == "č.ev.", zipCode,
		f[2], int32(obecCode), f[8], district, Okres(obecCode),
		SearchText(f[10], f[12], orient, f[8], f[2], zipCode)}, true
}

// zipRows streams the rows of every .csv entry of a zip, one line at a time:
// it never holds more than one line and the decoder buffer in memory. It
// implements pgx.CopyFromSource.
type zipRows struct {
	ctx     context.Context
	files   []*zip.File
	next    int
	cur     io.Closer
	scan    *bufio.Scanner
	row     []any
	err     error
	Skipped int64
}

func newZipRows(ctx context.Context, zr *zip.Reader) *zipRows {
	z := &zipRows{ctx: ctx}
	for _, f := range zr.File {
		if !f.FileInfo().IsDir() && strings.EqualFold(path.Ext(f.Name), ".csv") {
			z.files = append(z.files, f)
		}
	}
	return z
}

func (z *zipRows) Next() bool {
	for {
		if z.scan == nil {
			if z.next >= len(z.files) {
				return false
			}
			rc, err := z.files[z.next].Open()
			if err != nil {
				z.err = fmt.Errorf("open %s: %w", z.files[z.next].Name, err)
				return false
			}
			z.next++
			z.cur = rc
			z.scan = bufio.NewScanner(charmap.Windows1250.NewDecoder().Reader(rc))
			z.scan.Buffer(make([]byte, 0, 64*1024), 1<<20)
			z.scan.Scan() // the header line
			if err := z.ctx.Err(); err != nil {
				z.err = err
				return false
			}
		}
		if z.scan.Scan() {
			if row, ok := parseLine(z.scan.Text()); ok {
				z.row = row
				return true
			}
			z.Skipped++
			continue
		}
		if err := z.scan.Err(); err != nil {
			z.err = err
			return false
		}
		z.cur.Close()
		z.scan = nil
	}
}

func (z *zipRows) Values() ([]any, error) { return z.row, nil }
func (z *zipRows) Err() error             { return z.err }
