// Package schema reports which goose migrations of App/migrations_pg are pending.
// It mirrors App/app/db.py goose_files and goose_applied.
package schema

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"

	"github.com/jackc/pgx/v5"
)

var gooseName = regexp.MustCompile(`^(\d{5})_([a-z0-9_]+)\.sql$`)

// Files returns the goose version numbers of the .sql files in dir, in order.
// A file name that breaks the NNNNN_name.sql rule, or a repeated version, is an error.
func Files(dir string) ([]int, error) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil, err
	}
	seen := map[int]string{}
	var versions []int
	for _, e := range entries {
		name := e.Name()
		if e.IsDir() || !strings.HasSuffix(name, ".sql") {
			continue
		}
		m := gooseName.FindStringSubmatch(name)
		if m == nil {
			return nil, fmt.Errorf("goose file %s must be NNNNN_name.sql", name)
		}
		version, err := strconv.Atoi(m[1])
		if err != nil {
			return nil, err
		}
		if other, ok := seen[version]; ok {
			return nil, fmt.Errorf("goose files %s and %s share version %d", other, name, version)
		}
		seen[version] = name
		versions = append(versions, version)
	}
	sort.Ints(versions)
	return versions, nil
}

// Pending returns the versions in dir whose newest goose_db_version row is not applied.
// The table is looked up through search_path. A missing table means everything is pending.
func Pending(ctx context.Context, conn *pgx.Conn, dir string) ([]int, error) {
	files, err := Files(filepath.Clean(dir))
	if err != nil {
		return nil, err
	}
	applied, err := appliedVersions(ctx, conn)
	if err != nil {
		return nil, err
	}
	var pending []int
	for _, v := range files {
		if !applied[v] {
			pending = append(pending, v)
		}
	}
	return pending, nil
}

func appliedVersions(ctx context.Context, conn *pgx.Conn) (map[int]bool, error) {
	applied := map[int]bool{}
	var name *string
	if err := conn.QueryRow(ctx, "SELECT to_regclass('goose_db_version')::text").Scan(&name); err != nil {
		return nil, err
	}
	if name == nil {
		return applied, nil
	}
	rows, err := conn.Query(ctx,
		"SELECT DISTINCT ON (version_id) version_id, is_applied FROM goose_db_version ORDER BY version_id, id DESC")
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	for rows.Next() {
		var version int64
		var isApplied bool
		if err := rows.Scan(&version, &isApplied); err != nil {
			return nil, err
		}
		if isApplied && version != 0 {
			applied[int(version)] = true
		}
	}
	return applied, rows.Err()
}
