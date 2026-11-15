package doorcodes

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ttlock"
)

// testPool makes a throwaway database from UBYHOST_TEST_DATABASE_URL, applies
// the goose Up sections of App/migrations_pg and drops the database at the end.
// It skips when the variable is unset.
func testPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_doorcodes_%d", time.Now().UnixNano())
	admin, err := pgx.Connect(ctx, base)
	if err != nil {
		t.Fatal("admin connect failed")
	}
	if _, err := admin.Exec(ctx, "CREATE DATABASE "+name); err != nil {
		admin.Close(ctx)
		t.Fatal(err)
	}
	admin.Close(ctx)
	t.Cleanup(func() {
		c, err := pgx.Connect(context.Background(), base)
		if err != nil {
			t.Errorf("admin connect for cleanup failed")
			return
		}
		defer c.Close(context.Background())
		if _, err := c.Exec(context.Background(), "DROP DATABASE IF EXISTS "+name+" WITH (FORCE)"); err != nil {
			t.Errorf("drop test database: %v", err)
		}
	})
	cfg, err := pgxpool.ParseConfig(base)
	if err != nil {
		t.Fatal("bad UBYHOST_TEST_DATABASE_URL")
	}
	cfg.ConnConfig.Database = name
	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(pool.Close)
	applyMigrations(t, pool)
	return pool
}

func applyMigrations(t *testing.T, pool *pgxpool.Pool) {
	t.Helper()
	files, err := filepath.Glob("../../../App/migrations_pg/*.sql")
	if err != nil || len(files) == 0 {
		t.Fatal("no migrations found")
	}
	sort.Strings(files)
	for _, f := range files {
		raw, err := os.ReadFile(f)
		if err != nil {
			t.Fatal(err)
		}
		up := string(raw)
		if i := strings.Index(up, "-- +goose Up"); i >= 0 {
			up = up[i+len("-- +goose Up"):]
		}
		if i := strings.Index(up, "-- +goose Down"); i >= 0 {
			up = up[:i]
		}
		if _, err := pool.Exec(context.Background(), up); err != nil {
			t.Fatalf("%s: %v", filepath.Base(f), err)
		}
	}
}

// Fakes. None of them reaches the real TTLock API, mail, or alerts.

type fakeClock struct{ t time.Time }

func (c *fakeClock) Now() time.Time { return c.t }

type fakeTTLock struct {
	create func() (string, string, error)
	add    func() (string, string, error)
	find   func() (string, string, bool, error)
}

func (f *fakeTTLock) Enabled() bool { return true }

func (f *fakeTTLock) CreatePeriodCode(_ context.Context, _ int64, _ string, _, _ int64, _, _ string) (string, string, error) {
	return f.create()
}

func (f *fakeTTLock) AddCustomCode(_ context.Context, _ int64, _ string, _, _ int64, _, _ string) (string, string, error) {
	return f.add()
}

func (f *fakeTTLock) FindCodeByName(_ context.Context, _ int64, _, _ string, _, _ int64) (string, string, bool, error) {
	return f.find()
}

type fakePlans struct{ allowed bool }

func (p *fakePlans) TTLockAllowed(_ context.Context, _ int64) (bool, error) { return p.allowed, nil }

type fakeAlerts struct {
	raised   []Alert
	resolved []string
}

func (a *fakeAlerts) Raise(_ context.Context, in Alert) error {
	a.raised = append(a.raised, in)
	return nil
}

func (a *fakeAlerts) Resolve(_ context.Context, key string) error {
	a.resolved = append(a.resolved, key)
	return nil
}

type fakeMailer struct {
	notices  []string
	enqueued []OutboxMail
	drained  int
}

func (m *fakeMailer) BuildDoorCode(_ context.Context, _ DoorCodeMail) (DoorCodeContent, error) {
	return DoorCodeContent{Subject: "Your door code"}, nil
}

func (m *fakeMailer) GuestPayload(_ context.Context, _ int64, _ DoorCodeContent, _ string) (map[string]any, error) {
	return map[string]any{"reply_to": "host@example.test"}, nil
}

