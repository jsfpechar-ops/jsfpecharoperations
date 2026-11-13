// Package photosweep is the photo_sweep job, App/app/scheduler.py
// _job_photo_sweep, in Go. This file holds the two file steps:
// passport_photos.purge_stale (App/app/passport_photos.py) and
// guide_photos.purge_orphans (App/app/guide_photos.py). db.go holds the three
// database steps, sweep.go runs all five in the job's order.
//
// Parity: testdata/photo_sweep_golden.json, written by
// App/scripts/photo_sweep_golden.py from the real Python, is what the Go test
// must reproduce. Python is the reference: when they differ, Go is wrong.
package photosweep

import (
	"context"
	"errors"
	"fmt"
	"io/fs"
	"math/big"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"syscall"
	"time"
	"unicode"

	"github.com/jackc/pgx/v5/pgxpool"
)

const (
	// photoAfterCheckinDays is passport_photos.PHOTO_AFTER_CHECKIN_DAYS.
	photoAfterCheckinDays = 7
	// photoMaxAgeDays is passport_photos.PHOTO_MAX_AGE_DAYS.
	photoMaxAgeDays = 30
	// encSuffix is passport_photos.ENC_SUFFIX.
	encSuffix = ".enc"
	// guideOrphanAge is the one hour guide_photos.purge_orphans leaves a new
	// file alone (add writes the file before its row).
	guideOrphanAge = time.Hour
)

// allExtensions is passport_photos.ALL_EXTENSIONS, in the same sorted order.
var allExtensions = []string{".jpg", ".pdf", ".png", ".webp"}

// staleGuestsSQL is the query of passport_photos.purge_stale for the global
// sweep (owner_user_id None, so its "? IS NULL OR" filter is always true and
// left out). ubyhost_sqlite_date is what db.sqlite_date_expr names on
// PostgreSQL. ORDER BY only makes runs repeatable.
const staleGuestsSQL = `SELECT g.id, g.passport_photo_at FROM guest g
	JOIN reservation r ON r.id = g.reservation_id
	JOIN apartment a ON a.id = r.apartment_id
	WHERE (g.identity_verified_at IS NOT NULL
	OR COALESCE(ubyhost_sqlite_date(g.stay_from), ubyhost_sqlite_date(r.date_from)) <= $1
	OR ubyhost_sqlite_date(g.passport_photo_at) <= $2)
	ORDER BY g.id`

// photosDir and guideDir are passport_photos.PHOTOS_DIR and
// guide_photos.PHOTOS_DIR under the data directory.
func photosDir(dataDir string) string { return filepath.Join(dataDir, "passport_photos") }
func guideDir(dataDir string) string  { return filepath.Join(dataDir, "guide_photos") }

// ignoredStatError is pathlib's _ignore_error (Python 3.12): these errors make
// is_file and is_dir answer false; every other error is raised.
func ignoredStatError(err error) bool {
	return errors.Is(err, fs.ErrNotExist) || errors.Is(err, syscall.ENOTDIR) ||
		errors.Is(err, syscall.EBADF) || errors.Is(err, syscall.ELOOP)
}

// statMode is the shared part of isFile and isDir: os.Stat follows symlinks,
// like Path.stat().
func statMode(path string) (fs.FileMode, bool, error) {
	info, err := os.Stat(path)
	if err != nil {
		if ignoredStatError(err) {
			return 0, false, nil
		}
		return 0, false, err
	}
	return info.Mode(), true, nil
}

// isFile is pathlib.Path.is_file.
func isFile(path string) (bool, error) {
	mode, ok, err := statMode(path)
	return ok && mode.IsRegular(), err
}

// isDir is pathlib.Path.is_dir.
func isDir(path string) (bool, error) {
	mode, ok, err := statMode(path)
	return ok && mode.IsDir(), err
}

// removeFile unlinks one file. A file that is already gone is not an error
// (another process won the race); any other error, a read-only mount
// included, fails the job.
func removeFile(path string) error {
	if err := os.Remove(path); err != nil && !errors.Is(err, fs.ErrNotExist) {
		return fmt.Errorf("photo sweep: remove %s: %w", filepath.Base(path), err)
	}
	return nil
}

