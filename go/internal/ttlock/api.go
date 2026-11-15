package ttlock

import (
	"context"
	"crypto/rand"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math/big"
	"strconv"
	"strings"
	"time"
	_ "time/tzdata" // the stay window uses Europe/Prague; embed the zone database so no system tzdata is needed
)

const (
	adminKeyStatus = "110401" // ttlock.py _ADMIN_STATUS
	topAdminType   = "110301" // ttlock.py _TOP_ADMIN
	// stayZone is config.TIMEZONE.
	stayZone = "Europe/Prague"

	// ListPageSize and ListMaxPages are ttlock.py LIST_PAGE_SIZE and LIST_MAX_PAGES.
	ListPageSize = 20
	ListMaxPages = 5
)

// TriState is the answer of CodeIsListed: TTLock's list may be incomplete.
type TriState int8

const (
	TriUnknown TriState = iota // Python None: the list was incomplete or answered -1007
	TriNo                      // Python False: the whole list was read and the id is not on it
	TriYes                     // Python True
)

// Lock is one entry of the list check_locks returns and stores in locks_json.
// Field names and JSON keys match the Python dict keys.
type Lock struct {
	LockID     string `json:"lock_id"`
	Alias      string `json:"alias"`
	Battery    any    `json:"battery"`
	TZOffsetMS any    `json:"tz_offset_ms"`
	KeyEnd     any    `json:"key_end"`
}

// ParseLocks ports locks_of: decodes a stored locks_json, empty meaning "[]".
func ParseLocks(raw []byte) ([]Lock, error) {
	if len(raw) == 0 {
		return []Lock{}, nil
	}
	var out []Lock
	if err := json.Unmarshal(raw, &out); err != nil {
		return nil, fmt.Errorf("ttlock: locks json: %w", err)
	}
	if out == nil {
		out = []Lock{}
	}
	return out, nil
}

// randomBytes returns n bytes from crypto/rand.
func randomBytes(n int) ([]byte, error) {
	b := make([]byte, n)
	if _, err := rand.Read(b); err != nil {
		return nil, err
	}
	return b, nil
}

// randomPIN ports _random_custom_pin: a 7-digit number from 1000000 to 9999999.
func randomPIN() (string, error) {
	n, err := rand.Int(rand.Reader, big.NewInt(9_000_000))
	if err != nil {
		return "", err
	}
	return strconv.FormatInt(n.Int64()+1_000_000, 10), nil
}

// lockInt ports int(lock_id).
func lockInt(lockID string) (int64, error) {
	n, err := strconv.ParseInt(strings.TrimSpace(lockID), 10, 64)
	if err != nil {
		return 0, fmt.Errorf("ttlock: lock id: %w", err)
	}
	return n, nil
}

// wholeHour ports _whole_hour: TTLock periods are whole hours in milliseconds.
func wholeHour(ms int64) error {
	if ms%3_600_000 != 0 {
		return ErrWholeHour
	}
	return nil
}

// validPermanentPIN is the check in add_permanent_code: ASCII digits, 4 to 9 long.
func validPermanentPIN(pin string) bool {
	if len(pin) < 4 || len(pin) > 9 {
		return false
	}
	for i := 0; i < len(pin); i++ {
		if pin[i] < '0' || pin[i] > '9' {
			return false
		}
	}
	return true
}