func (m *fakeMailer) DoorCodeNotice(_ context.Context, _ int64, stage string) error {
	m.notices = append(m.notices, stage)
	return nil
}

func (m *fakeMailer) Enqueue(_ context.Context, out OutboxMail) (int64, bool, error) {
	m.enqueued = append(m.enqueued, out)
	return int64(len(m.enqueued)), true, nil
}

func (m *fakeMailer) Drain(_ context.Context, _ int) error {
	m.drained++
	return nil
}

type fakeBilling struct{}

func (fakeBilling) ReservationProgress(_ context.Context, _ int64) (int, *int, error) {
	return 0, nil, nil
}

func (fakeBilling) CompletionFee(_ context.Context, _, _ int64) (map[string]any, error) {
	return nil, nil
}

type fakeConfirm struct{ calls []int64 }

func (c *fakeConfirm) MaybeNotifyCompletion(_ context.Context, reservationID, _ int64, _ bool) error {
	c.calls = append(c.calls, reservationID)
	return nil
}

// fixture is one eligible stay (2026-11-15 to 2026-11-18, check-in 14:00, check-out 10:00)
// with its pending door_code row, a lock account, and a guest claim with its confirmation sent.
type fixture struct {
	t      *testing.T
	ctx    context.Context
	svc    *Service
	clk    *fakeClock
	tl     *fakeTTLock
	plans  *fakePlans
	alerts *fakeAlerts
	mail   *fakeMailer
	conf   *fakeConfirm
	now    time.Time
	apt    int64
	acc    int64
	res    int64
	dc     int64
}

func newFixture(t *testing.T) *fixture {
	t.Helper()
	ctx := context.Background()
	pool := testPool(t)
	keys, err := secure.NewMultiFernet(secure.LegacyKey("doorcodes-test-secret"))
	if err != nil {
		t.Fatal(err)
	}
	now := time.Date(2026, 11, 15, 10, 0, 0, 0, time.UTC)
	f := &fixture{
		t:      t,
		ctx:    ctx,
		clk:    &fakeClock{t: now},
		now:    now,
		plans:  &fakePlans{allowed: true},
		alerts: &fakeAlerts{},
		mail:   &fakeMailer{},
		conf:   &fakeConfirm{},
	}
	f.tl = &fakeTTLock{
		create: func() (string, string, error) { return "123456", "code-1", nil },
		add:    func() (string, string, error) { return "654321", "custom-1", nil },
		find:   func() (string, string, bool, error) { return "", "", false, nil },
	}
	f.svc = &Service{
		Pool:     pool,
		Keys:     keys,
		Settings: Settings{Enabled: true, Live: true, BufferHours: 1},
		TTLock:   f.tl,
		Accounts: NewAccountStore(pool, keys),
		Plans:    f.plans,
		Alerts:   f.alerts,
		Mailer:   f.mail,
		Billing:  fakeBilling{},
		Confirm:  f.conf,
		Clock:    f.clk,
	}
	if _, err := pool.Exec(ctx, "INSERT INTO user_account (id, username, password_hash, created_at) VALUES (7, 'owner7', 'x', $1)", iso(now)); err != nil {
		t.Fatal(err)
	}
	acc, err := f.svc.Accounts.Insert(ctx, 7, "uhx", "password", now)
	if err != nil {
		t.Fatal(err)
	}
	f.acc = acc
	if err := pool.QueryRow(ctx,
		"INSERT INTO apartment (internal_name, owner_user_id, lock_provider, lock_id, checkin_hour, checkout_hour, created_at) "+
			"VALUES ('Test flat', 7, 'ttlock', '555', 14, 10, $1) RETURNING id", iso(now)).Scan(&f.apt); err != nil {
		t.Fatal(err)
	}
	f.res = f.insertReservation("2026-11-15", "2026-11-18")
	f.dc = f.ensure(f.res)
	if _, err := pool.Exec(ctx,
		"INSERT INTO reservation_claim (reservation_id, state, email, lang, completion_notified_at, created_at, updated_at) "+
			"VALUES ($1, 'claimed', 'guest@example.test', 'en', $2, $2, $2)", f.res, iso(now)); err != nil {
		t.Fatal(err)
	}
	return f
}

