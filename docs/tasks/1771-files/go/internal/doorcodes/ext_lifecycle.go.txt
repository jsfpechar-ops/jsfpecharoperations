package doorcodes

import (
	"context"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ttlock"
)

// HostNotices is mail_notify.door_code_notice(door_code_id, stage, key_suffix). An empty
// keySuffix is Python's None. Phase 1's Mailer.DoorCodeNotice has no key suffix, so the
// lifecycle takes this interface instead and deps.go does not change.
type HostNotices interface {
	DoorCodeNotice(ctx context.Context, doorCodeID int64, stage, keySuffix string) error
}

// LockCodes is the part of the TTLock client that the lifecycle calls and the TTLock interface
// in deps.go lacks: ttlock.delete_code and ttlock.code_is_listed. *ttlock.Client satisfies it.
type LockCodes interface {
	DeleteCode(ctx context.Context, accountID int64, lockID, codeID, priority string) error
	CodeIsListed(ctx context.Context, accountID int64, lockID, name, codeID string) (ttlock.TriState, error)
}

// Lifecycle is the revoke, cancel and move half of door_codes.py (lines 802-1373). It embeds
// the Service, so the phase-1 methods (Issue, SendCodeMail, loadDoorCode, ...) are promoted.
type Lifecycle struct {
	*Service
	Notices HostNotices
	Locks   LockCodes
}

// lcErrcodeKinds is ttlock.ERROR_KINDS. The table in go/internal/ttlock is unexported, so
// _already_gone keeps this copy: it only needs to know whether an errcode is mapped, and
// whether it maps to code_missing. Keep it in step with errorKinds in client.go.
var lcErrcodeKinds = map[int]string{
	10003: ttlock.KindAuth,
	10004: ttlock.KindAuth,
	10011: ttlock.KindReauth,
	10007: ttlock.KindLogin,
	10000: ttlock.KindConfig,
	10001: ttlock.KindConfig,
	10005: ttlock.KindPermission,
	30001: ttlock.KindPermission,
	-2018: ttlock.KindPermission,
	20002: ttlock.KindPermission,
	30006: ttlock.KindRate,
	30007: ttlock.KindBudget,
	80000: ttlock.KindClock,
	-2012: ttlock.KindOffline,
	-4056: ttlock.KindStorage,
	-3009: ttlock.KindStorage,
	90000: ttlock.KindTransient,
	1:     ttlock.KindTransient,
	-3:    ttlock.KindBug,
	-3008: ttlock.KindUnusedCode,
	-1026: ttlock.KindPeriodTaken,
	-3007: ttlock.KindDuplicate,
	-1007: ttlock.KindCodeMissing,
	-3002: ttlock.KindOffline,
	-3003: ttlock.KindOffline,
	-3035: ttlock.KindOffline,
	-3036: ttlock.KindOffline,
	-3037: ttlock.KindOffline,
	-2025: ttlock.KindOffline,
	-1003: ttlock.KindLockSetup,
	-4037: ttlock.KindLockSetup,
	-4043: ttlock.KindLockSetup,
	-3034: ttlock.KindLockSetup,
	-4067: ttlock.KindLockSetup,
	-4063: ttlock.KindConfig,
	30008: ttlock.KindConfig,
	80002: ttlock.KindBug,
	-2009: ttlock.KindBug,
	-2032: ttlock.KindBug,
	-3006: ttlock.KindBug,
	-3045: ttlock.KindBug,
}