// StayWindow ports stay_window: the check-in and check-out instants in Unix milliseconds,
// with buffer_hours added on both sides. Hours are wall-clock in Europe/Prague, as the
// Python code does arithmetic on wall-clock datetimes.
func StayWindow(dateFrom, dateTo string, checkinHour, checkoutHour, bufferHours int) (int64, int64, error) {
	if bufferHours < 0 {
		return 0, 0, ErrBufferHours
	}
	if checkinHour < 0 || checkinHour > 23 || checkoutHour < 0 || checkoutHour > 23 {
		return 0, 0, ErrHour
	}
	loc, err := time.LoadLocation(stayZone)
	if err != nil {
		return 0, 0, err
	}
	startDay, err := time.Parse("2006-01-02", dateFrom)
	if err != nil {
		return 0, 0, fmt.Errorf("ttlock: date_from: %w", err)
	}
	endDay, err := time.Parse("2006-01-02", dateTo)
	if err != nil {
		return 0, 0, fmt.Errorf("ttlock: date_to: %w", err)
	}
	start := time.Date(startDay.Year(), startDay.Month(), startDay.Day(), checkinHour-bufferHours, 0, 0, 0, loc)
	end := time.Date(endDay.Year(), endDay.Month(), endDay.Day(), checkoutHour+bufferHours, 0, 0, 0, loc)
	if !end.After(start) {
		return 0, 0, ErrWindow
	}
	return start.UnixMilli(), end.UnixMilli(), nil
}

// CreateAccount ports create_account: registers a UbyHost user at TTLock (random name and
// password, md5 sent), stores it, then logs in. Returns the row id. An existing row for the
// host is returned unchanged. If the login fails, the row exists and its id is returned with the error.
func (c *Client) CreateAccount(ctx context.Context, ownerUserID int64) (int64, error) {
	existing, err := c.accounts.ForOwner(ctx, ownerUserID)
	if err != nil {
		return 0, err
	}
	if existing != nil {
		return existing.ID, nil
	}
	idBytes, err := randomBytes(8)
	if err != nil {
		return 0, err
	}
	pwBytes, err := randomBytes(18)
	if err != nil {
		return 0, err
	}
	username := "uh" + hex.EncodeToString(idBytes)
	password := base64.RawURLEncoding.EncodeToString(pwBytes) // token_urlsafe(18)
	answer, err := c.post(ctx, "/v3/user/register", map[string]any{
		"username": username,
		"password": md5Password(password),
	}, PriorityNormal)
	if err != nil {
		return 0, err
	}
	prefixed, err := field(answer, "username")
	if err != nil {
		return 0, err
	}
	id, err := c.accounts.Insert(ctx, ownerUserID, prefixed, password, c.now())
	if err != nil {
		return 0, err
	}
	if _, err := c.login(ctx, id); err != nil {
		return id, err
	}
	return id, nil
}

// CheckLocks ports check_locks: reads every page of /v3/key/list and keeps the locks where
// UbyHost is a top admin or holds key right 1. Other keys are counted as "plain" (eKeys
// cannot make codes). The list is saved to the account row. ListAdminLocks ports list_admin_locks.
func (c *Client) CheckLocks(ctx context.Context, accountID int64) ([]Lock, int, error) {
	pageNo := 1
	items := []Lock{}
	plain := 0
	for {
		answer, err := c.call(ctx, accountID, "/v3/key/list", map[string]any{"pageNo": pageNo, "pageSize": 1000}, PriorityLow)
		if err != nil {
			return nil, 0, err
		}
		for _, raw := range listOf(answer) {
			status := ""
			if v, ok := raw["keyStatus"]; ok {
				status = pyStr(v)
			}
			if status != adminKeyStatus {
				continue
			}
			userType := ""
			if v, ok := raw["userType"]; ok {
				userType = pyStr(v)
			}
			keyRight, err := intOr0(raw["keyRight"])
			if err != nil {
				return nil, 0, err
			}
			if userType != topAdminType && keyRight != 1 {
				plain++
				continue
			}
			lid, ok := raw["lockId"]
			if !ok {
				return nil, 0, fmt.Errorf("ttlock: key list entry has no lockId")
			}
			items = append(items, Lock{
				LockID:     pyStr(lid),
				Alias:      firstTruthyStr(raw["lockAlias"], raw["lockName"]),
				Battery:    raw["electricQuantity"],
				TZOffsetMS: raw["timezoneRawOffset"],
				KeyEnd:     raw["endDate"],
			})
		}
		pages := int64(1)
		if v, ok := answer["pages"]; ok && truthy(v) {
			n, err := asInt(v)
			if err != nil {
				return nil, 0, err
			}
			pages = n
		}
		if int64(pageNo) >= pages {
			break
		}
		pageNo++
	}
	raw, err := json.Marshal(items)
	if err != nil {
		return nil, 0, err
	}
	if err := c.accounts.SaveLocks(ctx, accountID, raw, c.now()); err != nil {
		return nil, 0, err
	}
	return items, plain, nil
}