func (f *fixture) insertReservation(dateFrom, dateTo string) int64 {
	f.t.Helper()
	var id int64
	uid := fmt.Sprintf("uid-%s-%s-%d", dateFrom, dateTo, time.Now().UnixNano())
	if err := f.svc.Pool.QueryRow(f.ctx,
		"INSERT INTO reservation (apartment_id, uid, date_from, date_to, registration_completed_at, status, source, created_at, updated_at) "+
			"VALUES ($1, $2, $3, $4, $5, 'active', 'manual', $6, $6) RETURNING id",
		f.apt, uid, dateFrom, dateTo, iso(f.now.Add(-time.Hour)), iso(f.now)).Scan(&id); err != nil {
		f.t.Fatal(err)
	}
	return id
}

func (f *fixture) ensure(resID int64) int64 {
	f.t.Helper()
	id, ok, err := f.svc.EnsureRow(f.ctx, resID)
	if err != nil || !ok {
		f.t.Fatalf("EnsureRow ok=%v err=%v", ok, err)
	}
	return id
}

func (f *fixture) issue(allowGateway bool) bool {
	f.t.Helper()
	return f.issueRow(f.dc, allowGateway)
}

func (f *fixture) issueRow(id int64, allowGateway bool) bool {
	f.t.Helper()
	ok, err := f.svc.Issue(f.ctx, id, allowGateway)
	if err != nil {
		f.t.Fatalf("Issue: %v", err)
	}
	return ok
}

func (f *fixture) row(id int64) *doorCode {
	f.t.Helper()
	d, err := f.svc.loadDoorCode(f.ctx, "id = $1", id)
	if err != nil || d == nil {
		f.t.Fatalf("loadDoorCode: %v %v", d, err)
	}
	return d
}

func (f *fixture) exec(sql string, args ...any) {
	f.t.Helper()
	if _, err := f.svc.Pool.Exec(f.ctx, sql, args...); err != nil {
		f.t.Fatal(err)
	}
}

func wantState(t *testing.T, d *doorCode, state string, attempts int64) {
	t.Helper()
	if d.State != state || d.Attempts != attempts {
		t.Fatalf("state=%s attempts=%d, want state=%s attempts=%d (last_error=%q)",
			d.State, d.Attempts, state, attempts, derefOr(d.LastError, ""))
	}
}

func wantLastError(t *testing.T, d *doorCode, want string) {
	t.Helper()
	if got := derefOr(d.LastError, ""); got != want {
		t.Fatalf("last_error=%q, want %q", got, want)
	}
}

func wantNext(t *testing.T, d *doorCode, want time.Time) {
	t.Helper()
	if got := derefOr(d.NextAttemptAt, ""); got != iso(want) {
		t.Fatalf("next_attempt_at=%q, want %q", got, iso(want))
	}
}

func TestIssueSuccess(t *testing.T) {
	f := newFixture(t)
	if !f.issue(false) {
		t.Fatal("issue returned false")
	}
	d := f.row(f.dc)
	wantState(t, d, StateIssued, 1)
	if derefOr(d.ProviderCodeID, "") != "code-1" || derefOr(d.CodeKind, "") != "random" {
		t.Fatalf("provider=%q kind=%q", derefOr(d.ProviderCodeID, ""), derefOr(d.CodeKind, ""))
	}
	if d.ClaimedAt != nil || d.LastError != nil {
		t.Fatalf("claimed_at and last_error must be cleared")
	}
	pin, err := f.svc.decryptField(d.PinEnc)
	if err != nil || pin != "123456" {
		t.Fatalf("pin=%q err=%v", pin, err)
	}
	if got := len(f.alerts.resolved); got != 3 {
		t.Fatalf("resolved %d alerts, want 3", got)
	}
	// The stay is live, so the code mail goes out in the same call.
	if len(f.mail.enqueued) != 1 || f.mail.enqueued[0].Kind != "door_code" || f.mail.drained != 1 {
		t.Fatalf("mail enqueued=%d drained=%d", len(f.mail.enqueued), f.mail.drained)
	}
	if d.NotifiedAt == nil {
		t.Fatal("notified_at not set after the mail was queued")
	}
	var audits int
	if err := f.svc.Pool.QueryRow(f.ctx, "SELECT count(*) FROM audit WHERE action = 'door_code_issued'").Scan(&audits); err != nil || audits != 1 {
		t.Fatalf("audit rows=%d err=%v", audits, err)
	}
}

