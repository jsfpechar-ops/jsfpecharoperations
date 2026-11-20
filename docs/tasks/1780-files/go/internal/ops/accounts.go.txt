package ops

import (
	"context"
	"fmt"
	"io"

	"github.com/jackc/pgx/v5/pgxpool"
)

// RunListAccountsWithoutEmail is list_accounts_without_email.py.
func RunListAccountsWithoutEmail(ctx context.Context, pool *pgxpool.Pool, w io.Writer) (int, error) {
	rows, err := pool.Query(ctx, `SELECT id, role FROM user_account
WHERE active = 1 AND (email IS NULL OR TRIM(email) = '') ORDER BY id`)
	if err != nil {
		return 1, err
	}
	defer rows.Close()
	n := 0
	for rows.Next() {
		var id int64
		var role string
		if err := rows.Scan(&id, &role); err != nil {
			return 1, err
		}
		fmt.Fprintf(w, "id=%d role=%s\n", id, role)
		n++
	}
	if err := rows.Err(); err != nil {
		return 1, err
	}
	fmt.Fprintf(w, "active accounts without a login e-mail: %d\n", n)
	return 0, nil
}