// ListAdminLocks ports list_admin_locks: CheckLocks without the plain-key count.
func (c *Client) ListAdminLocks(ctx context.Context, accountID int64) ([]Lock, error) {
	locks, _, err := c.CheckLocks(ctx, accountID)
	return locks, err
}

// firstTruthyStr ports `a or b or ""` for the alias fields, rendered as a string.
func firstTruthyStr(values ...any) string {
	for _, v := range values {
		if truthy(v) {
			return pyStr(v)
		}
	}
	return ""
}

// CreatePeriodCode ports create_period_code: TTLock makes a type-3 (period) code and returns
// its digits and id. Window hours must be whole hours.
func (c *Client) CreatePeriodCode(ctx context.Context, accountID int64, lockID string, startMS, endMS int64, name, priority string) (string, string, error) {
	if err := wholeHour(startMS); err != nil {
		return "", "", err
	}
	if err := wholeHour(endMS); err != nil {
		return "", "", err
	}
	lid, err := lockInt(lockID)
	if err != nil {
		return "", "", err
	}
	answer, err := c.call(ctx, accountID, "/v3/keyboardPwd/get", map[string]any{
		"lockId":          lid,
		"keyboardPwdType": 3,
		"keyboardPwdName": name,
		"startDate":       startMS,
		"endDate":         endMS,
	}, priority)
	if err != nil {
		return "", "", err
	}
	pin, err := field(answer, "keyboardPwd")
	if err != nil {
		return "", "", err
	}
	codeID, err := field(answer, "keyboardPwdId")
	if err != nil {
		return "", "", err
	}
	return pin, codeID, nil
}

// AddCustomCode ports add_custom_code: sends a random 7-digit PIN with /v3/keyboardPwd/add.
// If TTLock refuses the PIN (-3007 or -2032), one new PIN is drawn and sent once more.
func (c *Client) AddCustomCode(ctx context.Context, accountID int64, lockID string, startMS, endMS int64, name, priority string) (string, string, error) {
	if err := wholeHour(startMS); err != nil {
		return "", "", err
	}
	if err := wholeHour(endMS); err != nil {
		return "", "", err
	}
	lid, err := lockInt(lockID)
	if err != nil {
		return "", "", err
	}
	payload := func(pin string) map[string]any {
		return map[string]any{
			"lockId":          lid,
			"keyboardPwd":     pin,
			"keyboardPwdName": name,
			"keyboardPwdType": 3,
			"startDate":       startMS,
			"endDate":         endMS,
			"addType":         2,
		}
	}
	pin, err := randomPIN()
	if err != nil {
		return "", "", err
	}
	answer, err := c.call(ctx, accountID, "/v3/keyboardPwd/add", payload(pin), priority)
	if err != nil {
		te, ok := AsError(err)
		if !ok || !containsInt(newPINErrcodes, te.Code) {
			return "", "", err
		}
		if pin, err = randomPIN(); err != nil {
			return "", "", err
		}
		if answer, err = c.call(ctx, accountID, "/v3/keyboardPwd/add", payload(pin), priority); err != nil {
			return "", "", err
		}
	}
	codeID, err := field(answer, "keyboardPwdId")
	if err != nil {
		return "", "", err
	}
	return pin, codeID, nil
}

func containsInt(xs []int, v int) bool {
	for _, x := range xs {
		if x == v {
			return true
		}
	}
	return false
}