// pathsFor is passport_photos._paths_for: id is the decimal guest id.
func pathsFor(dir, id string) []string {
	out := make([]string, 0, 2*len(allExtensions))
	for _, ext := range allExtensions {
		out = append(out, filepath.Join(dir, id+ext+encSuffix), filepath.Join(dir, id+ext))
	}
	return out
}

// hasPhoto is passport_photos.has_photo.
func hasPhoto(dir, id string) (bool, error) {
	for _, p := range pathsFor(dir, id) {
		ok, err := isFile(p)
		if err != nil || ok {
			return ok, err
		}
	}
	return false, nil
}

// deletePhoto is passport_photos.delete_photo.
func deletePhoto(dir, id string) error {
	for _, p := range pathsFor(dir, id) {
		ok, err := isFile(p)
		if err != nil {
			return err
		}
		if ok {
			if err := removeFile(p); err != nil {
				return err
			}
		}
	}
	return nil
}

// pySuffix is PurePath(name).suffix.
func pySuffix(name string) string {
	i := strings.LastIndex(name, ".")
	if 0 < i && i < len(name)-1 {
		return name[i:]
	}
	return ""
}

// pyStem is PurePath(name).stem.
func pyStem(name string) string {
	i := strings.LastIndex(name, ".")
	if 0 < i && i < len(name)-1 {
		return name[:i]
	}
	return name
}

// pySpace is str.isspace for one rune: Go's White_Space plus the four
// separators U+001C..U+001F that Python also strips.
func pySpace(r rune) bool {
	return unicode.IsSpace(r) || (r >= 0x1c && r <= 0x1f)
}

// pyDigit is the value of a Unicode decimal digit (category Nd), as int()
// reads it. Every Nd run in Unicode starts at its zero, so the value is the
// distance from the start of the run, modulo 10.
func pyDigit(r rune) (int64, bool) {
	if r >= '0' && r <= '9' {
		return int64(r - '0'), true
	}
	if !unicode.Is(unicode.Nd, r) {
		return 0, false
	}
	start := r
	for unicode.Is(unicode.Nd, start-1) {
		start--
	}
	return int64(r-start) % 10, true
}

// pyInt is Python's int(s) for a str in base 10: surrounding whitespace, one
// optional sign, Unicode decimal digits with single underscores between them.
// ok is false where int() raises ValueError.
func pyInt(s string) (*big.Int, bool) {
	s = strings.TrimFunc(s, pySpace)
	neg := false
	if strings.HasPrefix(s, "+") || strings.HasPrefix(s, "-") {
		neg = s[0] == '-'
		s = s[1:]
	}
	n := new(big.Int)
	ten := big.NewInt(10)
	digits := 0
	prevUnderscore := false
	for _, r := range s {
		if r == '_' {
			if digits == 0 || prevUnderscore {
				return nil, false
			}
			prevUnderscore = true
			continue
		}
		d, ok := pyDigit(r)
		if !ok {
			return nil, false
		}
		n.Mul(n, ten).Add(n, big.NewInt(d))
		digits++
		prevUnderscore = false
	}
	if digits == 0 || prevUnderscore {
		return nil, false
	}
	if neg {
		n.Neg(n)
	}
	return n, true
}

// orphanIDs is passport_photos._orphan_ids: the ids, as decimal strings in
// numeric order, that files in dir name and no guest row has. An id beyond the
// bigint range can name no guest row, so it is an orphan without a lookup.
func orphanIDs(ctx context.Context, pool *pgxpool.Pool, dir string) ([]string, error) {
	ok, err := isDir(dir)
	if err != nil || !ok {
		return nil, err
	}
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil, err
	}
	found := map[string]*big.Int{}
	for _, e := range entries {
		file, err := isFile(filepath.Join(dir, e.Name()))
		if err != nil {
			return nil, err
		}
		if !file {
			continue
		}
		name := strings.TrimSuffix(e.Name(), encSuffix)
		ext := strings.ToLower(pySuffix(name))
		known := false
		for _, a := range allExtensions {
			known = known || ext == a
		}
		if !known {
			continue
		}
		if n, ok := pyInt(pyStem(name)); ok {
			found[n.String()] = n
		}
	}
	if len(found) == 0 {
		return nil, nil
	}
	var lookup []int64
	for _, n := range found {
		if n.IsInt64() {
			lookup = append(lookup, n.Int64())
		}
	}
	if len(lookup) > 0 {
		rows, err := pool.Query(ctx, `SELECT id FROM guest WHERE id = ANY($1)`, lookup)
		if err != nil {
			return nil, err
		}
		for rows.Next() {
			var id int64
			if err := rows.Scan(&id); err != nil {
				rows.Close()
				return nil, err
			}
			delete(found, strconv.FormatInt(id, 10))
		}
		rows.Close()
		if err := rows.Err(); err != nil {
			return nil, err
		}
	}
	nums := make([]*big.Int, 0, len(found))
	for _, n := range found {
		nums = append(nums, n)
	}
	sort.Slice(nums, func(i, j int) bool { return nums[i].Cmp(nums[j]) < 0 })
	out := make([]string, len(nums))
	for i, n := range nums {
		out[i] = n.String()
	}
	return out, nil
}