func TestIssueGatewayErrorRetriesWithBackoff(t *testing.T) {
	f := newFixture(t)
	f.tl.create = func() (string, string, error) {
		return "", "", &ttlock.TTLockError{Kind: ttlock.KindOffline, Message: "lock gateway down"}
	}
	if f.issue(false) {
		t.Fatal("issue returned true on a gateway error")
	}
	d := f.row(f.dc)
	wantState(t, d, StateRetrying, 1)
	wantLastError(t, d, "offline")
	wantNext(t, d, f.now.Add(time.Minute))
	if d.ClaimedAt != nil {
		t.Fatal("claimed_at must be cleared on retry")
	}
	if len(f.alerts.raised) != 0 || len(f.mail.notices) != 0 {
		t.Fatal("a retry must not alert or notify the host")
	}
}

func TestIssuePermanentErrorFailsAtOnce(t *testing.T) {
	f := newFixture(t)
	f.tl.create = func() (string, string, error) {
		return "", "", &ttlock.TTLockError{Kind: ttlock.KindPermission, Code: -1, Message: "no rights"}
	}
	if f.issue(false) {
		t.Fatal("issue returned true")
	}
	wantState(t, f.row(f.dc), StateFailed, 1)
	if len(f.alerts.raised) != 1 || f.alerts.raised[0].DedupeKey != fmt.Sprintf("door_code_failed:%d", f.res) {
		t.Fatalf("alerts=%+v", f.alerts.raised)
	}
	if len(f.mail.notices) != 1 || f.mail.notices[0] != "failed" {
		t.Fatalf("notices=%v", f.mail.notices)
	}
	if len(f.conf.calls) != 1 || f.conf.calls[0] != f.res {
		t.Fatalf("confirmation released for %v", f.conf.calls)
	}
}

func TestIssueFailsAfterMaxAttempts(t *testing.T) {
	f := newFixture(t)
	f.tl.create = func() (string, string, error) {
		return "", "", &ttlock.TTLockError{Kind: ttlock.KindTransient, Message: "server fault"}
	}
	if f.issue(false) {
		t.Fatal("first try returned true")
	}
	wantState(t, f.row(f.dc), StateRetrying, 1)
	// The row is due again after its one-minute backoff.
	f.clk.t = f.now.Add(2 * time.Minute)
	if f.issue(false) {
		t.Fatal("second try returned true")
	}
	d := f.row(f.dc)
	if d.Attempts != IssueMaxAttempts {
		t.Fatalf("attempts=%d, want %d", d.Attempts, IssueMaxAttempts)
	}
	wantState(t, d, StateFailed, IssueMaxAttempts)
	if len(f.alerts.raised) != 1 || f.mail.notices[len(f.mail.notices)-1] != "failed" {
		t.Fatalf("alerts=%d notices=%v", len(f.alerts.raised), f.mail.notices)
	}
}