// FindCodeByName ports find_code_by_name: one page of /v3/lock/listKeyboardPwd searched by name.
// It returns the first code with this exact name and the same window. found is false when none matches.
func (c *Client) FindCodeByName(ctx context.Context, accountID int64, lockID, name string, startMS, endMS int64) (string, string, bool, error) {
	lid, err := lockInt(lockID)
	if err != nil {
		return "", "", false, err
	}
	answer, err := c.call(ctx, accountID, "/v3/lock/listKeyboardPwd", map[string]any{
		"lockId":    lid,
		"searchStr": name,
		"orderBy":   1,
		"pageNo":    1,
		"pageSize":  20,
	}, PriorityNormal)
	if err != nil {
		return "", "", false, err
	}
	for _, raw := range listOf(answer) {
		nameVal := ""
		if v, ok := raw["keyboardPwdName"]; ok {
			nameVal = pyStr(v)
		}
		if nameVal != name {
			continue
		}
		start, err := intOr0(raw["startDate"])
		if err != nil {
			return "", "", false, err
		}
		if start != startMS {
			continue
		}
		end, err := intOr0(raw["endDate"])
		if err != nil {
			return "", "", false, err
		}
		if end != endMS {
			continue
		}
		pin, err := field(raw, "keyboardPwd")
		if err != nil {
			return "", "", false, err
		}
		codeID, err := field(raw, "keyboardPwdId")
		if err != nil {
			return "", "", false, err
		}
		return pin, codeID, true, nil
	}
	return "", "", false, nil
}

// readListing ports _read_listing: the one paging loop over /v3/lock/listKeyboardPwd.
// It returns the entries keep accepts. complete is false (Python None) when an answer has no
// list, when the page limit ran out first, or when TTLock answers -1007 on any page. stopAtFirst
// returns at the first kept entry. A full page is always read on, whatever pages says.
func (c *Client) readListing(ctx context.Context, accountID int64, lockID, name string, keep func(map[string]any) bool, stopAtFirst bool) ([]map[string]any, bool, error) {
	lid, err := lockInt(lockID)
	if err != nil {
		return nil, false, err
	}
	var kept []map[string]any
	for page := 1; page <= ListMaxPages; page++ {
		answer, err := c.call(ctx, accountID, "/v3/lock/listKeyboardPwd", map[string]any{
			"lockId":    lid,
			"searchStr": name,
			"orderBy":   1,
			"pageNo":    page,
			"pageSize":  ListPageSize,
		}, PriorityNormal)
		if err != nil {
			if te, ok := AsError(err); ok && te.Code == NoPasscodeDataCode {
				return nil, false, nil
			}
			return nil, false, err
		}
		items, ok := answer["list"].([]any)
		if !ok {
			return nil, false, nil
		}
		for _, it := range items {
			if raw, ok := it.(map[string]any); ok && keep(raw) {
				kept = append(kept, raw)
			}
		}
		if len(kept) > 0 && stopAtFirst {
			return kept, true, nil
		}
		if len(items) < ListPageSize {
			return kept, true, nil
		}
	}
	return nil, false, nil
}

// CodeIsListed ports code_is_listed: is the lock code with this id on the lock? The id decides,
// not the name or the window. TriNo only when the whole list was read.
func (c *Client) CodeIsListed(ctx context.Context, accountID int64, lockID, name, codeID string) (TriState, error) {
	kept, complete, err := c.readListing(ctx, accountID, lockID, name, func(raw map[string]any) bool {
		v, ok := raw["keyboardPwdId"]
		if !ok {
			return pyStr(nil) == codeID
		}
		return pyStr(v) == codeID
	}, true)
	if err != nil {
		return TriUnknown, err
	}
	if !complete {
		return TriUnknown, nil
	}
	if len(kept) > 0 {
		return TriYes, nil
	}
	return TriNo, nil
}

// CodesNamed ports codes_named: every raw entry whose name is exactly name. complete is false
// (Python None) when the list is incomplete; an empty slice with complete true means none has that name.
func (c *Client) CodesNamed(ctx context.Context, accountID int64, lockID, name string) ([]map[string]any, bool, error) {
	return c.readListing(ctx, accountID, lockID, name, func(raw map[string]any) bool {
		s, ok := raw["keyboardPwdName"].(string)
		return ok && s == name
	}, false)
}

