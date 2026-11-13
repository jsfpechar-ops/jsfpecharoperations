package schema

// Go port of the database authority marker checks: App/scripts/pg_schema.py
// (database and schema must match) and App/app/config.py
// assert_database_authority (format, backend, schema, target fingerprint).
// Go only reads the marker; sealing it stays Python's seal-authority.

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
)

// AuthorityFile is the marker's name inside UBYHOST_DATA_DIR.
const AuthorityFile = "database-authority.json"

// CheckAuthority refuses a target that does not match the durable marker.
// No marker means no fence yet, as in Python.
func CheckAuthority(dataDir, databaseURL, actualDatabase string) error {
	raw, err := os.ReadFile(filepath.Join(dataDir, AuthorityFile))
	if errors.Is(err, os.ErrNotExist) {
		return nil
	}
	if err != nil {
		return errors.New("Database authority marker is unreadable; refusing startup.")
	}
	var marker map[string]any
	if err := json.Unmarshal(raw, &marker); err != nil || marker == nil {
		return errors.New("Database authority marker is unreadable; refusing startup.")
	}
	if database, _ := marker["database"].(string); database != actualDatabase || marker["schema"] != "public" {
		return errors.New("Connected PostgreSQL target does not match the durable authority marker.")
	}
	if !isPythonOne(marker["format_version"]) || marker["backend"] != "postgresql" {
		return errors.New("Database authority marker is invalid; refusing startup.")
	}
	want, err := Fingerprint(databaseURL)
	if err != nil {
		return err
	}
	if got, _ := marker["target_fingerprint"].(string); got != want {
		return errors.New("UBYHOST_DATABASE_URL does not match the durable database authority marker.")
	}
	return nil
}

// isPythonOne is Python's value == 1 for a decoded JSON value (1, 1.0, true).
func isPythonOne(v any) bool {
	switch x := v.(type) {
	case float64:
		return x == 1
	case bool:
		return x
	}
	return false
}