func TestIssuePeriodTakenRetriesThenGatewayAdds(t *testing.T) {
	f := newFixture(t)
	f.tl.create = func() (string, string, error) {
		return "", "", &ttlock.TTLockError{Kind: ttlock.KindPeriodTaken, Code: -1026, Message: "taken"}
	}
	if f.issue(false) {
		t.Fatal("period taken returned true without the gateway")
	}
	d := f.row(f.dc)
	wantState(t, d, StateRetrying, 1)
	wantLastError(t, d, "period_taken:-1026")
	wantNext(t, d, f.now)
	if len(f.mail.notices) != 1 || f.mail.notices[0] != ttlock.KindPeriodTaken {
		t.Fatalf("notices=%v", f.mail.notices)
	}
	// The next try (attempts 2) finds nothing by name and adds a custom code through the gateway.
	if !f.issue(true) {
		t.Fatal("gateway retry returned false")
	}
	d = f.row(f.dc)
	wantState(t, d, StateIssued, 2)
	if derefOr(d.CodeKind, "") != "custom" || derefOr(d.ProviderCodeID, "") != "custom-1" {
		t.Fatalf("kind=%q provider=%q", derefOr(d.CodeKind, ""), derefOr(d.ProviderCodeID, ""))
	}
}

func TestIssuePeriodSharedHeldByOther(t *testing.T) {
	f := newFixture(t)
	start, end, err := ttlock.StayWindow("2026-11-15", "2026-11-18", 14, 10, 1)
	if err != nil {
		t.Fatal(err)
	}
	// Another stay already stores the code the lock returns for this period.
	other := f.insertReservation("2026-11-20", "2026-11-22")
	f.exec(`INSERT INTO door_code (reservation_id, apartment_id, lock_id, code_kind, state, provider_code_id, valid_from, valid_to, attempts, created_at, updated_at)
		VALUES ($1, $2, '555', 'random', 'issued', 'code-1', $3, $4, 1, $5, $5)`,
		other, f.apt, msToISO(start), msToISO(end), iso(f.now))
	f.tl.create = func() (string, string, error) { return "1", "code-1", nil }

	if f.issue(false) {
		t.Fatal("period shared returned true without the gateway")
	}
	d := f.row(f.dc)
	wantState(t, d, StateRetrying, 1)
	wantLastError(t, d, "period_taken:shared")
	if len(f.mail.notices) != 1 || f.mail.notices[0] != PeriodShared {
		t.Fatalf("notices=%v", f.mail.notices)
	}
	// On the retry get finds the shared code by name: it is skipped and a custom code is added.
	f.tl.find = func() (string, string, bool, error) { return "1", "code-1", true, nil }
	if !f.issue(true) {
		t.Fatal("retry with the gateway returned false")
	}
	d = f.row(f.dc)
	wantState(t, d, StateIssued, 2)
	if derefOr(d.CodeKind, "") != "custom" {
		t.Fatalf("kind=%q, want custom", derefOr(d.CodeKind, ""))
	}
}

func TestIssueStayEndedExpires(t *testing.T) {
	f := newFixture(t)
	// Check-out at 06:00 on the last day: the window ended before the clock's 10:00 UTC.
	f.exec("UPDATE apartment SET checkout_hour = 6 WHERE id = $1", f.apt)
	res := f.insertReservation("2026-11-14", "2026-11-15")
	dc := f.ensure(res)
	if f.issueRow(dc, false) {
		t.Fatal("ended stay returned true")
	}
	wantState(t, f.row(dc), StateExpired, 0)
}

func TestIssueReleasesToPending(t *testing.T) {
	cases := []struct {
		name   string
		setup  func(f *fixture)
		reason string
		wait   time.Duration
	}{
		{"not eligible", func(f *fixture) { f.plans.allowed = false }, "not_eligible", 15 * time.Minute},
		{"no account", func(f *fixture) { f.exec("DELETE FROM lock_account WHERE id = $1", f.acc) }, "no_account", 15 * time.Minute},
		{"bad window", func(f *fixture) { f.exec("UPDATE apartment SET checkin_hour = 25 WHERE id = $1", f.apt) }, "bad_window", 60 * time.Minute},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			f := newFixture(t)
			c.setup(f)
			if f.issue(false) {
				t.Fatal("issue returned true")
			}
			d := f.row(f.dc)
			wantState(t, d, StatePending, 0)
			wantLastError(t, d, c.reason)
			wantNext(t, d, f.now.Add(c.wait))
			if d.ClaimedAt != nil {
				t.Fatal("claimed_at must be cleared on release")
			}
		})
	}
}