// purgePassportPhotos is passport_photos.purge_stale() for the global sweep.
// today is the server-local date (Python's date.today()). It returns the
// number of photos removed and writes the retention audit line, zero included.
func purgePassportPhotos(ctx context.Context, pool *pgxpool.Pool, dataDir string, today, now time.Time) (int, error) {
	dir := photosDir(dataDir)
	day := func(back int) string {
		return time.Date(today.Year(), today.Month(), today.Day()-back, 0, 0, 0, 0, time.UTC).Format("2006-01-02")
	}
	checkin, uploaded := day(photoAfterCheckinDays), day(photoMaxAgeDays)
	rows, err := pool.Query(ctx, staleGuestsSQL, checkin, uploaded)
	if err != nil {
		return 0, err
	}
	type stale struct {
		id     int64
		marked *string
	}
	var list []stale
	for rows.Next() {
		var s stale
		if err := rows.Scan(&s.id, &s.marked); err != nil {
			rows.Close()
			return 0, err
		}
		list = append(list, s)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return 0, err
	}
	removed := 0
	for _, s := range list {
		id := strconv.FormatInt(s.id, 10)
		has, err := hasPhoto(dir, id)
		if err != nil {
			return removed, err
		}
		if has {
			if err := deletePhoto(dir, id); err != nil {
				return removed, err
			}
			removed++
		}
		// Python: `if row["marked"]`, so an empty string is left as it is.
		if s.marked != nil && *s.marked != "" {
			if _, err := pool.Exec(ctx, `UPDATE guest SET passport_photo_at = NULL WHERE id = $1`, s.id); err != nil {
				return removed, err
			}
		}
	}
	orphans, err := orphanIDs(ctx, pool, dir)
	if err != nil {
		return removed, err
	}
	for _, id := range orphans {
		if err := deletePhoto(dir, id); err != nil {
			return removed, err
		}
		removed++
	}
	cutoff := "check-in on or before " + checkin + "; upload on or before " + uploaded + "; or verified"
	if err := auditRetention(ctx, pool, now, "passport_photos", removed, cutoff); err != nil {
		return removed, err
	}
	return removed, nil
}

// purgeGuideOrphans is guide_photos.purge_orphans: files in guide_photos that
// no guide_photo row names and that are more than an hour old.
func purgeGuideOrphans(ctx context.Context, pool *pgxpool.Pool, dataDir string, now time.Time) (int, error) {
	dir := guideDir(dataDir)
	ok, err := isDir(dir)
	if err != nil || !ok {
		return 0, err
	}
	known := map[string]bool{}
	rows, err := pool.Query(ctx, `SELECT file_name FROM guide_photo`)
	if err != nil {
		return 0, err
	}
	for rows.Next() {
		var name string
		if err := rows.Scan(&name); err != nil {
			rows.Close()
			return 0, err
		}
		known[name] = true
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return 0, err
	}
	entries, err := os.ReadDir(dir)
	if err != nil {
		return 0, err
	}
	cutoff := now.Add(-guideOrphanAge)
	removed := 0
	for _, e := range entries {
		path := filepath.Join(dir, e.Name())
		file, err := isFile(path)
		if err != nil {
			return removed, err
		}
		if !file || known[e.Name()] {
			continue
		}
		info, err := os.Stat(path)
		if err != nil {
			return removed, err
		}
		if !info.ModTime().Before(cutoff) {
			continue
		}
		if err := removeFile(path); err != nil {
			return removed, err
		}
		removed++
	}
	return removed, nil
}