// ChangeCodePeriod ports change_code_period: moves an existing code's window (changeType 2).
func (c *Client) ChangeCodePeriod(ctx context.Context, accountID int64, lockID, codeID string, startMS, endMS int64, priority string) error {
	if err := wholeHour(startMS); err != nil {
		return err
	}
	if err := wholeHour(endMS); err != nil {
		return err
	}
	lid, err := lockInt(lockID)
	if err != nil {
		return err
	}
	kid, err := lockInt(codeID)
	if err != nil {
		return err
	}
	_, err = c.call(ctx, accountID, "/v3/keyboardPwd/change", map[string]any{
		"lockId":        lid,
		"keyboardPwdId": kid,
		"startDate":     startMS,
		"endDate":       endMS,
		"changeType":    2,
	}, priority)
	return err
}

// DeleteCode ports delete_code (deleteType 2). The Python default priority is critical;
// callers pass PriorityCritical to keep it.
func (c *Client) DeleteCode(ctx context.Context, accountID int64, lockID, codeID, priority string) error {
	lid, err := lockInt(lockID)
	if err != nil {
		return err
	}
	kid, err := lockInt(codeID)
	if err != nil {
		return err
	}
	_, err = c.call(ctx, accountID, "/v3/keyboardPwd/delete", map[string]any{
		"lockId":        lid,
		"keyboardPwdId": kid,
		"deleteType":    2,
	}, priority)
	return err
}

// QueryLockTime ports query_lock_time: the lock's clock in Unix milliseconds (/v3/lock/queryDate).
func (c *Client) QueryLockTime(ctx context.Context, accountID int64, lockID string) (int64, error) {
	lid, err := lockInt(lockID)
	if err != nil {
		return 0, err
	}
	answer, err := c.call(ctx, accountID, "/v3/lock/queryDate", map[string]any{"lockId": lid}, PriorityLow)
	if err != nil {
		return 0, err
	}
	return dateField(answer)
}

// AdjustLockTime ports adjust_lock_time: sets the lock's clock (/v3/lock/updateDate) and returns the new value.
func (c *Client) AdjustLockTime(ctx context.Context, accountID int64, lockID string) (int64, error) {
	lid, err := lockInt(lockID)
	if err != nil {
		return 0, err
	}
	answer, err := c.call(ctx, accountID, "/v3/lock/updateDate", map[string]any{"lockId": lid}, PriorityNormal)
	if err != nil {
		return 0, err
	}
	return dateField(answer)
}

func dateField(answer map[string]any) (int64, error) {
	v, ok := answer["date"]
	if !ok {
		return 0, fmt.Errorf("ttlock: answer has no date")
	}
	return asInt(v)
}

// DeleteAccount ports delete_account: asks TTLock to delete the user, then removes the row even
// when TTLock fails, and returns the TTLock error. A missing row is a no-op.
func (c *Client) DeleteAccount(ctx context.Context, accountID int64) error {
	acc, err := c.accounts.Load(ctx, accountID)
	if err != nil {
		return err
	}
	if acc == nil {
		return nil
	}
	_, postErr := c.post(ctx, "/v3/user/delete", map[string]any{"username": acc.Username}, PriorityNormal)
	if err := c.accounts.Delete(ctx, accountID); err != nil {
		return err
	}
	return postErr
}

// AddPermanentCode ports add_permanent_code: a custom permanent PIN (type 2) through the gateway.
// The caller keeps the PIN and name for retries. Returns the TTLock keyboardPwdId.
func (c *Client) AddPermanentCode(ctx context.Context, accountID int64, lockID, pin, name string) (string, error) {
	if !validPermanentPIN(pin) {
		return "", ErrInvalidPermanentPIN
	}
	lid, err := lockInt(lockID)
	if err != nil {
		return "", err
	}
	answer, err := c.call(ctx, accountID, "/v3/keyboardPwd/add", map[string]any{
		"lockId":          lid,
		"keyboardPwd":     pin,
		"keyboardPwdName": name,
		"keyboardPwdType": 2,
		"addType":         2,
	}, PriorityNormal)
	if err != nil {
		return "", err
	}
	return field(answer, "keyboardPwdId")
}