func TestIssueClaimIsCompareAndSet(t *testing.T) {
	f := newFixture(t)
	f.exec("UPDATE door_code SET state = 'issued' WHERE id = $1", f.dc)
	if f.issue(false) {
		t.Fatal("an issued row was claimed again")
	}
	if d := f.row(f.dc); d.State != StateIssued || d.Attempts != 0 {
		t.Fatalf("state=%s attempts=%d changed by a lost claim", d.State, d.Attempts)
	}
}

func TestIssueMovesAreDeclared(t *testing.T) {
	moves := [][2]string{
		{StatePending, StateIssuing}, {StateRetrying, StateIssuing}, {StateIssuing, StatePending},
		{StateIssuing, StateExpired}, {StateIssuing, StateRetrying}, {StateIssuing, StateIssued},
		{StateIssuing, StateFailed},
	}
	for _, m := range moves {
		if !allowedMove(m[0], m[1]) {
			t.Fatalf("move %s -> %s is not in TRANSITIONS", m[0], m[1])
		}
	}
	if allowedMove(StateFailed, StateIssued) {
		t.Fatal("a failed row must not move back to issued")
	}
}

func TestAccountStoreRoundTrip(t *testing.T) {
	f := newFixture(t)
	acc, err := f.svc.Accounts.Load(f.ctx, f.acc)
	if err != nil || acc == nil {
		t.Fatalf("Load: %v %v", acc, err)
	}
	if acc.Password != "password" || acc.Username != "uhx" || acc.Status != ttlock.AccountStatusOK {
		t.Fatalf("account = %+v", acc)
	}
	if err := f.svc.Accounts.SaveLogin(f.ctx, f.acc, ttlock.TokenRecord{
		AccessToken: "a1", RefreshToken: "r1", ExpiresAt: f.now.Add(time.Hour),
	}, f.now); err != nil {
		t.Fatal(err)
	}
	acc, _ = f.svc.Accounts.Load(f.ctx, f.acc)
	if acc.AccessToken != "a1" || acc.RefreshToken != "r1" || acc.TokenVersion != 1 || !acc.ExpiresAt.Equal(f.now.Add(time.Hour)) {
		t.Fatalf("after login: %+v", acc)
	}
	if ok, err := f.svc.Accounts.SaveRefresh(f.ctx, f.acc, 0, ttlock.TokenRecord{AccessToken: "x", RefreshToken: "y"}, f.now); err != nil || ok {
		t.Fatalf("stale SaveRefresh ok=%v err=%v", ok, err)
	}
	if ok, err := f.svc.Accounts.SaveRefresh(f.ctx, f.acc, 1, ttlock.TokenRecord{AccessToken: "a2", RefreshToken: "r2"}, f.now); err != nil || !ok {
		t.Fatalf("SaveRefresh ok=%v err=%v", ok, err)
	}
	acc, _ = f.svc.Accounts.Load(f.ctx, f.acc)
	if acc.AccessToken != "a2" || acc.TokenVersion != 2 || !acc.ExpiresAt.IsZero() {
		t.Fatalf("after refresh: %+v", acc)
	}
	if err := f.svc.Accounts.SetStatus(f.ctx, f.acc, ttlock.AccountStatusReauthNeeded, f.now); err != nil {
		t.Fatal(err)
	}
	if err := f.svc.Accounts.SaveLocks(f.ctx, f.acc, []byte(`[{"lockId":"555"}]`), f.now); err != nil {
		t.Fatal(err)
	}
	acc, _ = f.svc.Accounts.Load(f.ctx, f.acc)
	if acc.Status != ttlock.AccountStatusReauthNeeded || string(acc.LocksJSON) != `[{"lockId":"555"}]` {
		t.Fatalf("after status and locks: %+v", acc)
	}
	if err := f.svc.Accounts.Delete(f.ctx, f.acc); err != nil {
		t.Fatal(err)
	}
	if acc, err := f.svc.Accounts.Load(f.ctx, f.acc); err != nil || acc != nil {
		t.Fatalf("after delete: %+v %v", acc, err)
	}
}
